"""OpenMHS driver for gh.ad-sdl/pf400_module_ros: the PF400 collaborative robot arm through its TCP command server.

Authored by Grok (grok-4.7, a model and not a human) on 2026-11-05 (the user's decision of 2026-11-05:
Grok authors, Codex reviews). The card's ros/RosDriver route is replaced by the override
MHS/registry/overrides/p5-reauthor-pf400-routing.json, which selects ``pf400_driver.pf400_driver.tcp_driver:PF400``
(tcp_driver.py:12). This package serves robot 1 only:

* ``x-cap.ad-sdl.move_joints.v1`` (R2): on the robot port, ``mspeed`` then ``MoveJ``. Class_command.gpl:280 sets
  the default reply to 0. The client says a leading 0 means the command was successful (tcp_driver.py:23). Neither
  line is a reached flag. Profile, joint targets and speed are ``Limit.operator_required``.
* ``x-cap.ad-sdl.halt.v1`` (the safe-state action) and the e-stop: one status-port connection, ``selectRobot 1``,
  then ``halt``, then ``state`` until TrajState is 0 or 1. The status port serves one client (Main.gpl:88-90).
  A busy or unreachable status port fails the stop. The socket is closed before the stop returns, so the
  safe-state action can open the port again. ``Cmd_Halt`` is ``Robot.RapidDecel`` (Cmd.gpl:1840-1842) and does not
  retire a command still in the mailbox. The mailbox is cleared after the handler returns (Main.gpl:605-607), and
  the reply is sent only after that wait (Main.gpl:207-209, then Main.gpl:225). A complete MoveJ reply is that
  retirement. The stop that sees no reply yet fails and does not report the safe state. The next halt, after the
  reply, reads TrajState again before it confirms. A robot-port connect does not share its handshake with the
  status port: each caller binds ``port`` on its own thread (tcp_driver.py:117) and copies it before the handshake.
  Cancellation and publication of the socket share one lock that is not held across ``connect_robot``. A handshake
  the caller has abandoned is closed by the caller or the worker, including when the socket becomes ready in the
  gap after the first cancel check.

``stop_robot`` (tcp_driver.py:399-409) is not used. It sends ``halt`` through ``send_command``. ``connect_robot``
uses ``self.port`` (tcp_driver.py:117) and ``send_command`` receives with ``recv`` and no ``settimeout``
(tcp_driver.py:156). The client says a second command will not reply until the first motion is complete
(tcp_driver.py:19). The comm thread waits until the robot mailbox is clear (Main.gpl:203-209). ``selectRobot`` and
``halt`` are two receives: NewRobNum is applied at the start of the next receive (Main.gpl:98-123), not between
lines already in one buffer.

No power, attach, home, reset, gripper or re-enable is served. The lab client's status-port init calls
``enable_power`` (pf400_driver.py:275-278); this package does not. A reset of the MHS latch does not resume motion.
Joint angles are degrees for rotary axes and millimetres for linear axes (tcp_driver.py:486-488). The host is
the operator's; the clone's example addresses are not pins.
"""

from __future__ import annotations

import math
import sys
import threading
import time

from mhs.driver import Busy, Cancelled, Driver, DriverFailed, Fact, Field, Limit, OutcomeUnknown, action, estop, read
from mhs.errors import MHSError

TCS = "resources/original_tcp_code/Tcp_cmd_server_3_0_c1_INSTALLATION/Tcp_cmd_server"
CMD = f"{TCS}/Cmd.gpl"
MAIN = f"{TCS}/Main.gpl"
GLOBALS = f"{TCS}/Globals.gpl"
STARTUP = f"{TCS}/Startup.gpl"
CLASS_CMD = f"{TCS}/Class_command.gpl"
TCP = "pf400_driver/pf400_driver/tcp_driver.py"
PF400_PY = "pf400_driver/pf400_driver/pf400_driver.py"

#: Absolute budget for one status-port stop: connect, both commands, the reply bytes and the TrajState polls.
#: It is not a controller fact. The idle fake confirms on the first read, so the gate stays under 2 s.
#: ``@estop(latency_ms=15000)`` is the ceiling; ``stop_confirm_s`` cannot be set above it.
ESTOP_LATENCY_S = 15.0
STOP_CONFIRM_S = 4.0
POLL_S = 0.05
#: Driver budgets, not controller facts.
READ_TIMEOUT_S = 1.0
MOVE_RECV_S = 30.0
REPLY_CAP = 4096
DEFAULT_ROBOT_PORT = 10100
DEFAULT_STATUS_PORT = 10000

_MISSING = object()
_LOCK_GUARD = threading.Lock()

_PROFILE = Limit.operator_required(
    "Cmd.gpl:116 rejects a profile index below 1 or above N_PROF, and Globals.gpl:82 sets N_PROF to 20. "
    "Those two numbers are not in one file, and one field cannot carry two limits, so the operator overlay "
    "supplies the profile bound. An undefined profile is a negative reply and is a failure.")
_JOINTS = Limit.operator_required(
    "MoveJ angles are degrees for rotary axes and millimetres for linear axes (tcp_driver.py:486-488); "
    "the clone states no joint envelope",
    path="[*]")
_SPEED = Limit.operator_required(
    "mspeed takes the new system speed as a percentage (Cmd.gpl:532) and the GPL states no numeric range; "
    "tcp_driver.py:498's 0-100 is the client's comment, not a controller limit")


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", f"{name} must be a finite number")


class PF400Arm(Driver):
    device_id = "pf400"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    native = "pf400_driver.pf400_driver.tcp_driver:PF400"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePF400"}
    vendor, model = "PF400", "collaborative robot arm"
    display_name = "PF400 arm through ad-sdl pf400_module_ros"
    estop_timeout_ms = 20000
    tags = ["pf400", "arm", "tcp", "tcs", "cobot"]
    safe_state = ("TrajState 0 or 1 with power still on, and only when this endpoint has no unanswered MoveJ; "
                  "RapidDecel does not retire a mailbox command. The arm may hold or sag, and this package does "
                  "not re-enable power, attach or home and offers no unpause")
    facts = [
        Fact("Startup declares Status1Port 10000 and Robot1Port 10100. StartMain opens the status port with "
             "TcpComMain(0, Status1Port) and TcpCom1 opens the robot port with TcpComMain(1, Robot1Port). The "
             "startup comment says a motion thread can block and the status thread does not",
             source="upstream_code", ref=f"{STARTUP}:42-157"),
        Fact("The status thread is robot 0 with IsStatus set, and after AcceptSocket it stops listening so the "
             "port serves one client", source="upstream_code", ref=f"{MAIN}:59-90"),
        Fact("NewRobNum is applied at the start of the next receive, before that receive's bytes are read",
             source="upstream_code", ref=f"{MAIN}:98-123"),
        Fact("A status command runs in the comm thread; a robot-port command is posted to the robot mailbox and "
             "the comm thread waits until the mailbox is clear", source="upstream_code", ref=f"{MAIN}:199-210"),
        Fact("After Handler returns, the robot thread sets the mailbox to Nothing and wakes the comm thread",
             source="upstream_code", ref=f"{MAIN}:603-607"),
        Fact("PC mode's default reply is 0", source="upstream_code", ref=f"{CLASS_CMD}:280"),
        Fact("The client states that a response begins with 0 when the command was successful, or a negative "
             "error code", source="upstream_code", ref=f"{TCP}:23"),
        Fact("The PC-mode reply on the socket is Cmd.Reply followed by CR LF", source="upstream_code",
             ref=f"{MAIN}:225"),
        Fact("halt calls Robot.RapidDecel for the command's robot and the comment says motion stops with power "
             "left on; the handler does not clear a destination", source="upstream_code", ref=f"{CMD}:1833-1841"),
        Fact("In PC mode, state replies 0 and the integer Robot.TrajState of the selected robot",
             source="upstream_code", ref=f"{CMD}:1816-1828"),
        Fact("TrajState labels are 0 Halted, 1 Idle, 2 to 6 position-mode motion, 8 velocity, 9 homing, 10 jog, "
             "11 external trajectory and 15 motion terminated nulling", source="upstream_code",
             ref=f"{GLOBALS}:118-129"),
        Fact("Check_ProfIdx rejects an index below 1 or above N_PROF; success leaves the reply unchanged",
             source="upstream_code", ref=f"{CMD}:111-122"),
        Fact("N_PROF is the constant 20", source="upstream_code", ref=f"{GLOBALS}:82"),
        Fact("MoveJ takes a profile index and up to 12 angle parameters, calls Move.Loc when there are more "
             "parameters than axes, and does not change its reply to a reached flag", source="upstream_code",
             ref=f"{CMD}:1688-1727"),
        Fact("Joint angles are degrees for rotary axes and millimetres for linear axes", source="upstream_code",
             ref=f"{TCP}:486-488"),
        Fact("mspeed's optional parameter is the new system speed as a percentage and is stored in PDbNum 601; "
             "those lines state no numeric range", source="upstream_code", ref=f"{CMD}:524-546"),
        Fact("On the status thread, selectRobot requests NewRobNum for the given robot; selecting the current "
             "robot leaves the reply at the default", source="upstream_code", ref=f"{CMD}:565-593"),
        Fact("The command delegate is Cmd_ concatenated with the first token as received", source="upstream_code",
             ref=f"{CLASS_CMD}:304"),
        Fact("stop_robot assigns halt and sends it through send_command", source="upstream_code",
             ref=f"{TCP}:399-409"),
        Fact("connect_robot connects to self.host and self.port", source="upstream_code", ref=f"{TCP}:117"),
        Fact("send_command receives with recv and that line does not call settimeout", source="upstream_code",
             ref=f"{TCP}:156"),
        Fact("The client states that a second command will not reply until the first motion is complete",
             source="upstream_code", ref=f"{TCP}:19"),
        Fact("A socket.error around socket() falls off the end of connect_robot. connect() is outside that "
             "handler, so its socket.error propagates. send_command returns the string failed on socket.error",
             source="upstream_code", ref=f"{TCP}:103-170"),
        Fact("The lab client's status-port init sends selectRobot 1 and then enable_power",
             source="upstream_code", ref=f"{PF400_PY}:275-278"),
        Fact("The lab client's movement-state comment labels 0 as power off and 1 as stopping",
             source="upstream_code", ref=f"{PF400_PY}:307-315"),
    ]

    # -- lifecycle -------------------------------------------------------------------------------------------------
    def setup(self):
        options = dict(self.options or {})
        robot = options.get("robot_port", DEFAULT_ROBOT_PORT)
        status = options.get("status_port", DEFAULT_STATUS_PORT)
        for name, value in (("robot_port", robot), ("status_port", status)):
            if isinstance(value, bool) or not isinstance(value, int) or not 0 < value < 65536:
                raise ValueError(f"{name} must be a TCP port number")
        if robot == status:
            raise ValueError("robot_port and status_port must differ")
        confirm = options.get("stop_confirm_s", STOP_CONFIRM_S)
        if (isinstance(confirm, bool) or not isinstance(confirm, (int, float)) or not math.isfinite(float(confirm))
                or not 0 < float(confirm) <= ESTOP_LATENCY_S):
            raise ValueError("stop_confirm_s must be a positive number of seconds at most the 15 s e-stop latency")
        self._robot_port = robot
        self._status_port = status
        self._stop_confirm_s = float(confirm)
        self._stop_generation = 0
        self._motion_open = False
        self._motion_unconfirmed = False
        self._command_fenced = False

    def _stop_lock(self):
        lock = getattr(self, "_pf400_stop_lock", None)
        if lock is None:
            with _LOCK_GUARD:
                lock = getattr(self, "_pf400_stop_lock", None)
                if lock is None:
                    lock = threading.Lock()
                    self._pf400_stop_lock = lock
        return lock

    def _before_send(self):
        """Test seam. Runs on the move's thread and does not hold the stop lock."""

    def _before_socket_handoff(self):
        """Test seam. Runs after ``connect_robot`` returns and before the handoff lock decides ownership."""

    # -- port I/O --------------------------------------------------------------------------------------------------
    def _release(self, sock, saved):
        failed = sys.exc_info()[1] is not None
        if sock is not None:
            try:
                self.native.disconnect_robot(sock)
            except Exception:
                if not failed:
                    raise
        if saved is not _MISSING:
            try:
                self.native.port = saved
            except Exception:
                if not failed:
                    raise

    def _remaining(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("the deadline is exhausted")
        return remaining

    def _connect(self, port, deadline):
        """Open ``port`` without blocking another port's handshake.

        ``connect_robot`` reads ``self.port`` (tcp_driver.py:117). The worker binds that attribute on its own
        thread, then connects. No lock is held across the handshake, so a robot-port connect that is still in
        progress cannot postpone a status-port halt. The handoff lock covers only the decision to publish the
        socket or abandon it. When this wait expires, a socket already published is closed here. A socket that
        becomes ready afterwards is closed by the worker and is not published.
        """
        remaining = self._remaining(deadline)
        box = {}
        cancelled = threading.Event()
        handoff = threading.Lock()

        def run():
            threading.current_thread().pf400_connect_cancel = cancelled
            sock = None
            try:
                self.native.port = port
                sock = self.native.connect_robot()
                if cancelled.is_set():
                    return
                self._before_socket_handoff()
                with handoff:
                    if cancelled.is_set():
                        return
                    box["sock"] = sock
                    sock = None
            except Exception as exc:  # noqa: BLE001 - the caller thread raises this
                with handoff:
                    if not cancelled.is_set():
                        box["err"] = exc
            finally:
                if sock is not None:
                    try:
                        self.native.disconnect_robot(sock)
                    except Exception:
                        pass

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        worker.join(remaining)
        with handoff:
            if worker.is_alive():
                late = box.pop("sock", None)
                cancelled.set()
                timed_out = True
            else:
                late = None
                timed_out = False
        if late is not None:
            try:
                self.native.disconnect_robot(late)
            except Exception:
                pass
        if timed_out:
            raise TimeoutError("connect exceeded the deadline")
        if "err" in box:
            raise box["err"]
        sock = box.get("sock")
        if sock is None:
            raise DriverFailed("MHS.DEVICE.FAULTED", "connect returned no socket")
        return sock

    def _send_line(self, sock, line, deadline):
        if "\n" in line or "\r" in line:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "a command must be one line")
        try:
            payload = (line + "\n").encode("ascii")
        except UnicodeEncodeError as exc:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "a command must be ASCII") from exc
        sock.settimeout(self._remaining(deadline))
        sock.sendall(payload)

    def _read_reply(self, sock, deadline):
        """Read one LF-terminated reply. Each recv uses the time left until ``deadline``, not a fresh timeout."""
        buf = b""
        while b"\n" not in buf:
            if len(buf) >= REPLY_CAP:
                raise TimeoutError("the reply exceeded the receive cap")
            sock.settimeout(self._remaining(deadline))
            chunk = sock.recv(REPLY_CAP)
            if not chunk:
                raise ConnectionError("the controller closed the socket")
            buf += chunk
        text = buf.split(b"\n", 1)[0].decode("ascii", "replace").replace("\r", "").strip()
        return text

    def _exchange(self, sock, line, deadline):
        self._send_line(sock, line, deadline)
        return self._read_reply(sock, deadline)

    def _require_zero(self, reply):
        token = reply.split()[0] if reply else ""
        try:
            code = int(token)
        except ValueError:
            code = None
        if code != 0:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the controller replied {reply!r}")
        return reply

    def _state_value(self, reply):
        self._require_zero(reply)
        parts = reply.split()
        if len(parts) < 2:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"state reply {reply!r} has no TrajState")
        try:
            return int(parts[1])
        except ValueError as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"state reply {reply!r} has no TrajState") from exc

    def _token(self, value):
        return format(float(value), ".12g")

    # -- stop ------------------------------------------------------------------------------------------------------
    def _outstanding(self):
        return self._command_fenced or self._motion_open or self._motion_unconfirmed

    def _status_halt(self):
        """selectRobot 1, halt, then state, on one status-port connection.

        Connect, sends and replies do not hold the stop lock, so a move blocked in ``recv`` cannot postpone
        ``halt``. The status handshake does not share a lock with a robot-port handshake. One deadline covers
        the connection and every reply byte. A MoveJ that was written and has not been answered is still in the
        controller's buffer or mailbox (Main.gpl:204). Cmd.gpl:1840-1842 is only RapidDecel, so that case fails
        and keeps the fence. A complete reply is sent after the mailbox wait (Main.gpl:207-209, Main.gpl:225) and
        retires the fence on the move's thread. Confirmation is a later halt and a fresh TrajState read.
        """
        deadline = time.monotonic() + self._stop_confirm_s
        sock = None
        try:
            with self._stop_lock():
                self._stop_generation += 1
            sock = self._connect(self._status_port, deadline)
            self._require_zero(self._exchange(sock, "selectRobot 1", deadline))
            self._require_zero(self._exchange(sock, "halt", deadline))
            with self._stop_lock():
                outstanding = self._outstanding()
            if outstanding:
                raise DriverFailed(
                    "MHS.DEVICE.FAULTED",
                    "a MoveJ was written and has no reply yet; RapidDecel does not retire a mailbox command")
            while True:
                reply = self._exchange(sock, "state", deadline)
                state = self._state_value(reply)
                if state in (0, 1):
                    with self._stop_lock():
                        if self._outstanding():
                            raise DriverFailed(
                                "MHS.DEVICE.FAULTED",
                                "a MoveJ was written during the stop; RapidDecel does not retire it")
                        self._command_fenced = False
                        self._motion_open = False
                        self._motion_unconfirmed = False
                        return {"traj_state": state, "reply": reply}
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise DriverFailed(
                        "MHS.DEVICE.FAULTED",
                        f"TrajState stayed {state} for {self._stop_confirm_s} s after the stop started")
                time.sleep(min(POLL_S, remaining))
        except (Cancelled, DriverFailed, Busy, OutcomeUnknown):
            raise
        except Exception as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"the status-port halt failed ({type(exc).__name__})") from exc
        finally:
            self._release(sock, _MISSING)

    # -- reads -----------------------------------------------------------------------------------------------------
    @read("traj_state", type="integer",
          description="Robot 1 TrajState from one state command on the robot port (0 halted, 1 idle)")
    def traj_state(self):
        deadline = time.monotonic() + READ_TIMEOUT_S
        sock = None
        try:
            with self._stop_lock():
                if self._outstanding():
                    raise Busy("robot 1 has a move whose reply is not confirmed; not opening the robot port")
            sock = self._connect(self._robot_port, deadline)
            with self._stop_lock():
                if self._outstanding():
                    raise Busy("robot 1 has a move whose reply is not confirmed; not opening the robot port")
            return self._state_value(self._exchange(sock, "state", deadline))
        except (Cancelled, DriverFailed, Busy, OutcomeUnknown):
            raise
        except Exception as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"reading state failed ({type(exc).__name__})") from exc
        finally:
            self._release(sock, _MISSING)

    def _admit_move(self, epoch, admitted):
        """Under the stop lock: cancellation, the e-stop epoch, and no stop that started after ``admitted``."""
        self.check_cancelled()
        self._refuse_if_estopped(epoch, "x-cap.ad-sdl.move_joints.v1")
        if admitted is not None and self._stop_generation != admitted:
            raise Cancelled("a status-port stop started before this send")
        if self._outstanding():
            raise Busy("a joint move on this endpoint is still unconfirmed; halt on the status port first")

    # -- actions ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.ad-sdl.move_joints.v1", risk="R2", long_running=True, cancellable=True,
            max_duration_ms=120000,
            description="Send mspeed and MoveJ for robot 1. A leading 0 is the client's success code "
                        "(tcp_driver.py:23), not proof the target was reached",
            input={
                "profile": Field("integer", unit="1",
                                 description="Motion profile index, a count. The operator's site limits bound it",
                                 limit=_PROFILE),
                "joints": Field("array", items=Field("number", unit="1"), min_items=1, max_items=12,
                                description="Joint targets sent unchanged. A rotary axis is degrees and a linear "
                                            "axis is millimetres (tcp_driver.py:486-488). Those are not one UCUM "
                                            "unit, so the element code is 1 and this package does not convert. "
                                            "At most 12 values (Cmd.gpl:1697). Fewer than the controller's axis "
                                            "count is a negative reply",
                                limit=_JOINTS),
                "speed": Field("number", unit="%",
                               description="System speed sent as mspeed before MoveJ. Cmd.gpl:532 calls it a "
                                           "percentage. The number is not scaled, and the GPL states no range",
                               limit=_SPEED),
            },
            output={
                "reply": Field("string", description="The MoveJ reply with CR LF removed"),
                "accepted": Field("boolean", description="True when the reply's first token is 0, the client's "
                                                         "success code (tcp_driver.py:23). Class_command.gpl:280 only "
                                                         "sets that default. This is not a reached flag"),
                "profile": Field("integer", unit="1", description="The profile index that was sent"),
                "joints": Field("array", items=Field("number", unit="1"),
                                description="The joint numbers that were sent, unconverted"),
                "speed": Field("number", unit="%", description="The mspeed number that was sent, unscaled"),
            })
    def move_joints(self, profile, joints, speed):
        if isinstance(profile, bool) or not isinstance(profile, int):
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "profile must be an integer")
        if not isinstance(joints, (list, tuple)) or not joints or len(joints) > 12:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID", "joints must hold 1 to 12 numbers")
        for item in joints:
            _finite(item, "joints")
        _finite(speed, "speed")
        line = "MoveJ " + str(profile) + " " + " ".join(self._token(item) for item in joints)
        speed_line = "mspeed " + self._token(speed)
        epoch = self.estop_epoch
        self._before_send()
        sock = None
        sent_move = False
        admitted = None
        generation = 0
        try:
            connect_deadline = time.monotonic() + READ_TIMEOUT_S
            sock = self._connect(self._robot_port, connect_deadline)
            mspeed_deadline = time.monotonic() + READ_TIMEOUT_S
            with self._stop_lock():
                self._admit_move(epoch, None)
                admitted = self._stop_generation
                self._send_line(sock, speed_line, mspeed_deadline)
            speed_reply = self._read_reply(sock, mspeed_deadline)
            self._require_zero(speed_reply)
            move_deadline = time.monotonic() + MOVE_RECV_S
            send_deadline = time.monotonic() + READ_TIMEOUT_S
            with self._stop_lock():
                self._admit_move(epoch, admitted)
                self._command_fenced = True
                try:
                    self._send_line(sock, line, send_deadline)
                except (Cancelled, DriverFailed, Busy, OutcomeUnknown, MHSError):
                    self._motion_open = True
                    self._motion_unconfirmed = True
                    raise
                except Exception as exc:
                    self._motion_open = True
                    self._motion_unconfirmed = True
                    raise OutcomeUnknown(
                        f"MoveJ may have been sent ({type(exc).__name__}); halt on the status port") from exc
                sent_move = True
                generation = self._stop_generation
                self._motion_open = True
            reply = self._read_reply(sock, move_deadline)
        except Cancelled:
            if sent_move:
                self._motion_unconfirmed = True
            raise
        except (DriverFailed, Busy, OutcomeUnknown, MHSError):
            if sent_move:
                self._motion_unconfirmed = True
            raise
        except Exception as exc:
            if sent_move or self._command_fenced:
                self._motion_unconfirmed = True
                raise OutcomeUnknown(
                    f"the MoveJ reply was not received ({type(exc).__name__}); halt on the status port") from exc
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the joint move failed ({type(exc).__name__})") from exc
        finally:
            self._release(sock, _MISSING)
        # A complete reply is the retirement. Main.gpl:225 sends it after the wait at Main.gpl:207-209, and
        # Main.gpl:605-607 clears the mailbox only after Handler returns. The move is still unknown when a
        # stop started, and the safe state is a later halt plus a fresh TrajState read.
        with self._stop_lock():
            self._motion_open = False
            self._motion_unconfirmed = False
            self._command_fenced = False
            halted = generation != self._stop_generation or self.estop_epoch != epoch
        if halted:
            raise OutcomeUnknown("the MoveJ reply arrived after a status-port halt of this endpoint")
        self._require_zero(reply)
        return {"reply": reply, "accepted": True, "profile": profile,
                "joints": [float(item) for item in joints], "speed": float(speed)}

    @action(name="x-cap.ad-sdl.halt.v1", safe_state=True, risk="R2",
            description="On the status port, select robot 1 and halt. Confirms TrajState 0 or 1 only when every "
                        "MoveJ this endpoint wrote has been answered, and this halt has read state after that. "
                        "The reply follows the mailbox wait (Main.gpl:225). RapidDecel does not retire an "
                        "unanswered command",
            output={
                "traj_state": Field("integer", description="TrajState after halt: 0 halted or 1 idle"),
                "reply": Field("string", description="The state reply that showed 0 or 1"),
            })
    def halt(self):
        return self._status_halt()

    @estop(native="status-port selectRobot 1, halt, state", latency_ms=15000)
    def stop(self):
        """The runtime latches and cancels first. This stop does not wait for an in-flight MoveJ."""
        self._status_halt()

"""Fake backend of the PF400 TCP command server, stood in for ``tcp_driver.PF400``.

Public methods are only ``connect_robot`` and ``disconnect_robot`` (tcp_driver.py:103-119 and 125-127). The socket
those return is private. The driver sends one line and reads one reply on that socket; this module does not add a
``send_command`` or a ``stop_robot``, because the driver must not use the upstream robot-port halt.

The receive model follows Main.gpl. ``NewRobNum`` is applied at the start of a receive, before the bytes of that
receive are handled (Main.gpl:98-123). Every complete line already in that buffer is handled before the next
receive applies ``NewRobNum`` again (the Do loop at Main.gpl:145, the handler at 199-210). A status connection
starts on robot 0 (Main.gpl:59-63). One client per port (Main.gpl:88-90): a second ``connect_robot`` on a port
that still has a client raises ``ConnectionError``.

``halt`` on robot 1 sets that robot's trajectory state to 0 unless ``_stuck`` is set, and it releases a MoveJ that
is waiting. A halt that runs on robot 0 (select and halt in one buffer, or no select) does not. A blocking MoveJ
is a test flag, ``_block_moves``; the gate's default replies ``0`` immediately and leaves the state at 1, which
is a placeholder duration of zero, not a measured move. Ids, the default host and every trajectory value other
than the labels in Globals.gpl:118-129 are test data. Nothing here opens a network socket.
"""

from __future__ import annotations

import threading
import time


class _Sock:
    """One accepted client. ``send`` / ``recv`` / ``settimeout`` are the socket methods the driver uses."""

    def __init__(self, fake, port, robot, is_status):
        self._fake = fake
        self._port = port
        self._robot = robot
        self._is_status = is_status
        self._pending = None
        self._inbox = bytearray()
        self._queue = []
        self._timeout = None
        self._closed = False
        self._block_kind = None

    def settimeout(self, seconds):
        self._timeout = seconds

    def send(self, data):
        self.sendall(data)
        return len(data)

    def sendall(self, data):
        if self._closed:
            raise ConnectionError("socket is closed")
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("send requires bytes")
        self._inbox.extend(data)

    def recv(self, n):
        if self._closed:
            raise ConnectionError("socket is closed")
        pause = self._fake._recv_pause_s
        timeout = self._timeout if isinstance(self._timeout, (int, float)) and self._timeout > 0 else None
        if pause > 0:
            if timeout is not None and timeout < pause:
                time.sleep(timeout)
                raise TimeoutError("timed out waiting for a reply")
            time.sleep(pause)
        if n <= 0:
            return b""
        if not self._queue:
            self._fake._receive(self)
        if not self._queue:
            raise TimeoutError("timed out waiting for a reply")
        take = 1 if self._fake._fragment else n
        chunk = self._queue[0][:take]
        self._queue[0] = self._queue[0][take:]
        if not self._queue[0]:
            del self._queue[0]
        return bytes(chunk)

    def close(self):
        self._closed = True


class FakePF400:
    def __init__(self, host="operator-supplied.invalid", robot_port=10100, status_port=10000, **_options):
        self.host = host if isinstance(host, str) and host else "operator-supplied.invalid"
        robot = robot_port if isinstance(robot_port, int) and not isinstance(robot_port, bool) else 10100
        self._robot_port = robot
        self._status_port = status_port if isinstance(status_port, int) and not isinstance(status_port, bool) else 10000
        self.port = robot
        self._clients = {}
        self._lock = threading.Lock()
        self.traj = {0: 1, 1: 1}          # placeholder until a test or a halt changes robot 1
        self.exchanges = []               # {port, command, robot} in order
        self._move_event = threading.Event()
        self._move_waiting = threading.Event()
        self._mspeed_event = threading.Event()
        self._mspeed_waiting = threading.Event()
        self._release_move = threading.Event()
        self._block_moves = False
        self._block_mspeed = False
        self._defer_move = False
        self._recv_pause_s = 0.0
        self._fragment = False
        self._connect_pause_s = 0.0
        self._connect_pause_ports = None
        self._connect_entered = threading.Event()
        self._connects_finished = 0
        self._stuck = False
        self._status_down = False
        self._select_reply = None
        self._mspeed_reply = None
        self._move_reply = None

    @property
    def port(self):
        """The port the calling thread bound. ``connect_robot`` reads ``self.port`` (tcp_driver.py:117)."""
        ports = getattr(self, "_thread_ports", None)
        if ports:
            bound = ports.get(threading.get_ident())
            if bound is not None:
                return bound
        if hasattr(self, "_port_value"):
            return self._port_value
        return getattr(self, "_robot_port", 10100)

    @port.setter
    def port(self, value):
        self._port_value = value
        ports = getattr(self, "_thread_ports", None)
        if ports is None:
            ports = {}
            self._thread_ports = ports
        ports[threading.get_ident()] = value

    def connect_robot(self):
        # Snapshot before any pause. Another thread's assignment must not retarget this handshake.
        port = self.port
        try:
            port = int(port)
        except (TypeError, ValueError) as exc:
            self._connects_finished += 1
            raise ConnectionError("port is not an integer") from exc
        pause = self._connect_pause_s
        selected = self._connect_pause_ports
        if isinstance(selected, (set, frozenset, tuple, list)) and port not in selected:
            pause = 0
        try:
            if isinstance(pause, (int, float)) and not isinstance(pause, bool) and pause > 0:
                self._connect_entered.set()
                self._sleep_pause(pause)
            if port == self._status_port and self._status_down:
                raise ConnectionError("status port unreachable")
            with self._lock:
                if port in self._clients:
                    raise ConnectionError(f"port {port} already has a client")
                is_status = port == self._status_port
                robot = 0 if is_status else 1
                sock = _Sock(self, port, robot, is_status)
                self._clients[port] = sock
            return sock
        finally:
            self._connects_finished += 1

    def _sleep_pause(self, pause):
        """Sleep ``pause`` seconds, returning early when this thread's connect was cancelled."""
        cancel = getattr(threading.current_thread(), "pf400_connect_cancel", None)
        deadline = time.monotonic() + pause
        while True:
            if cancel is not None and cancel.is_set():
                raise TimeoutError("connect exceeded the deadline")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(0.02, remaining))

    def disconnect_robot(self, sock):
        sock.close()
        with self._lock:
            if self._clients.get(sock._port) is sock:
                del self._clients[sock._port]

    def _crlf(self, text):
        body = str(text).replace("\r", "").replace("\n", "")
        return body + "\r\n"

    def _defer_movej(self, sock):
        if not self._defer_move or sock._is_status:
            return False
        text = bytes(sock._inbox).decode("ascii", "replace")
        if "\n" not in text:
            return False
        first = text.split("\n", 1)[0].replace("\r", "").strip()
        verb = first.split(" ")[0] if first else ""
        return verb == "MoveJ"

    def _receive(self, sock):
        with self._lock:
            defer = self._defer_movej(sock)
        if defer:
            # The line stays in the inbox until the test releases it. halt does not release it:
            # Cmd.gpl:1840-1842 does not retire a command the robot thread has not handled.
            self._move_waiting.set()
            timeout = sock._timeout if isinstance(sock._timeout, (int, float)) and sock._timeout > 0 else 30.0
            if not self._release_move.wait(timeout):
                raise TimeoutError("deferred MoveJ was not released")
        with self._lock:
            if sock._pending is not None:
                sock._robot = sock._pending
                sock._pending = None
            text = bytes(sock._inbox).decode("ascii", "replace")
            if "\n" not in text:
                raise TimeoutError("timed out waiting for a command line")
            parts = text.split("\n")
            sock._inbox = bytearray(parts[-1].encode("ascii", "replace"))
            lines = parts[:-1]
            block = None
            block_kind = None
            for line in lines:
                reply = self._handle(sock, line)
                if reply is None:
                    block_kind = "mspeed" if sock._block_kind == "mspeed" else "move"
                    block = sock._timeout if sock._timeout and sock._timeout > 0 else 30.0
                    break
                sock._queue.append(reply.encode("ascii"))
        if block is None:
            return
        event = self._mspeed_event if block_kind == "mspeed" else self._move_event
        signaled = event.wait(block)
        if not signaled:
            raise TimeoutError("the command reply timed out")
        with self._lock:
            if block_kind == "mspeed":
                reply = "0" if self._mspeed_reply is None else self._mspeed_reply
            else:
                reply = "0" if self._move_reply is None else self._move_reply
            sock._queue.append(self._crlf(reply).encode("ascii"))

    def _handle(self, sock, raw):
        text = raw.replace("\r", "").strip()
        if not text:
            return "0\r\n"
        parts = text.split(" ")
        verb = parts[0]
        self.exchanges.append({"port": sock._port, "command": text, "robot": sock._robot})
        if verb == "selectRobot":
            return self._select(sock, parts[1] if len(parts) > 1 else None)
        if verb == "halt":
            if sock._robot == 1 and not self._stuck:
                self.traj[1] = 0
            if sock._robot == 1:
                self._move_event.set()
            return "0\r\n"
        if verb == "state":
            return f"0 {self.traj.get(sock._robot, 1)}\r\n"
        if verb == "mspeed":
            if self._block_mspeed and not sock._is_status:
                sock._block_kind = "mspeed"
                self._mspeed_waiting.set()
                return None
            if self._mspeed_reply is not None:
                return self._crlf(self._mspeed_reply)
            return "0\r\n"
        if verb == "MoveJ":
            if self._defer_move and not sock._is_status:
                self.traj[1] = 2
            if self._move_reply is not None:
                return self._crlf(self._move_reply)
            if self._block_moves and not sock._is_status:
                sock._block_kind = "move"
                self.traj[1] = 2
                self._move_event.clear()
                self._move_waiting.set()
                return None
            return "0\r\n"
        return "-2805\r\n"

    def _select(self, sock, arg):
        if self._select_reply is not None:
            return self._crlf(self._select_reply)
        if not sock._is_status:
            return "-2808\r\n"
        try:
            number = int(arg)
        except (TypeError, ValueError):
            return "-1000\r\n"
        if number == sock._robot:
            return "0\r\n"
        sock._pending = number
        return "0\r\n"

"""OpenMHS driver for gh.squad-lab/qcdrivers: the SQUAD Lab AD75019 crosspoint switch (``Muxi``).

Re-authored by Claude (claude-opus-5-5, a model and not a human) on 2026-11-05 as a decorated direct ``Driver``
(the user's decision of 2026-11-05: Claude authors, Claude Sonnet reviews).  The earlier DeepSeek package served the
same class through ``PythonObjectDriver``; its review found the stop real but the route unreported and the second
``*RST`` reply line left unread (blocked, G8 TCAP-003).  This package talks to the switch through the upstream's own
transport calls and reads every line the clone's firmware prints.

``Muxi`` (src/qcdrivers/squad/mux/mux.py:29) is a QCoDeS ``VisaInstrument`` whose ``send_command`` is one
``visa_handle.query`` (mux.py:85-86) and whose ``printconfig`` reads a further line with ``visa_handle.read``
(mux.py:170-171).  The driver uses exactly these two calls of the upstream handle, one exchange at a time under a
lock, and not ``send_command`` itself: that method's retry path calls ``self.visa.handle.clear()``, an attribute the
class never defines (mux.py:87-90), so a VISA timeout surfaces as an AttributeError and the command is not retried.

The firmware beside the class (helpers/firmware.ino) registers ``*IDN?``, ``*RST``, ``STAT?``, ``SWITCH16``,
``SWITCH32``, ``CLEAR`` and ``PRINT`` (firmware.ino:34-40) and answers with fixed lines:

* ``SWITCH32 x,y`` adds one route to the 32x32 route buffer, shifts the buffer out to the chips and prints
  ``Route added 32x32``, or prints ``Route skipped: disabled range`` for pins 12-15 and 28-31 (firmware.ino:71-88);
* ``STAT? x,y`` prints two labelled lines, ``16x16: `` and ``32x32: `` each followed by 1 or 0, read from the two
  route buffers (firmware.ino:90-106);
* ``*RST`` runs ``Clear`` (both route buffers to zero, prints ``Clear complete``), shifts both buffers out and
  prints ``Reset complete`` (firmware.ino:51-56, 108-112);
* ``*IDN?`` prints ``SQUAD, Arduino AD75019 Switch, 1.0, 1.0`` (firmware.ino:47-49).

So the connect action reports the route it sent and reads it back from the firmware's 32x32 route buffer, and the
e-stop sends ``*RST`` and succeeds only when the two lines that follow every line still owed by an earlier command
are ``Clear complete`` then ``Reset complete``.  Those owed lines are the ones the sketch prints for commands this
driver already wrote and has not finished reading: one for ``*IDN?`` (firmware.ino:48) and for ``SWITCH32``
(firmware.ino:78 or 84), two for ``STAT?`` (firmware.ino:98-102) and two for ``*RST`` (firmware.ino:111, then
firmware.ino:55).  Each handler prints its lines before it returns, and ``loop`` processes input one call at a time
(firmware.ino:43-44), so an earlier command's lines are printed before this ``*RST``'s pair.  The e-stop therefore
does not treat an unread pair from an earlier ``*RST`` as its own.  The connect and reset actions check for
cancellation under the line lock right before they write, so neither writes after the e-stop's ``*RST`` (the server
cancels operations before it stops).  Both read-backs are of the firmware's route buffers and of its completion
line, not a measurement of the analog switches: nothing in the clone senses the chips (the firmware only drives
SIN, SCLK and PCLK, firmware.ino:6-13).

The e-stop declares 5000 ms.  A connect with nothing still owed holds the line lock across ``SWITCH32`` and the
``STAT?`` read-back, so ``*RST`` does not fall between those two reads.  Each read is bounded by the 2000 ms VISA
timeout (mux.py:55).  If earlier commands still owe lines, the exchange checks again after the last of those lines,
before this command's own reply and before that read-back.  It yields when ``estop_epoch`` moves (``_engage_estop``
runs before ``stop`` takes this lock; a state read has no cancel context), when the operation is cancelled, or when
the prefix has held the line for 2000 ms.  The unread count stays owed, including this command's own reply when the
write has already gone out.  The e-stop's own ``*RST`` is not stopped this way.  It is the first query once the line
is free, so it is transmitted before its confirmation reads.  A line that has not arrived still ends that read at
2000 ms, the attempt fails closed and the unread debt stays for the retry.  A stop that takes longer than the
declared latency is reported unconfirmed; the runtime keeps the latch and retries it.
"""

from __future__ import annotations

import threading
import time

from mhs.driver import Cancelled, Driver, DriverFailed, Fact, Field, Limit, OutcomeUnknown, action, estop, read

SOURCE = "src/qcdrivers/squad/mux/mux.py"
FIRMWARE = "src/qcdrivers/squad/mux/helpers/firmware.ino"
CHIP = "src/qcdrivers/squad/mux/helpers/AD75019_24.cpp"
CHIP_H = "src/qcdrivers/squad/mux/helpers/AD75019_24.h"
CHIP16_H = "src/qcdrivers/squad/mux/helpers/AD75019.h"
CHIP16 = "src/qcdrivers/squad/mux/helpers/AD75019.cpp"

#: Reply lines of the clone's firmware (each printed with println; the VISA read strips the CRLF, mux.py:53).
IDENTITY_PREFIX = "SQUAD,"                        # firmware.ino:48
ROUTE_ADDED = "Route added 32x32"                 # firmware.ino:84
ROUTE_SKIPPED = "Route skipped: disabled range"   # firmware.ino:78
CLEAR_COMPLETE = "Clear complete"                 # firmware.ino:111
RESET_COMPLETE = "Reset complete"                 # firmware.ino:55
STATUS_16 = "16x16: "                             # firmware.ino:98
STATUS_32 = "32x32: "                             # firmware.ino:101
#: Lines the sketch prints for one command, before the handler returns.  SWITCH32 and STAT? are sent with two
#: parameters, so the one-line "Usage:" replies (firmware.ino:86, 104) are not the forms this driver writes.
IDN_LINES = 1                                     # firmware.ino:48
SWITCH32_LINES = 1                                # firmware.ino:78 or 84
STAT_LINES = 2                                    # firmware.ino:98-102
RST_LINES = 2                                     # firmware.ino:111, then firmware.ino:55
#: An ordinary drain of lines owed by earlier commands may hold the line for one VISA timeout (mux.py:55).
_ORDINARY_PREFIX_HOLD_S = 2.0


class _PrefixDrainYield(Exception):
    """The ordinary exchange stopped while lines owed by earlier commands were still unread."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason

_PIN_REASON = ("the usable AD75019 {axis} pins depend on the crate wiring: the firmware's 32x32 buffer takes pins "
               "0-31 (AD75019_24.h:115-116) and refuses 12-15 and 28-31 (firmware.ino:76-80), and the mux README "
               "says those pins are grounded (src/qcdrivers/squad/mux/README.md:9); which of the rest are cabled is "
               "deployment data")
PIN_X = Limit.operator_required(_PIN_REASON.format(axis="X (input)"))
PIN_Y = Limit.operator_required(_PIN_REASON.format(axis="Y (output)"))

_LOCK_GUARD = threading.Lock()


class SquadAd75019Mux(Driver):
    device_id = "squad-ad75019-mux"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "qcdrivers.squad.mux.mux:Muxi"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeMuxi"}
    vendor, model = "SQUAD Lab", "AD75019 crosspoint switch (Arduino firmware)"
    display_name = "SQUAD Lab AD75019 crosspoint switch (qcdrivers Muxi)"
    tags = ["qcodes", "visa", "crosspoint", "switch", "ad75019", "squad-lab"]
    safe_state = ("every crosspoint open in the firmware's route buffers and shifted out to the chips: *RST clears "
                  "both buffers, flushes them and prints 'Reset complete' (firmware.ino:51-56); the e-stop succeeds "
                  "only when the next two lines, after every line still owed by an earlier command, are "
                  "'Clear complete' then 'Reset complete'; the analog switches are not sensed")
    facts = [
        Fact("Muxi is a QCoDeS VisaInstrument that controls an AD75019 crosspoint switch over pyVISA",
             source="upstream_code", ref=f"{SOURCE}:29-35"),
        Fact("The constructor sets the baud rate (default 9600), newline write and CRLF read terminators and a "
             "2000 ms VISA timeout, calls connect_message and clears the VISA handle", source="upstream_code",
             ref=f"{SOURCE}:37-58"),
        Fact("send_command queries the VISA handle; on VisaIOError it calls self.visa.handle.clear(), an attribute "
             "path the class never defines, before sleeping 0.1 s and querying again", source="upstream_code",
             ref=f"{SOURCE}:85-92"),
        Fact("switch32 returns 'Route skipped: disabled range' without sending a command for x or y in 12-15 or "
             "28-31, and otherwise sends SWITCH32 x,y", source="upstream_code", ref=f"{SOURCE}:105-114"),
        Fact("status sends MUX:STATUS? PIN,OUT, a command the firmware does not register", source="upstream_code",
             ref=f"{SOURCE}:144-146"),
        Fact("reset sends *RST through send_command, which reads one reply line", source="upstream_code",
             ref=f"{SOURCE}:148-158"),
        Fact("printconfig sends PRINT and then reads a further line from the VISA handle", source="upstream_code",
             ref=f"{SOURCE}:170-172"),
        Fact("close closes the VISA handle", source="upstream_code", ref=f"{SOURCE}:225-235"),
        Fact("The firmware registers the commands *IDN?, *RST, STAT?, SWITCH16, SWITCH32, CLEAR and PRINT",
             source="upstream_code", ref=f"{FIRMWARE}:34-40"),
        Fact("*IDN? prints the line 'SQUAD, Arduino AD75019 Switch, 1.0, 1.0'", source="upstream_code",
             ref=f"{FIRMWARE}:47-49"),
        Fact("The *RST handler runs Clear, flushes the 16x16 and the 32x32 matrices and then prints 'Reset "
             "complete'", source="upstream_code", ref=f"{FIRMWARE}:51-56"),
        Fact("Clear sets both route buffers to zero and prints 'Clear complete'", source="upstream_code",
             ref=f"{FIRMWARE}:108-112"),
        Fact("SWITCH32 prints 'Route skipped: disabled range' for x or y in 12-15 or 28-31; otherwise it adds the "
             "route, flushes the 32x32 matrix and prints 'Route added 32x32'", source="upstream_code",
             ref=f"{FIRMWARE}:71-88"),
        Fact("STAT? x,y prints '16x16: ' and '32x32: ' each followed by 1 or 0 from isRouted of the two route "
             "buffers, or 'Usage: STAT? x,y' without two parameters", source="upstream_code",
             ref=f"{FIRMWARE}:90-106"),
        Fact("The two matrix objects share one PCLK, SCLK and SIN pin set", source="upstream_code",
             ref=f"{FIRMWARE}:6-13"),
        Fact("AD75019_24.flush shifts the route buffer out bit by bit and then pulses PCLK; clear sets every word of "
             "the buffer to 0", source="upstream_code", ref=f"{CHIP}:95-150"),
        Fact("isRouted reads the bit of the configuration buffer, not the chip", source="upstream_code",
             ref=f"{CHIP}:91-93"),
        Fact("The 32x32 matrix class's X and Y pin mappings have 32 entries", source="upstream_code",
             ref=f"{CHIP_H}:115-116"),
        Fact("The 16x16 matrix class's X and Y pin mappings have 16 entries", source="upstream_code",
             ref=f"{CHIP16_H}:124-125"),
        Fact("The 16x16 matrix class's isRouted indexes its X and Y pin mappings with the x and y it is given",
             source="upstream_code", ref=f"{CHIP16}:79-82"),
        Fact("STAT? passes the x and y it parses to isRouted of both the 16x16 and the 32x32 matrix",
             source="upstream_code", ref=f"{FIRMWARE}:90-96"),
        Fact("Four AD75019 chips are daisy-chained for the 24x24 array, each with X12-X15 and Y12-Y15 disabled and "
             "grounded", source="vendor_doc", ref="src/qcdrivers/squad/mux/README.md:8-9"),
    ]

    # -- one exchange of lines, never interleaved with another ---------------------------------------------------------
    def _line_lock(self) -> threading.RLock:
        """One exchange at a time: a connect holds it across SWITCH32 and its STAT? read-back; the e-stop takes it."""
        lock = getattr(self, "_mux_line_lock", None)
        if lock is None:
            with _LOCK_GUARD:
                lock = getattr(self, "_mux_line_lock", None)
                if lock is None:
                    lock = threading.RLock()
                    self._mux_line_lock = lock
        return lock

    def _lines_owed(self) -> int:
        """Reply lines commands already written will still print, and this driver has not read."""
        return int(getattr(self, "_mux_lines_owed", 0))

    def _prefix_hold_s(self) -> float:
        """How long an ordinary prefix may keep the line.  A test may set ``_ordinary_prefix_hold_s``."""
        return float(getattr(self, "_ordinary_prefix_hold_s", _ORDINARY_PREFIX_HOLD_S))

    def _yield_prefix_drain(self, started: float, epoch: int) -> None:
        """Stop reading owed lines so ``*RST`` can take the line.  The caller still holds the lock.

        ``check_cancelled`` sees an invoke the server cancelled.  A ``client.read`` has no cancel context
        (``server._read_state``), so it does not.  ``estop_epoch`` moves in ``_engage_estop`` before ``stop`` waits
        for this lock.  The hold is one VISA timeout, so a run of slow successful reads ends even when neither has
        fired yet: the next stop then waits for at most the read already in flight.
        """
        self.check_cancelled()
        if self.estop_epoch != epoch:
            raise _PrefixDrainYield("estop")
        if time.monotonic() - started >= self._prefix_hold_s():
            raise _PrefixDrainYield("hold")

    def _write_and_read(self, command: str, total: int, *, preemptable: bool = False, own: int = 0) -> list[str]:
        """Write ``command`` and read ``total`` lines: the debt from earlier commands, then this command's lines.

        The debt is counted as the write is attempted.  ``query`` is the upstream's write-then-read (mux.py:86); a
        raise may mean the write reached the firmware and the read timed out, the same assumption as an unknown
        outcome, so the unread lines stay owed.  Counting a write that never left the host makes a later
        confirmation fail closed.  A preemptable caller stops between owed lines, and again once the last owed line
        has been taken, before this command's own lines.  That is when the stop has begun, the operation is
        cancelled, or the prefix hold is used up.  Lines of this command that have already started are read: they are
        one or two, each bounded by the VISA timeout.  Stopping before the write leaves the debt unchanged.
        Stopping after it leaves this command's unread lines owed.  The caller holds the line lock.  The e-stop
        passes ``preemptable=False``: its ``*RST`` is the first query, and its confirmation is the pair this stop is
        for.
        """
        handle = self.native.visa_handle
        taken: list[str] = []
        wrote = False
        prefix = total - own
        started = time.monotonic()
        epoch = self.estop_epoch
        try:
            if preemptable and prefix > 0:
                self._yield_prefix_drain(started, epoch)
            wrote = True
            taken.append(str(handle.query(command)).strip())
            while len(taken) < total:
                # ``<= prefix`` is the line after the last owed reply, before this command's own reply.  ``<``
                # alone lets a connect with one owed line keep the lock for that reply and for STAT?.
                if preemptable and prefix > 0 and len(taken) <= prefix:
                    self._yield_prefix_drain(started, epoch)
                taken.append(str(handle.read()).strip())
            return taken
        finally:
            if wrote:
                self._mux_lines_owed = total - len(taken)

    def _exchange(self, command: str, lines: int, *, effect: bool, guard: bool = False) -> list[str]:
        """Send ``command`` and return its own ``lines`` reply lines, after any lines still owed.

        A transport error after the command may have reached the firmware: an effectful command then ends unknown,
        a query fails.  With ``guard`` the operation's cancellation is checked under the line lock, which the e-stop
        also takes: the e-stop cancels operations before it stops (the server's order), so a cancelled command is
        never sent after the e-stop's *RST, and one sent before it is cleared by it.  The owed prefix is read under
        the same lock and yields on cancellation, on ``estop_epoch``, or after one VISA timeout, so a slow run of
        successful reads cannot hold ``*RST`` past the declared latency.  Lines not yet read stay owed.  The line
        lock does not serve waiters in order; a read that takes the line first updates this same debt before it
        returns.  Yielding raises out of this lock, including a connect's outer hold of it.
        """
        with self._line_lock():
            if guard:
                self.check_cancelled()
            prior = self._lines_owed()
            try:
                taken = self._write_and_read(command, prior + lines, preemptable=True, own=lines)
            except _PrefixDrainYield as exc:
                owed = self._lines_owed()
                if exc.reason == "hold":
                    message = (f"{command!r}: stopped reading lines still owed by earlier commands after one VISA "
                               f"timeout ({owed} still unread)")
                    if effect:
                        raise OutcomeUnknown(f"{message}; the command may have been written") from exc
                    raise DriverFailed("MHS.DEVICE.FAULTED", message) from exc
                raise Cancelled("the owed-line drain yielded the line so the e-stop can send *RST") from exc
            except (Cancelled, DriverFailed):
                raise
            except Exception as exc:  # noqa: BLE001 - every transport error is reported, never swallowed
                if effect:
                    raise OutcomeUnknown(f"{command!r}: the exchange failed after the command was written "
                                         f"({type(exc).__name__}); the firmware may have acted on it") from exc
                raise DriverFailed("MHS.DEVICE.FAULTED", f"{command!r}: the exchange failed "
                                   f"({type(exc).__name__})") from exc
        return taken[prior:]

    def _read_status(self, x: int, y: int, *, effect: bool) -> int:
        """STAT? x,y: the firmware's two labelled lines; returns the 32x32 bit (the 16x16 line is read and checked)."""
        first, second = self._exchange(f"STAT? {x},{y}", STAT_LINES, effect=effect)
        if not first.startswith(STATUS_16) or not second.startswith(STATUS_32):
            message = f"STAT? {x},{y}: unexpected reply lines {first!r}, {second!r}"
            if effect:
                raise OutcomeUnknown(message)
            raise DriverFailed("MHS.DEVICE.FAULTED", message)
        value = second[len(STATUS_32):]
        if value not in ("0", "1"):
            raise DriverFailed("MHS.DEVICE.FAULTED", f"STAT? {x},{y}: the 32x32 line is {second!r}")
        return int(value)

    def _reset_matrix(self, *, guard: bool = False) -> list[str]:
        """*RST, then this command's own 'Clear complete' and 'Reset complete'.

        Lines still owed by earlier commands are read first and are not this confirmation: the sketch prints them
        before this handler runs (firmware.ino:43-44, 51-56, 108-112).  A pair in that owed prefix is an earlier
        *RST.  With ``guard`` (the reset action) cancellation is checked under the line lock first, as for a
        connect; the e-stop never passes it.  The debt lives on this driver instance, so releasing the latch does
        not forget a *RST whose reads timed out.
        """
        with self._line_lock():
            if guard:
                self.check_cancelled()
            prior = self._lines_owed()
            try:
                # Not preemptable.  estop_epoch has already moved, and this *RST is the stop: the first query
                # transmits it, then these reads are its confirmation.  Cutting them off would drop that pair.
                taken = self._write_and_read("*RST", prior + RST_LINES, preemptable=False, own=RST_LINES)
            except (Cancelled, DriverFailed):
                raise
            except Exception as exc:  # noqa: BLE001 - an unconfirmed *RST is a failed stop, never a success
                raise DriverFailed("MHS.DEVICE.FAULTED", f"*RST: the reply was not read ({type(exc).__name__}; "
                                   f"{prior} line(s) were still owed and {self._lines_owed()} still are)") from exc
            own = taken[prior:]
            if own != [CLEAR_COMPLETE, RESET_COMPLETE]:
                raise DriverFailed("MHS.DEVICE.FAULTED",
                                   f"*RST: the two lines after {prior} line(s) still owed by earlier commands were "
                                   f"{own!r}, not 'Clear complete' then 'Reset complete' (firmware.ino:51-56, 111); "
                                   "not confirmed")
        return own

    # -- reads -----------------------------------------------------------------------------------------------------
    @read("identity", type="string",
          description="The firmware's identity line, read with *IDN? (firmware.ino:47-49)")
    def identity(self):
        (line,) = self._exchange("*IDN?", IDN_LINES, effect=False)
        if not line.startswith(IDENTITY_PREFIX):
            raise DriverFailed("MHS.DEVICE.FAULTED", f"*IDN?: unexpected reply {line!r} (a line left over from an "
                               "earlier exchange, or another device)")
        return line

    # -- actions ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.squad-lab.mux_connect.v1", risk="R1",
            description="Close one crosspoint with SWITCH32 x,y and read it back with STAT? x,y",
            input={"x": Field("integer", unit="1", description="X (input) pin, as cabled for this crate",
                              limit=PIN_X),
                   "y": Field("integer", unit="1", description="Y (output) pin, as cabled for this crate",
                              limit=PIN_Y)},
            output={"x": Field("integer", description="X pin of the route sent"),
                    "y": Field("integer", description="Y pin of the route sent"),
                    "reply": Field("string", description="The firmware's reply line to SWITCH32"),
                    "routed": Field("boolean", description="The 32x32 route-buffer bit STAT? read back after the "
                                                           "command (the firmware's buffer, not a measurement)")})
    def connect(self, x, y):
        with self._line_lock():   # held across SWITCH32 and its read-back when nothing is owed and no stop has begun
            epoch = self.estop_epoch
            (reply,) = self._exchange(f"SWITCH32 {x},{y}", SWITCH32_LINES, effect=True, guard=True)
            if reply == ROUTE_SKIPPED:
                raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", f"the firmware refused SWITCH32 {x},{y}: "
                                   f"{reply!r} (pins 12-15 and 28-31, firmware.ino:76-80); nothing changed")
            if reply != ROUTE_ADDED:
                raise OutcomeUnknown(f"SWITCH32 {x},{y}: unexpected reply {reply!r}; the route may have been added")
            # Do not start STAT? once the stop has begun.  The route this SWITCH32 added is cleared by *RST.
            self.check_cancelled()
            if self.estop_epoch != epoch:
                raise Cancelled("the connect read-back yielded the line so the e-stop can send *RST")
            routed = self._read_status(x, y, effect=True)
        if routed != 1:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"SWITCH32 {x},{y} answered {reply!r} but STAT? reads the "
                               "32x32 route bit as 0")
        return {"x": x, "y": y, "reply": reply, "routed": True}

    @action(name="x-cap.squad-lab.mux_status.v1", risk="R0",
            description="Read one crosspoint of the firmware's 32x32 route buffer with STAT? x,y",
            input={"x": Field("integer", unit="1", description="X (input) pin, as cabled for this crate",
                              limit=PIN_X),
                   "y": Field("integer", unit="1", description="Y (output) pin, as cabled for this crate",
                              limit=PIN_Y)},
            output={"x": Field("integer", description="X pin read"),
                    "y": Field("integer", description="Y pin read"),
                    "routed": Field("boolean", description="The 32x32 route-buffer bit (the firmware's buffer, not a "
                                                           "measurement)")})
    def status(self, x, y):
        return {"x": x, "y": y, "routed": self._read_status(x, y, effect=False) == 1}

    @action(name="x-cap.squad-lab.mux_reset.v1", risk="R1",
            description="Open every crosspoint with *RST and read this command's two reply lines",
            output={"lines": Field("array", items=Field("string", description="A reply line"),
                                   description="This *RST's 'Clear complete' and 'Reset complete'; lines still "
                                               "owed by an earlier command are not included")})
    def reset_matrix(self):
        return {"lines": self._reset_matrix(guard=True)}

    # -- safety ----------------------------------------------------------------------------------------------------
    @estop(native="*RST", latency_ms=5000)
    def stop(self):
        """The runtime latches first; then *RST, confirmed only by this command's own reply pair."""
        self._reset_matrix()

    def teardown(self):
        self.native.close()   # mux.py:225-235

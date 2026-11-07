"""Hardware backend for the Newport SMC100 over RS-232.

The upstream clone is Python 2, so this module is a Python 3 port of the same wire protocol rather than an import
of ``smc100.py``.  It opens pyserial lazily (only the hardware view calls :func:`connect`), sends the controller ID,
the command word and the argument followed by CR LF, validates the ID-prefixed reply, and keeps the upstream
method names so the driver can use one interface.  The acceptance gate never imports this module and no hardware
was attached.
"""

import time

MAX_WAIT_TIME_SEC = 12
COMMAND_WAIT_TIME_SEC = 0.06

STATE_NOT_REFERENCED_FROM_RESET = "0A"
STATE_NOT_REFERENCED_FROM_CONFIGURATION = "0C"
STATE_READY_FROM_HOMING = "32"
STATE_READY_FROM_MOVING = "33"
STATE_CONFIGURATION = "14"

STATE_DISABLE_FROM_READY = "3C"
STATE_DISABLE_FROM_MOVING = "3D"
STATE_DISABLE_FROM_JOGGING = "3E"

_DISABLED_STATES = (STATE_DISABLE_FROM_READY, STATE_DISABLE_FROM_MOVING, STATE_DISABLE_FROM_JOGGING)


class SMC100ReadTimeOutException(Exception):
    pass


class SMC100WaitTimedOutException(Exception):
    pass


class SMC100DisabledStateException(Exception):
    pass


class SMC100InvalidResponseException(Exception):
    pass


class SMC100:
    """Python 3 port of ``smc100:SMC100`` for the hardware view."""

    def __init__(self, smcID, port, *, timeout_s=0.050, silent=True, sleepfunc=None):
        import serial

        self._smcID = str(smcID)
        self._silent = bool(silent)
        self._sleepfunc = sleepfunc or time.sleep
        self._last_sendcmd_time = 0.0
        self._port = serial.Serial(
            port=port,
            baudrate=57600,
            bytesize=8,
            stopbits=1,
            parity="N",
            xonxoff=True,
            timeout=float(timeout_s),
        )

    def reset_and_configure(self):
        self.sendcmd("RS")
        self.sendcmd("RS")
        self._sleepfunc(3)
        self.wait_states(STATE_NOT_REFERENCED_FROM_RESET, ignore_disabled_states=True)
        self.sendcmd("ID", "?", expect_response=True)
        self.sendcmd("PW", 1)
        self.wait_states(STATE_CONFIGURATION)
        self.sendcmd("ZX", 1)
        self.sendcmd("ZX", 2)
        self.sendcmd("PW", 0)
        self.wait_states(STATE_NOT_REFERENCED_FROM_CONFIGURATION)

    def home(self, waitStop=True):
        self.sendcmd("OR")
        if waitStop:
            state = self.wait_states((STATE_READY_FROM_HOMING, STATE_READY_FROM_MOVING))
            if state == STATE_READY_FROM_MOVING:
                self.move_absolute_um(0, waitStop=True)
        else:
            self.move_absolute_um(0, waitStop=False)

    def stop(self):
        self.sendcmd("ST")

    def get_status(self, silent=False):
        response = self.sendcmd("TS", "?", expect_response=True, retry=10)
        errors = int(response[0:4], 16)
        state = response[4:]
        if len(state) != 2:
            raise SMC100InvalidResponseException("TS?", response)
        return errors, state

    def get_position_mm(self):
        return float(self.sendcmd("TP", "?", expect_response=True, retry=10))

    def get_position_um(self):
        return int(self.get_position_mm() * 1000)

    def move_relative_mm(self, dist_mm, waitStop=True):
        self.sendcmd("PR", dist_mm)
        if waitStop:
            self.wait_states((STATE_READY_FROM_MOVING, STATE_READY_FROM_HOMING))

    def move_relative_um(self, dist_um, **kwargs):
        self.move_relative_mm(int(dist_um) / 1000, **kwargs)

    def move_absolute_mm(self, position_mm, waitStop=True):
        self.sendcmd("PA", position_mm)
        if waitStop:
            self.wait_states((STATE_READY_FROM_MOVING, STATE_READY_FROM_HOMING))

    def move_absolute_um(self, position_um, **kwargs):
        from math import floor

        return self.move_absolute_mm(floor(position_um) / 1000, **kwargs)

    def wait_states(self, targetstates, ignore_disabled_states=False):
        targets = (targetstates,) if isinstance(targetstates, str) else tuple(targetstates)
        starttime = time.monotonic()
        while True:
            if time.monotonic() - starttime > MAX_WAIT_TIME_SEC:
                raise SMC100WaitTimedOutException("Wait timed out")
            try:
                state = self.get_status()[1]
            except SMC100ReadTimeOutException:
                self._sleepfunc(1)
                continue
            if state in targets:
                return state
            if not ignore_disabled_states and state in _DISABLED_STATES:
                raise SMC100DisabledStateException("Disabled state encountered: " + state)

    def sendcmd(self, command, argument=None, expect_response=False, retry=False):
        if not command or command.endswith("?"):
            raise ValueError("the '?' belongs in the argument")
        if self._port is None:
            return None

        argument = "" if argument is None else str(argument)
        prefix = self._smcID + command
        tosend = prefix + argument

        if command in ("PR", "OR"):
            retry = False

        while self._port is not None:
            if expect_response:
                self._port.reset_input_buffer()
            self._port.reset_output_buffer()
            self._port.write(tosend.encode("ascii"))
            self._port.write(b"\r\n")
            self._port.flush()

            if expect_response:
                try:
                    response = self._readline()
                except SMC100ReadTimeOutException:
                    if not retry or retry <= 0:
                        raise
                    if isinstance(retry, int):
                        retry -= 1
                    continue
                if response.startswith(prefix):
                    return response[len(prefix):]
                if not retry or retry <= 0:
                    raise SMC100InvalidResponseException(command, response)
                if isinstance(retry, int):
                    retry -= 1
                continue

            now = time.monotonic()
            delay = COMMAND_WAIT_TIME_SEC - (now - self._last_sendcmd_time)
            if delay > 0:
                self._sleepfunc(delay)
            self._last_sendcmd_time = now
            return None
        return None

    def _readline(self):
        line = []
        while True:
            char = self._port.read()
            if not char:
                raise SMC100ReadTimeOutException("Read timed out")
            text = char.decode("ascii", "replace")
            if text == "\r":
                continue
            if text == "\n":
                return "".join(line)
            if 32 < ord(text) < 127:
                line.append(text)
            else:
                raise SMC100InvalidResponseException("read", repr(text))

    def close(self):
        port, self._port = self._port, None
        if port is not None:
            port.close()


def connect(**options):
    """Open the RS-232 port and return the controller (hardware view only)."""

    allowed = {key: value for key, value in options.items()
               if key in ("smcID", "port", "timeout_s", "silent", "sleepfunc")}
    return SMC100(**allowed)

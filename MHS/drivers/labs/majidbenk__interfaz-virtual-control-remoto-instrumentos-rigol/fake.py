"""Fake SCPI transport of the RIGOL DP832A driver.

The upstream clone ships no simulator, mock or transcript (the card's ``mock_strategy.preferred`` is ``transcript``
but the repository contains only Tkinter code and an image of extra commands), so this class is an in-memory stand-in
for the text transport of the supply.  It accepts the same command shapes the driver sends and keeps the state the
driver reads back.

Gate G7 (transport mode) checks the command mnemonics the driver sends against the clone, not this class.  Every
state value and reply below is test data, not a statement about a device; each is marked ``# placeholder``.  The
measured voltage, current and power are derived from the set points regardless of the output state: this is the
stand-in's simplification (the real DP832A reports what the load draws), and it exists so a write has an observable
state effect in the conformance run.  Nothing here talks to a device.

The channel numbers are the ones the upstream UI uses (``intefaz_FuenteContinua_v2.py:398``), not measured values.
"""

_CHANNELS = ("1", "2", "3")   # channel identifiers sent by the upstream code (line 398)


class FakeRigolDP832A:
    def __init__(self, **_options):
        self.written = []
        self._pending = []
        self._selected = "1"
        # every value below is placeholder test data, not a fact about a device
        self._voltage = {channel: 0.0 for channel in _CHANNELS}           # placeholder
        self._current = {channel: 0.1 for channel in _CHANNELS}           # placeholder
        self._voltage_protection = {"1": 33.0, "2": 33.0, "3": 5.5}       # placeholder
        self._current_protection = {channel: 3.3 for channel in _CHANNELS}  # placeholder
        self._output = {channel: False for channel in _CHANNELS}          # placeholder
        self._identity = "RIGOL,DP832A,FAKE0001,0.0"                     # placeholder

    # -- transport surface ---------------------------------------------------------------------------------------
    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        for part in line.split(";"):
            command = part.strip()
            if not command:
                continue
            self._apply(command)

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        return self._pending.pop(0)

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        pass

    # -- command handling ----------------------------------------------------------------------------------------
    def _apply(self, command):
        if command == "*IDN?":
            self._pending.append(self._identity)
        elif command.startswith(":INST:NSEL "):
            self._selected = command.split(None, 1)[1].strip()
        elif command.startswith(":MEAS:VOLT? "):
            self._pending.append(self._measurement(self._voltage, command))
        elif command.startswith(":MEAS:CURR? "):
            self._pending.append(self._measurement(self._current, command))
        elif command.startswith(":MEAS:POWE? "):
            channel = self._channel(command.split()[-1])
            self._pending.append(repr(self._voltage[channel] * self._current[channel]))
        elif command.startswith(":VOLT:PROT "):
            self._voltage_protection[self._selected] = float(command.split(None, 1)[1])
        elif command.startswith(":CURR:PROT "):
            self._current_protection[self._selected] = float(command.split(None, 1)[1])
        elif command.startswith(":VOLT "):
            self._voltage[self._selected] = float(command.split(None, 1)[1])
        elif command.startswith(":CURR "):
            self._current[self._selected] = float(command.split(None, 1)[1])
        elif command.startswith(":OUTP "):
            channel, _, state = command.split(None, 1)[1].partition(",")
            self._output[self._channel(channel)] = state.strip().upper() == "ON"
        else:
            raise ValueError(f"the fake transport does not know {command!r}")

    @staticmethod
    def _channel(token):
        """``CH1`` -> ``1`` (the key of the state dictionaries)."""
        return str(token).strip().upper().removeprefix("CH")

    @classmethod
    def _measurement(cls, values, command):
        return repr(values[cls._channel(command.split()[-1])])

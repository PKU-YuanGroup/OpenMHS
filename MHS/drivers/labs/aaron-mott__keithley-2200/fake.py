"""Fake SCPI transport of the Keithley 2200 series driver: an in-memory bench supply.

The upstream clone ships no simulator, no tests and no captured session, so this is an in-memory stand-in, not a
recording.  It holds the state the driver reads and applies the effect of the writes the driver sends; every start
value and every modelled reading is test data, marked ``# placeholder``, and nothing here states a device fact or a
device limit.  A fresh transport starts with the output disabled and zero set points.

Gate G7 (transport mode) checks the command mnemonics the driver sends against the clone, not this class.  The
methods here are the transport surface the SCPI bridge calls (``write``, ``read``, ``query``, ``close``); no
upstream class is imported or reimplemented.
"""


class FakeKeithley2200:
    def __init__(self, **_options):
        self.written = []
        self._pending = []
        self.identity = "Keithley Instruments,2220-30-1,0000000,1.0"  # placeholder identity
        self.voltage_setpoint = 0.0                                   # placeholder start value
        self.current_setpoint = 0.0                                   # placeholder start value
        self.overvoltage_protection = 0.0                             # placeholder start value
        self.output_on = False                                        # placeholder start value
        self.overvoltage_enabled = False                              # placeholder start value
        self.load_resistance = 100.0                                  # placeholder modelled load in ohms

    # -- transport ------------------------------------------------------------------------------------------------
    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        for part in line.split(";"):
            self._command(part.strip())

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        return self._pending.pop(0)

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        pass

    # -- instrument model ------------------------------------------------------------------------------------------
    def _command(self, command):
        if command == "*IDN?":
            self._pending.append(self.identity)
        elif command == "*CLS":
            return
        elif command == "VOLT?":
            self._pending.append(f"{self.voltage_setpoint:.9g}")
        elif command == "CURR?":
            self._pending.append(f"{self.current_setpoint:.9g}")
        elif command == "OUTP?":
            self._pending.append("ON" if self.output_on else "OFF")
        elif command == "VOLT:PROT?":
            self._pending.append(f"{self.overvoltage_protection:.9g}")
        elif command == "VOLT:PROT:STAT?":
            self._pending.append("ON" if self.overvoltage_enabled else "OFF")
        elif command == "MEAS:VOLT?":
            self._pending.append(f"{self._measured_voltage():.9g}")
        elif command == "MEAS:CURR?":
            self._pending.append(f"{self._measured_current():.9g}")
        elif command == "FETCh:POW?":
            self._pending.append(f"{self._measured_voltage() * self._measured_current():.9g}")
        elif command.startswith("VOLT:PROT:STAT "):
            self.overvoltage_enabled = self._bool(command.split(None, 1)[1])
        elif command.startswith("VOLT:PROT "):
            self.overvoltage_protection = float(command.split(None, 1)[1])
        elif command.startswith("VOLT "):
            self.voltage_setpoint = float(command.split(None, 1)[1])
        elif command.startswith("CURR "):
            self.current_setpoint = float(command.split(None, 1)[1])
        elif command.startswith("OUTP "):
            self.output_on = self._bool(command.split(None, 1)[1])
        elif command == "OUTP:PROT:CLE":
            return
        else:
            raise ValueError(f"the fake does not know the command {command!r}")

    @staticmethod
    def _bool(token):
        text = str(token).strip().upper()
        if text in ("ON", "1", "TRUE"):
            return True
        if text in ("OFF", "0", "FALSE"):
            return False
        raise ValueError(f"the fake does not know the boolean {token!r}")

    def _measured_voltage(self):
        """A placeholder reading: the set point while the output is on, otherwise zero."""
        return self.voltage_setpoint if self.output_on else 0.0  # placeholder off reading

    def _measured_current(self):
        """A placeholder reading: the current set point capped by the modelled resistive load."""
        if not self.output_on:
            return 0.0  # placeholder off reading
        return min(self.current_setpoint, self.voltage_setpoint / self.load_resistance)

"""Fake SCPI transport of the Keithley 2400 driver: an in-memory source-measure unit.

The driver sends either a single query/write line or, for a measurement action, one semicolon-separated line that
configures the function and ends with ``READ?``.  This fake applies every part of a line in order and queues one reply
for each query, so any order of requests works on a fresh transport.  The initial state, the identity and every
reading below are test data (marked ``placeholder``), not facts from the clone or a manual; nothing here talks to an
instrument.  Gate G7 (transport mode) checks the command mnemonics against the clone, not this class.
"""


class FakeKeithley2400:
    def __init__(self, **_options):
        self.written = []
        self._pending = []
        self.source_voltage = 0.0           # placeholder: the safe source-voltage state the clone writes with 0
        self.source_current = 0.0           # placeholder
        self.output_on = False              # placeholder: a fresh fake starts with the output disabled
        self.source_function = "VOLT"       # placeholder
        self.measure_function = "CURR"      # placeholder
        self.element = "CURR"               # placeholder
        self.arm_count = 1                  # placeholder
        self.trigger_count = 1              # placeholder
        self.trigger_delay = 0.0            # placeholder
        self.fake_resistance = 1000.0       # placeholder: the modelled load resistance for the current reading

    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        for part in line.split(";"):
            self._command(part.strip())

    def _command(self, command):
        if command == "*IDN?":
            self._pending.append("KEITHLEY INSTRUMENTS INC.,MODEL 2400,0000000,1.0")  # placeholder identity
        elif command == "SOUR:VOLT?":
            self._pending.append(f"{self.source_voltage:.6f}")  # placeholder formatting
        elif command == "SOUR:CURR?":
            self._pending.append(f"{self.source_current:.6f}")  # placeholder formatting
        elif command == "OUTP?":
            self._pending.append("ON" if self.output_on else "OFF")
        elif command == "TRIG:DEL?":
            self._pending.append(f"{self.trigger_delay:.6f}")  # placeholder formatting
        elif command == "READ?":
            self._pending.append(f"{self._reading():.9g}")  # placeholder reading
        elif command == "*OPC?":
            self._pending.append("1")
        elif command == "INIT":
            return
        elif command.startswith("SOUR:FUNC "):
            self.source_function = command.split(" ", 1)[1].strip()
        elif command.startswith("SOUR:VOLT "):
            self.source_voltage = float(command.split(" ", 1)[1])
        elif command.startswith("SOUR:CURR "):
            self.source_current = float(command.split(" ", 1)[1])
        elif command.startswith("CONF:"):
            self.measure_function = command.split(":", 1)[1].strip()
        elif command.startswith("FORM:ELEM "):
            self.element = command.split(" ", 1)[1].strip()
        elif command.startswith("ARM:COUN "):
            self.arm_count = int(float(command.split(" ", 1)[1]))
        elif command.startswith("TRIG:COUN "):
            self.trigger_count = int(float(command.split(" ", 1)[1]))
        elif command.startswith("TRIG:DEL "):
            self.trigger_delay = float(command.split(" ", 1)[1])
        elif command in ("OUTP ON", "OUTP OFF"):
            self.output_on = command.endswith("ON")
        else:
            raise ValueError(f"the fake does not know the command {command!r}")

    def _reading(self):
        """A placeholder reading in the unit of the selected function."""
        if self.measure_function == "CURR":
            return self.source_voltage / self.fake_resistance  # placeholder Ohm's law on the modelled load
        if self.measure_function == "VOLT":
            return self.source_current * self.fake_resistance  # placeholder Ohm's law on the modelled load
        return self.fake_resistance  # placeholder resistance

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        return self._pending.pop(0)

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        pass

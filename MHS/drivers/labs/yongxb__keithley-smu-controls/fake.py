"""Fake text transport of the Keithley 2450 driver: an in-memory source-measure unit.

The driver sends either one TSP assignment or a semicolon-separated query line that selects the measurement function
and ends with ``print(...)``.  This fake applies every part of a line in order and queues one reply for each
``print(...)``, so any request order works on a fresh transport.  The identity, the initial state, the load
resistance and every reading below are test data (marked ``placeholder``), not facts from the clone or a manual;
nothing here talks to an instrument.  Gate G7 (transport mode) checks the command mnemonics against the clone, not
this class.
"""


class FakeKeithley2450:
    def __init__(self, **_options):
        self.written = []
        self._pending = []
        self.source_level = 0.0             # placeholder: the safe source level the clone writes with 0
        self.compliance_voltage = 0.0       # placeholder: a fresh fake has no compliance set
        self.output_on = False              # placeholder: a fresh fake starts with the output disabled
        self.source_function = "CURRENT"    # placeholder: the clone selects current source mode
        self.measure_function = "VOLTAGE"   # placeholder: the runtime reads voltage first
        self.load_resistance = 1000.0       # placeholder: the modelled load for the voltage reading

    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        for part in line.split(";"):
            self._command(part.strip())

    def _command(self, command):
        if command == "*IDN?":
            self._pending.append("KEITHLEY INSTRUMENTS,INC.,MODEL 2450,0000000,1.0")  # placeholder identity
        elif command == "print(smu.source.level)":
            self._pending.append(f"{self.source_level:.9g}")  # placeholder formatting
        elif command == "print(smu.source.vlimit.level)":
            self._pending.append(f"{self.compliance_voltage:.9g}")  # placeholder formatting
        elif command == "print(smu.source.output)":
            self._pending.append("smu.ON" if self.output_on else "smu.OFF")
        elif command == "print(smu.measure.read())":
            self._pending.append(f"{self._reading():.9g}")  # placeholder reading
        elif command == "smu.measure.func = smu.FUNC_DC_VOLTAGE":
            self.measure_function = "VOLTAGE"
        elif command == "smu.measure.func = smu.FUNC_DC_CURRENT":
            self.measure_function = "CURRENT"
        elif command == "smu.source.func = smu.FUNC_DC_CURRENT":
            self.source_function = "CURRENT"
        elif command == "smu.source.func = smu.FUNC_DC_VOLTAGE":
            self.source_function = "VOLTAGE"
        elif command.startswith("smu.source.level = "):
            self.source_level = float(command.split("=", 1)[1])
        elif command.startswith("smu.source.vlimit.level = "):
            self.compliance_voltage = float(command.split("=", 1)[1])
        elif command in ("smu.source.output = smu.ON", "smu.source.output = smu.OFF"):
            self.output_on = command.endswith("smu.ON")
        else:
            raise ValueError(f"the fake does not know the command {command!r}")

    def _reading(self):
        """A placeholder reading derived from the modelled load (Ohm's law)."""
        if self.measure_function == "VOLTAGE":
            return self.source_level * self.load_resistance  # placeholder: a current source into the modelled load
        if self.source_function == "CURRENT":
            return self.source_level  # placeholder: the source current flows through the modelled load
        return 0.0  # placeholder: the voltage source mode is not covered by this driver

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        return self._pending.pop(0)

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        pass

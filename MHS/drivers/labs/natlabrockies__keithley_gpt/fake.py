"""Fake SCPI transport of the Keithley 2400 driver: a stateful stand-in for the pyvisa resource.

The upstream class (Keithley2400GPT.py) sends the SCPI lines this transport answers; its own pyvisa resource is not
used.  A write changes the value its read-back query returns, so the runtime can observe every setting it writes.
The commands and the 2-/4-wire mapping are the ones the clone writes; the start values and the identity string are
test data, marked ``# placeholder``, and are not device facts.  A query that was not recorded times out, like an
instrument that does not answer.  Nothing here talks to an instrument.
"""


class FakeKeithley2400:
    def __init__(self, **_options):
        # placeholder: test data, not the state of a real instrument
        self.identity = "Keithley Instruments,2400,0000000,1.0.0"  # placeholder
        self.current_compliance = 0.002  # placeholder
        self.measure_current_range = 0.002  # placeholder
        self.measure_voltage_range = 0.2  # placeholder
        self.four_wire = False  # placeholder
        self.nplc_current = 1.0  # placeholder
        self.nplc_voltage = 1.0  # placeholder
        self.source_current_range = 0.002  # placeholder
        self.source_voltage_range = 0.2  # placeholder
        self.output_on = False  # placeholder
        self._pending = []
        self.written = []

    def _setting(self, command):
        return {
            ":SENS:CURR:PROT": (self, "current_compliance"),
            ":SENS:CURR:RANG": (self, "measure_current_range"),
            ":SENS:VOLT:RANG": (self, "measure_voltage_range"),
            ":SENS:CURR:NPLC": (self, "nplc_current"),
            ":SENS:VOLT:NPLC": (self, "nplc_voltage"),
            ":SOUR:CURR:RANG": (self, "source_current_range"),
            ":SOUR:VOLT:RANG": (self, "source_voltage_range"),
        }.get(command)

    def _reply(self, command):
        if command == "*IDN?":
            return self.identity
        if command == ":SYST:RSEN?":
            return "1" if self.four_wire else "0"
        if command == ":SENS:CURR:PROT?":
            return f"{self.current_compliance:g}"
        if command == ":SENS:CURR:RANG?":
            return f"{self.measure_current_range:g}"
        if command == ":SENS:VOLT:RANG?":
            return f"{self.measure_voltage_range:g}"
        if command == ":SENS:CURR:NPLC?":
            return f"{self.nplc_current:g}"
        if command == ":SENS:VOLT:NPLC?":
            return f"{self.nplc_voltage:g}"
        if command == ":SOUR:CURR:RANG?":
            return f"{self.source_current_range:g}"
        if command == ":SOUR:VOLT:RANG?":
            return f"{self.source_voltage_range:g}"
        return None

    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        command, _, argument = line.strip().partition(" ")
        command = command.upper()
        argument = argument.strip()
        if command.endswith("?"):
            reply = self._reply(command)
            if reply is not None:
                self._pending.append(reply)
            return
        if command == ":SYST:RSEN":
            self.four_wire = argument.upper() == "ON"
            return
        if command == ":OUTP":
            self.output_on = argument.upper() == "ON"
            return
        setting = self._setting(command)
        if setting is not None and argument:
            owner, name = setting
            setattr(owner, name, float(argument))

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        return self._pending.pop(0)

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        pass

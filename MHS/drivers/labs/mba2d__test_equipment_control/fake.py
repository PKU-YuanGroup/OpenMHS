"""Fake SCPI transport of the A2D Eload driver: an in-memory stand-in for the instrument.

The transport answers the queries the driver's command map sends (the lines of lab_equipment/Eload_A2D_Eload.py) and
applies its writes, so a write changes the answer of its own query: CURR changes CURR?, INSTR:RELAY changes
INSTR:RELAY?, and so on.  The values are test data, never facts: the start voltage, the ADC voltage, the temperature
and the relay, LED and fan states are marked ``# placeholder`` and are not copied into a Fact, a Limit or the
reference.  The identity reply is a placeholder too.  Gate G7 (transport mode) checks the command mnemonics the driver
sends against the clone, not this class.  Nothing here talks to an instrument.
"""

#: A reply that is not one of the modelled queries.
_NO_REPLY = object()


class FakeA2DEload:
    def __init__(self, **_options):
        self._pending = []
        self.written = []
        self._current = 0.0             # placeholder: constant-current setpoint in amperes
        self._voltage = 12.0            # placeholder: supply voltage in volts
        self._adc_voltage = 11.9        # placeholder: supply voltage at the ADC in volts
        self._temperature = 25.0        # placeholder: temperature value the load reports
        self._output = False            # placeholder: the output relay is open at power-up
        self._led = False               # placeholder
        self._fan = False               # placeholder

    # -- the transport: write / read / query / close ------------------------------------------------
    def write(self, line, *, timeout_s=None):
        reply = self._handle(str(line).strip())
        self.written.append(str(line).strip())
        if reply is not _NO_REPLY:
            self._pending.append(reply)

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        return self._pending.pop(0)

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        pass

    # -- the command set of the clone ----------------------------------------------------------------
    def _handle(self, line):
        if line == "*IDN?":
            return "A2D,Eload,00000000,0.0.0"       # placeholder identity
        if line == "*RST":
            self._current = 0.0
            self._output = False
            return _NO_REPLY
        if line == "CURR 1?":
            # The clone multiplies this reply by -1 (Eload_A2D_Eload.py:74-75), so the target current comes back
            # negated; the driver does not read it, the value is here so that the query is modelled.
            return f"{-self._current:.6g}"
        if line == "MEAS:VOLT 1?":
            return f"{self._voltage:.6g}"
        if line == "MEAS:VOLT:ADC 1?":
            return f"{self._adc_voltage:.6g}"
        if line == "MEAS:TEMP 1?":
            return f"{self._temperature:.6g}"
        if line == "INSTR:RELAY 1?":
            return "1" if self._output else "0"
        if line == "INSTR:LED 1?":
            return "1" if self._led else "0"
        if line == "INSTR:FAN 1?":
            return "1" if self._fan else "0"
        state = self._state_write(line)
        if state is not _NO_REPLY:
            return _NO_REPLY
        raise TimeoutError(f"the fake load does not model the command {line!r}")

    def _state_write(self, line):
        command, _, argument = line.partition(" ")
        if command == "CURR" and argument.startswith("1,"):
            self._current = float(argument.split(",", 1)[1])
            return True
        if command in ("INSTR:RELAY", "INSTR:LED", "INSTR:FAN") and argument.startswith("1,"):
            value = argument.split(",", 1)[1].strip()
            if value not in ("0", "1"):
                raise TimeoutError(f"the fake load does not take {value!r} in {line!r}")
            if command == "INSTR:RELAY":
                self._output = value == "1"
            elif command == "INSTR:LED":
                self._led = value == "1"
            else:
                self._fan = value == "1"
            return True
        return _NO_REPLY

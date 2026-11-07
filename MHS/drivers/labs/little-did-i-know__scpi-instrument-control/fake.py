"""Fake SCPI transport of the SPD3303X driver: a small command model with no instrument behind it.

The class answers the lines this package sends, with the Siglent SPD forms of ``psu_scpi_commands.py``.  Every numeric
reply is test data marked ``# placeholder``; none of it is copied into a Fact, a Limit or the reference.  Gate G7
checks the command tokens the driver sends against the clone, not this class.  Nothing here talks to an instrument.

The transport keeps the voltage, current and tracking setpoints, so a write changes the answer of its own query, and
it records every line in ``written`` so a test can inspect the wire form.  An unknown query raises TimeoutError, the
way an instrument that does not answer behaves.
"""


class FakeSpd3303x:
    def __init__(self, **_options):
        self.voltage = 0.0                 # placeholder
        self.current = 0.0                 # placeholder
        self.tracking = 0                  # placeholder
        self.measured_voltage = 0.0        # placeholder
        self.measured_current = 0.0        # placeholder
        self.output1_on = False            # placeholder
        self.output2_on = False            # placeholder
        self.written = []
        self._pending = []

    def _reply(self, line):
        upper = line.upper()
        if upper == "*IDN?":
            return "Siglent Technologies,SPD3303X-E,SPD3XXXXXXXXXXX,V1.01"  # placeholder
        if upper == "CH1:VOLT?":
            return f"{self.voltage:.6f}"
        if upper == "CH1:CURR?":
            return f"{self.current:.6f}"
        if upper == "OUTP:TRACK?":
            return str(self.tracking)
        if upper == "MEASURE:VOLTAGE? CH1":
            return f"{self.measured_voltage:.6f}"
        if upper == "MEASURE:CURRENT? CH1":
            return f"{self.measured_current:.6f}"
        if upper == "SYST:ERR?":
            return '+0,"No error"'  # placeholder
        return None

    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        upper = line.upper()
        if "?" in line:
            self._pending.append(self._reply(line))
        elif upper.startswith("CH1:VOLT "):
            self.voltage = float(line.split(" ", 1)[1])
            self.measured_voltage = self.voltage
        elif upper.startswith("CH1:CURR "):
            self.current = float(line.split(" ", 1)[1])
            self.measured_current = self.current
        elif upper.startswith("OUTP:TRACK "):
            self.tracking = int(line.split(" ", 1)[1])
        elif upper == "OUTPUT CH1,ON":
            self.output1_on = True
        elif upper == "OUTPUT CH1,OFF":
            self.output1_on = False
        elif upper == "OUTPUT CH2,ON":
            self.output2_on = True
        elif upper == "OUTPUT CH2,OFF":
            self.output2_on = False
        elif upper == "*RST":
            self.voltage = 0.0             # placeholder
            self.current = 0.0             # placeholder
            self.tracking = 0              # placeholder
            self.measured_voltage = 0.0    # placeholder
            self.measured_current = 0.0    # placeholder
            self.output1_on = False
            self.output2_on = False

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        reply = self._pending.pop(0)
        if reply is None:
            raise TimeoutError("the instrument does not answer this query")
        return reply

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        pass

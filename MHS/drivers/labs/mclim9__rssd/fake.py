"""Fake SCPI transport of the FSWP driver: a stateful stand-in for the instrument the command map talks to.

The transport holds one plain attribute per read parameter, answers the query of each parameter from it, and lets a
write change the answer of its own query (``INP:ATT 20`` changes ``INP:ATT?``), so a write has an observable effect
on the resource state.  The e-stop commands are recorded like every other line.  A query this transport does not
know times out, like an instrument that does not answer.

Every number and every reply string here is test data, marked ``# placeholder``: none of them is a fact of the
instrument and none of them is cited anywhere.  Gate G7 (transport mode) checks the command mnemonics the driver
sends against the clone, not this class.  Nothing here talks to an instrument.
"""

#: Answers to the identity and the read queries of the command map.  All placeholder test data.
_ANSWERS = {
    "*IDN?": "Rohde&Schwarz,FSWP,100000,1.00",   # placeholder
    "INP:ATT?": None,                            # placeholder, built from attenuation_db
    "INST:LIST?": None,                          # placeholder, built from channels
    ":SENS:FREQ:CENT?": None,                    # placeholder, built from center_freq_hz
    ":SENS:SWE:POIN?": None,                     # placeholder, built from sweep_points
    "SENS:SWE:TIME?": None,                      # placeholder, built from sweep_time_s
    ":SENS:SWE:TYPE?": None,                     # placeholder, built from sweep_type
    "DISP:TRAC:Y:RLEV?": None,                   # placeholder, built from reference_level_db
}


class FakeRssd:
    def __init__(self, **_options):
        self.attenuation_db = 0          # placeholder
        self.channels = "'SAN','PNOISE'"  # placeholder
        self.center_freq_hz = 1.0e9      # placeholder
        self.sweep_points = 1001         # placeholder
        self.sweep_time_s = 0.01         # placeholder
        self.sweep_type = "SWE"          # placeholder
        self.reference_level_db = -10.0  # placeholder
        self.continuous = True           # placeholder
        self.attenuation_auto = False    # placeholder, set by the e-stop command
        self.written = []
        self._pending = []

    def _answer(self, line):
        if line == "*IDN?":
            return _ANSWERS[line]
        if line == "INP:ATT?":
            return f"{self.attenuation_db}"
        if line == "INST:LIST?":
            return self.channels
        if line == ":SENS:FREQ:CENT?":
            return f"{self.center_freq_hz:.6f}"
        if line == ":SENS:SWE:POIN?":
            return f"{self.sweep_points}"
        if line == "SENS:SWE:TIME?":
            return f"{self.sweep_time_s:.6f}"
        if line == ":SENS:SWE:TYPE?":
            return self.sweep_type
        if line == "DISP:TRAC:Y:RLEV?":
            return f"{self.reference_level_db:.6f}"
        return None

    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        if line.endswith("?"):
            self._pending.append(self._answer(line))
            return
        command, _, argument = line.partition(" ")
        value = argument.strip().split(" ")[0] if argument.strip() else ""
        if command == "INP:ATT" and value:
            self.attenuation_db = int(float(value))
        elif command == ":SENS:FREQ:CENT" and value:
            self.center_freq_hz = float(value)
        elif command == ":SENS:SWE:POIN" and value:
            self.sweep_points = int(float(value))
        elif line == "INIT:CONT OFF":
            self.continuous = False
        elif line == ":INP:ATT:AUTO ON":
            self.attenuation_auto = True

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

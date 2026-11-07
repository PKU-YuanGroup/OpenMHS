"""Fake SCPI transport for the PN300 driver.

The upstream clone has no simulator or recorded session for this instrument, so this is a stateful stand-in for
the text transport: it answers the queries the driver declares and lets each write change the answer of its own
query.  Every canned value and identity string is test data for the fake, marked ``# placeholder``; none is a fact,
a limit or a citation.  The real identity, ranges and measurement values come from the instrument.

Gate G7 (transport mode) checks the command words the driver sends against the clone, not this class.  Nothing
here talks to an instrument.
"""

import threading


class FakePn300:
    """A thread-safe line transport with the PN300 command vocabulary used by the driver."""

    def __init__(self, **_options):
        self._lock = threading.Lock()
        self._pending = []
        self.written = []
        # All values below are placeholders for the fake's initial state, not device facts.
        self._identity = "Digimess,PN300,PLACEHOLDER,0.0"  # placeholder
        self._output = "OFF"  # placeholder
        self._source = "A"  # placeholder
        self._operating_mode = "IND"  # placeholder
        self._source_type = "CV"  # placeholder
        self._protection = "LIM"  # placeholder
        self._voltage = 0.0  # placeholder
        self._current = 0.0  # placeholder

    def _reply(self, line):
        if line == "*IDN?":
            return self._identity
        if line == "OUT?":
            return "OUT_" + self._output
        if line == "SEL?":
            return "SEL_" + self._source
        if line == "OPER?":
            return "OPER_" + self._operating_mode
        if line == "CONT?":
            return "CONT_" + self._source_type
        if line == "PROT?":
            return "PROT_" + self._protection
        if line == "VSET?":
            return "V=" + format(self._voltage, ".6g")  # placeholder reply format
        if line == "ISET?":
            return "I=" + format(self._current, ".6g")  # placeholder reply format
        if line == "VOUT?":
            value = self._voltage if self._output == "ON" else 0.0
            return "V=" + format(value, ".6g")  # placeholder reply format
        if line == "IOUT?":
            value = self._current if self._output == "ON" else 0.0
            return "I=" + format(value, ".6g")  # placeholder reply format
        return None

    def _apply(self, line):
        command, _, argument = line.partition(" ")
        if command == "*RST":
            self._output = "OFF"
            self._source = "A"
            self._operating_mode = "IND"
            self._source_type = "CV"
            self._protection = "LIM"
            self._voltage = 0.0
            self._current = 0.0
        elif command == "OUT_ON":
            self._output = "ON"
        elif command == "OUT_OFF":
            self._output = "OFF"
        elif command in ("SEL_A", "SEL_B"):
            self._source = command[-1]
        elif command in ("OPER_IND", "OPER_TRAC", "OPER_PAR"):
            self._operating_mode = command.split("_", 1)[1]
        elif command in ("CONT_CC", "CONT_CV"):
            self._source_type = command.split("_", 1)[1]
        elif command in ("PROT_LIM", "PROT_CUT"):
            self._protection = command.split("_", 1)[1]
        elif command == "VSET" and argument:
            self._voltage = float(argument)
        elif command == "ISET" and argument:
            self._current = float(argument)

    def write(self, line, *, timeout_s=None):
        with self._lock:
            self.written.append(line)
            if line.endswith("?"):
                self._pending.append(self._reply(line))
            else:
                self._apply(line)

    def read(self, *, timeout_s=None):
        with self._lock:
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

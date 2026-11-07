"""Fake SCPI transport of the keysight33210A driver: a stateful command responder.

The class answers the small command set the driver's command map sends, and a write changes the answer of its own
query.  Gate G7 (transport mode) checks the command mnemonics the driver sends against the clone, not this class.
Nothing here talks to an instrument.  Every number and canned reply is test data, marked ``# placeholder``.
"""


class Fake33210A:
    def __init__(self, **_options):
        # Test data, not a fact: the identity the upstream class would accept starts with "Agilent Technologies".
        self._identity = "Agilent Technologies,33210A,0,1.0"  # placeholder
        self._frequency = 1000.0  # placeholder
        self._amplitude = 0.1  # placeholder
        self._offset = 0.0  # placeholder
        self._function = "SIN"  # placeholder
        self._load = "50"  # placeholder
        self._output = "OFF"  # placeholder
        self._pending = []
        self.written = []

    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        command, _, argument = line.strip().partition(" ")
        command = command.upper()
        argument = argument.strip()
        if command == "*IDN?":
            self._pending.append(self._identity)
        elif command == "*OPC?":
            self._pending.append("1")  # placeholder
        elif command in ("*CLS", "*RST"):
            pass
        elif command == "FREQ?":
            self._pending.append(f"{self._frequency:.10g}")
        elif command == "VOLT?":
            self._pending.append(f"{self._amplitude:.10g}")
        elif command == "VOLT:OFFS?":
            self._pending.append(f"{self._offset:.10g}")
        elif command == "FUNC?":
            self._pending.append(self._function)
        elif command == ":OUTP:LOAD?":
            self._pending.append(self._load)
        elif command == ":OUTP?":
            self._pending.append(self._output)
        elif command == "FREQ":
            self._frequency = float(argument)
        elif command == "VOLT":
            self._amplitude = float(argument)
        elif command == "VOLT:OFFS":
            self._offset = float(argument.rstrip("Vv"))
        elif command == "FUNC":
            self._function = argument.upper()
        elif command == ":OUTP:LOAD":
            self._load = argument.upper()
        elif command == ":OUTP":
            self._output = argument.upper()
        else:
            raise TimeoutError(f"the fake does not answer {line!r}")

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        return self._pending.pop(0)

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        pass

"""Fake SCPI transport of the FSV3030 driver: an in-memory spectrum analyzer, not a recording.

The replies are a state machine of the commands the driver sends.  Marker 1 and delta marker 1 follow the
upstream simulator file ``src/pyinsts/instrument/sim/Fsv3030.yaml`` of the clone; every number here is test data
and is marked ``# placeholder``.  Nothing in this file is a Fact or a Limit of the instrument.

Gate G7 checks the command mnemonics the driver sends against the clone (transport mode), not this class.
"""

#: The identity the clone's FSV3030 simulator answers at Fsv3030.yaml:13 (test data here).
_IDENTITY = "Rohde&Schwarz,FSV3030,100001,3.40"


def _number(text):
    """The numeric part of a SCPI argument, with an optional frequency suffix."""
    text = text.strip()
    for suffix in ("GHz", "MHz", "kHz", "Hz"):
        if text.endswith(suffix):
            return float(text[: -len(suffix)])
    return float(text)


def _format(value):
    return format(float(value), ".10g")


class FakeFsv3030:
    def __init__(self, **_options):
        self.center_hz = 1.0e9  # placeholder
        self.span_hz = 1.0e7  # placeholder
        self.marker_hz = 9.5e8  # placeholder
        self.marker_level = -12.5  # placeholder
        self.delta_marker_hz = 1.0e6  # placeholder
        self.delta_marker_level = -3.0  # placeholder
        self.error_display = "ON"  # placeholder
        self.continuous_peak = "OFF"  # placeholder
        self.aborted = False
        self.written = []
        self._pending = []

    # -- SCPI transport --------------------------------------------------------
    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        if "?" in line:
            self._pending.append(self._query_reply(line))
            return
        command, _, argument = line.partition(" ")
        if command == "SENSE:FREQ:CENT":
            self.center_hz = _number(argument)
        elif command == "FREQ:SPAN":
            self.span_hz = _number(argument)
        elif command == "CALC:MARK1:X":
            self.marker_hz = _number(argument)
        elif command == "SYST:ERR:DISP":
            self.error_display = argument.strip()
        elif command == "CALCulate1:MARKer1:MAXimum:AUTO":
            self.continuous_peak = argument.strip()
        elif command == "ABOR":
            self.aborted = True
        # An unknown write is accepted silently, as a SCPI instrument that ignores a command it does not know.

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
        self._pending.clear()

    # -- replies ---------------------------------------------------------------
    def _query_reply(self, line):
        if line == "*IDN?":
            return _IDENTITY
        if line == "*OPC?":
            return "1"  # placeholder
        if line == "FREQ:CENT?":
            return _format(self.center_hz)
        if line == "CALC:MARK1:X?":
            return _format(self.marker_hz)
        if line == "CALC:MARK1:Y?":
            return _format(self.marker_level)
        if line == "CALC:DELT1:X?":
            return _format(self.delta_marker_hz)
        if line == "CALC:DELT1:Y?":
            return _format(self.delta_marker_level)
        return None

"""Fake SCPI transport for the Agilent 33600A driver: an in-memory instrument with the clone's command set.

It implements only ``write``, ``read``, ``query`` and ``close``, the pyvisa-resource surface the upstream scripts
use (``inst.write``, ``inst.read``, ``inst.query`` and ``inst.close`` in AgilentControl.py and UploadArb.py), and
answers the command lines the driver's command map sends.  A query is written and then read as two steps, so the
reply of a query is queued in ``_pending``.  A write changes the answer of its own query, which is what the gate's
effect test observes.

This is not a recording of an instrument run.  Every start value, the identity string and the error reply are test
data marked ``# placeholder``; none of them is a Fact or a Limit.  Gate G7 (transport mode) checks the command
mnemonics against the clone, not this class.  Nothing here talks to an instrument.
"""


class FakeAgilent33600:
    #: A stand-in identity string; the driver does not constrain '*IDN?'.
    IDENTITY = "Agilent Technologies,33622A,0,1.0"  # placeholder

    def __init__(self, **_options):
        self.frequency_hz = 1_000_000.0  # placeholder
        self.amplitude_v = 0.1  # placeholder
        self.offset_v = 0.0  # placeholder
        self.function = "SIN"  # placeholder
        self.waveform = "ATLASCALIB_B"  # placeholder
        self.sample_rate_hz = 1_000_000_000.0  # placeholder
        self.output_on = True  # placeholder
        self.written = []
        self._pending = []

    # -- transport surface ---------------------------------------------------
    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        command, _, argument = line.partition(" ")
        if command.endswith("?"):
            self._pending.append(self._reply(command))
        elif command == "*RST":
            self.amplitude_v = 0.0  # placeholder
        elif command == "SOURCE1:FREQUENCY":
            self.frequency_hz = float(argument)
        elif command == "SOURCE1:VOLTAGE":
            self.amplitude_v = float(argument)
        elif command == "SOUR1:VOLT:OFFS":
            self.offset_v = float(argument)
        elif command == "SOURCE1:FUNC":
            self.function = argument.strip()
        elif command == "SOUR1:FUNC:ARB:SRAT":
            self.sample_rate_hz = float(argument)
        elif command == "SOUR1:FUNC:ARB":
            self.waveform = argument.strip()
        elif command == "OUTPUT1":
            self.output_on = argument.strip() == "ON"
        else:
            raise ValueError(f"the fake does not implement the command {line!r}")

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        return self._pending.pop(0)

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        pass

    # -- replies -------------------------------------------------------------
    def _reply(self, command):
        if command == "*IDN?":
            return self.IDENTITY
        if command == "SYST:ERR?":
            return '+0,"No error"'  # placeholder
        if command == "SOURCE1:FREQUENCY?":
            return repr(self.frequency_hz)
        if command == "SOURCE1:VOLTAGE?":
            return repr(self.amplitude_v)
        if command == "SOUR1:VOLT:OFFS?":
            return repr(self.offset_v)
        if command == "SOURCE1:FUNC?":
            return self.function
        if command == "SOUR1:FUNC:ARB:SRAT?":
            return repr(self.sample_rate_hz)
        if command == "SOUR1:FUNC:ARB?":
            return self.waveform
        raise TimeoutError(f"the fake does not answer the query {command!r}")

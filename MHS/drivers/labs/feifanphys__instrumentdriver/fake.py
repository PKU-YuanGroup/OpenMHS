"""Fake SCPI transport for the Keysight N5182B driver, modelled on the clone's own mock.

The upstream clone ships ``KeysightN5182BMock`` in ``drivers/SignalGenerator/KeysightN5182B.py`` (lines 25-88); this
class reproduces its behaviour without importing it: it holds the same state attributes, answers ``*IDN?``, ``FREQ?``,
``POW?`` and ``OUTP?``, and applies ``*RST``, ``FREQ``, ``POW`` and ``OUTP`` writes.  The bridge sends a query as a
write followed by a read (the transport has a ``read`` method), so ``write`` queues the reply and ``read`` pops it;
``query`` is the write-then-read pair used by the identity probe on connect.

Gate G7 (transport mode) checks the command mnemonics the driver sends against the clone, not this class.  Every
canned state value below is test data (marked ``# placeholder``), not a fact or a device limit.  Nothing here talks to
an instrument.
"""


class FakeN5182B:
    """A stand-in for the upstream ``KeysightN5182BMock`` transport."""

    def __init__(self, **_options):
        self.command_log = []
        self.frequency_hz = 1.0e9  # placeholder
        self.power_dbm = 0.0  # placeholder
        self.output_enabled = False  # placeholder
        self.idn = "Keysight Technologies,N5182B,MY12345678,A.01.00"  # placeholder
        self._pending = []

    def write(self, line, *, timeout_s=None):
        line = line.strip()
        self.command_log.append(("query" if line.endswith("?") else "write", line))
        if line.endswith("?"):
            self._pending.append(self._answer(line))
            return
        self._apply(line)

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        return self._pending.pop(0)

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        pass

    def _answer(self, line):
        if line == "*IDN?":
            return self.idn
        if line == "FREQ?":
            return str(self.frequency_hz)
        if line == "POW?":
            return str(self.power_dbm)
        if line == "OUTP?":
            return "1" if self.output_enabled else "0"  # placeholder reply
        raise ValueError(f"Unsupported SCPI query: {line}")

    def _apply(self, line):
        if line == "*RST":
            self.frequency_hz = 1.0e9  # placeholder
            self.power_dbm = 0.0  # placeholder
            self.output_enabled = False  # placeholder
            return
        if line.startswith("FREQ "):
            self.frequency_hz = float(line[len("FREQ "):].strip())
            return
        if line.startswith("POW "):
            value = line[len("POW "):].strip()
            if value.upper().endswith("DBM"):
                value = value[:-3].strip()
            self.power_dbm = float(value)
            return
        if line == "OUTP ON":
            self.output_enabled = True
            return
        if line == "OUTP OFF":
            self.output_enabled = False
            return
        raise ValueError(f"Unsupported SCPI command: {line}")

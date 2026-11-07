"""Fake SCPI transport of the LeCroy WaveRunner 104MXi-A driver: a reply table plus the effect of writes.

Every reply below is placeholder test data (``# placeholder``): it is not a reading of an instrument and not a fact of
the clone.  The table answers every query of the driver's read map by lookup, whatever the order, and a write of a
setting changes the reply of its own query (``TRMD norm`` changes ``TRMD?``).  A query that is not in the table times
out, like an instrument that does not answer.

Gate G7 (transport mode) checks the command mnemonics the driver sends against the clone, not this class.  Nothing
here talks to an instrument.
"""

#: A write of ``<command> <value>`` changes the answer to ``<command>?``.
_SETTINGS = {
    "TRMD": "TRMD?",
    ":acquire:type": ":acquire:type?",
    ":acquire:mode": ":acquire:mode?",
    ":acquire:count": ":acquire:count?",
    ":timebase:mode": ":timebase:mode?",
    ":timebase:reference": ":timebase:reference?",
}


class FakeLecroyWR104MXIA:
    # placeholder: the reply table of a stand-in instrument
    RESPONSES = {
        "*IDN?": "LECROY,WR104MXI-A,000000,0.0.0",  # placeholder
        "TRMD?": "auto",  # placeholder
        ":acquire:type?": "norm",  # placeholder
        ":acquire:mode?": "rtim",  # placeholder
        ":acquire:count?": "16",  # placeholder
        ":timebase:mode?": "main",  # placeholder
        ":timebase:reference?": "cent",  # placeholder
        ":measure:frequency? C1": "1.0e+06",  # placeholder
        ":measure:period? C1": "1.0e-06",  # placeholder
        ":measure:vpp? C1": "2.0",  # placeholder
    }

    def __init__(self, **_options):
        self._replies = dict(self.RESPONSES)
        self._pending = []
        self.written = []

    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        if "?" in line:
            self._pending.append(self._replies.get(line))
            return
        command, _, argument = line.partition(" ")
        query = _SETTINGS.get(command)
        if query is not None and argument:
            self._replies[query] = argument.strip()

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

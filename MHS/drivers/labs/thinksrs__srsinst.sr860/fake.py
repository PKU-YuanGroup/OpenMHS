"""Fake SCPI transport of the SR860 driver: a lookup replay of a recorded session, plus the effect of writes.

The session is fixtures/session.json (the format of ``mhs.testing.Transcript``): the identity, the frequency and the
R and Theta that README.md of the upstream clone prints, with X and Y derived from them.  A strict replay
(``transcript = "fixtures/session.json"`` on the driver) needs one fixed request sequence, but the gate and the
conformance suite send many different sequences, each on a fresh transport.  So this transport answers every
recorded query by lookup, whatever the order, and lets a write change the answer of its own query (FREQ x changes
FREQ?, SLVL x changes SLVL?).  A query that was not recorded times out, like an instrument that does not answer.

Gate G7 (transport mode) checks the command mnemonics the driver sends against the clone, not this class.  Nothing
here talks to an instrument.
"""

import json
from pathlib import Path

SESSION = Path(__file__).resolve().parent / "fixtures" / "session.json"
#: A write of ``<command> <value>`` changes the answer to ``<command>?``.
_SETTINGS = ("FREQ", "SLVL", "OFLT")


class FakeSr860:
    def __init__(self, **_options):
        exchanges = json.loads(SESSION.read_text(encoding="utf-8"))["exchanges"]
        self._replies = {item["send"]: item["recv"] for item in exchanges if "recv" in item}
        self._pending = []
        self.written = []

    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        command, _, argument = line.partition(" ")
        if "?" in command:
            self._pending.append(self._replies.get(line))
        elif command in _SETTINGS and argument:
            self._replies[command + "?"] = argument.strip()

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

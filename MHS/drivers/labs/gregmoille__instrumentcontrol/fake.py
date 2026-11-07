"""Fake SCPI transport of the Tektronix DPO70000 driver.

The fixture ``fixtures/session.json`` is a synthetic transcript in the format of ``mhs.bridge.transcript``: every
reply is a placeholder (test data), not a reading of an instrument.  A strict replay would need one fixed request
sequence, but the gate and the conformance suite send different sequences on fresh transports, so this transport
looks each query up and lets a write change the answer of its own query (``ACQ:MOD AVE`` changes ``ACQ:MOD?``).
A query that is not in the transcript times out, like an instrument that does not answer.

Gate G7 (transport mode) checks the command mnemonics the driver sends against the clone, not this class.  Nothing
here talks to an instrument.
"""

import json
from pathlib import Path

SESSION = Path(__file__).resolve().parent / "fixtures" / "session.json"

#: A write of ``<command> <value>`` changes the answer to ``<command>?``.  ``:STOP``/``:RUN`` change ACQ:STATE?.
_SETTINGS = (
    "ACQ:MOD",
    "ACQ:NUMSAM",
    "ACQ:SAMP",
    "ACQ:STATE",
    "ACQ:STOPA",
    "ACQ:ENHANCEDE",
    "ACQ:ENHANCEDE:STATE",
    "ACQ:INTERPE",
    "ACQ:MAG",
)


class FakeTekDpo70000:
    def __init__(self, **_options):
        exchanges = json.loads(SESSION.read_text(encoding="utf-8"))["exchanges"]
        self._replies = {item["send"]: item["recv"] for item in exchanges if "recv" in item}
        self._pending = []
        self.written = []

    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        command, _, argument = line.partition(" ")
        if command.endswith("?"):
            self._pending.append(self._replies.get(line))
        elif command == ":STOP":
            self._replies["ACQ:STATE?"] = "STOP"
        elif command == ":RUN":
            self._replies["ACQ:STATE?"] = "RUN"
        elif command == "TRIG FORC":
            self._replies["TRIG:STATE?"] = "READY"  # placeholder: a forced trigger completes
        elif command in _SETTINGS and argument:
            self._replies[command + "?"] = argument.strip()
        else:
            raise AssertionError(f"the fake transcript has no effect for {line!r}")

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

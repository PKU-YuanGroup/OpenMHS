"""Fake SCPI transport of the TDS 3052 driver: the two settings the clone reads back, plus the writes it receives.

The upstream clone is a script with no simulator or mock (the card's ``mock_strategy`` prefers a transcript, but the
recorded session it names does not exist here and the clone records nothing).  This transport therefore answers the
two queries the clone reads back, ``CH1:SCALE?`` and ``CH2:SCALE?`` (``tekdaq.py:153-156``), and records every line
the bridge writes.  A ``CH1:SCA`` or ``CH2:SCA`` write changes the answer of its own query; every other write is
only recorded, because the clone states no query that reads it back.  An unrecorded query times out, like an
instrument that does not answer.

The startup values and the identity string are test data, not facts of the device: each is marked ``# placeholder``.
Gate G7 (transport mode) checks the command mnemonics the driver sends against the clone, not this class.  Nothing
here talks to an instrument.
"""


class FakeTds3052:
    def __init__(self, **_options):
        self.ch1_scale = 0.2  # placeholder
        self.ch2_scale = 0.2  # placeholder
        self.written: list[str] = []
        self._pending: list[str | None] = []

    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        command, _, argument = line.partition(" ")
        if command.endswith("?"):
            self._pending.append(self._reply(command))
        elif command == "CH1:SCA" and argument:
            self.ch1_scale = float(argument)
        elif command == "CH2:SCA" and argument:
            self.ch2_scale = float(argument)

    def _reply(self, command: str) -> str | None:
        replies = {
            "*IDN?": "TEKTRONIX,TDS 3052,0,1.0",  # placeholder
            "CH1:SCALE?": f"{self.ch1_scale:g}",
            "CH2:SCALE?": f"{self.ch2_scale:g}",
        }
        return replies.get(command)

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

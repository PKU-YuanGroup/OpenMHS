"""Fake SCPI transport for the SR865 driver: the state the three command words touch, no instrument.

The bridge sends ``OFLT <index>``, ``SCAL <index>`` and ``PHAS <degrees>`` to program the instrument, and
``OFLT?``, ``SCAL?`` and ``PHAS?`` to read the settings back.  A write changes the answer of its own query, so a
receipt and the state that follows it agree.  The e-stop command ``*CLS`` is recorded and changes no setting, as
the status clear does on the instrument.

The initial indexes and phase are test data, not facts about the instrument (the real start-up state is not stated
in the clone), so each is marked ``# placeholder``.  Gate G7 checks the command mnemonics the driver sends against
the clone, not this class.  Nothing here talks to an instrument.
"""


class FakeSr865:
    def __init__(self, **_options):
        self.tau_index = 0  # placeholder
        self.sens_index = 0  # placeholder
        self.phase = 0.0  # placeholder
        self._pending = []
        self.written = []

    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        command, _, argument = line.partition(" ")
        if command == "OFLT":
            self.tau_index = int(argument)
        elif command == "SCAL":
            self.sens_index = int(argument)
        elif command == "PHAS":
            self.phase = float(argument)
        elif command == "OFLT?":
            self._pending.append(str(self.tau_index))
        elif command == "SCAL?":
            self._pending.append(str(self.sens_index))
        elif command == "PHAS?":
            self._pending.append(f"{self.phase:.6f}")
        elif command == "*CLS":
            pass
        elif command.endswith("?"):
            self._pending.append(None)

    def read(self, *, timeout_s=None):
        if not self._pending:
            raise TimeoutError("no response is pending")
        reply = self._pending.pop(0)
        if reply is None:
            raise TimeoutError("the fake has no reply for this query")
        return reply

    def query(self, line, *, timeout_s=None):
        self.write(line, timeout_s=timeout_s)
        return self.read(timeout_s=timeout_s)

    def close(self):
        pass

"""Fake SCPI transport of the DG645 driver: an in-memory instrument that answers the lines the clone sends.

No upstream simulator or recorded session exists in the clone, so this is a stateful test double, not a replay of a
real instrument: the start values below are only test data and every one is marked ``# placeholder``.  It implements
the transport surface the ScpiBridge calls (``write``, ``read``, ``query``, ``begin_query``, ``close``); a write
changes the answer of its own query, so a write is observable in the state the runtime reads back.  Gate G7 checks
the command mnemonics the driver sends against the clone, not this class.  Nothing here talks to an instrument.
"""


class FakeDg645:
    def __init__(self, **_options):
        self.written: list[str] = []
        self._pending: list[str | None] = []
        self._idn = "Stanford_Research_Systems,DG645,000000,1.0"  # placeholder
        self._error = '0,"No error"'  # placeholder
        self._scalars = {
            "TIMB": "0",        # placeholder
            "TSRC": "1",        # placeholder
            "HOLD": "0.0",      # placeholder
            "TLVL": "1.0",      # placeholder
            "TRAT": "1000.0",   # placeholder
            "BURC": "1",        # placeholder
            "BURD": "0.0",      # placeholder
            "BURM": "1",        # placeholder
            "BURP": "0.001",    # placeholder
            "BURT": "0",        # placeholder
        }
        self._polarity = {1: "0", 2: "0", 3: "0", 4: "0"}       # placeholder
        self._amplitude = {1: "1.0", 2: "1.0", 3: "1.0", 4: "1.0"}  # placeholder
        self._offset = {1: "0.0", 2: "0.0", 3: "0.0", 4: "0.0"}     # placeholder
        self._delay = {1: "0.0", 2: "0.0", 3: "0.0", 4: "0.0"}      # placeholder

    def write(self, line, *, timeout_s=None):
        self.written.append(line)
        text = line.strip()
        if "?" in text:
            self._pending.append(self._answer(text))
        else:
            self._apply(text)

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

    def begin_query(self):
        self._pending.clear()

    def close(self):
        pass

    def _apply(self, text: str) -> None:
        head, _, rest = text.partition(" ")
        parts = [item.strip() for item in rest.split(",")]
        if head == "LPOL" and len(parts) == 2:
            self._polarity[int(parts[0])] = parts[1]
        elif head == "LAMP" and len(parts) == 2:
            self._amplitude[int(parts[0])] = parts[1]
        elif head == "LOFF" and len(parts) == 2:
            self._offset[int(parts[0])] = parts[1]
        elif head == "DLAY" and len(parts) == 3:
            self._delay[int(parts[0])] = parts[2]
        elif head in self._scalars:
            self._scalars[head] = rest

    def _answer(self, text: str) -> str | None:
        head, _, rest = text.partition(" ")
        if head == "*IDN?":
            return self._idn
        if head == "LERR?":
            return self._error
        if head == "LPOL?":
            return self._polarity.get(int(rest))
        if head == "LAMP?":
            return self._amplitude.get(int(rest))
        if head == "LOFF?":
            return self._offset.get(int(rest))
        if head == "DLAY?":
            return self._delay.get(int(rest))
        if head.endswith("?") and head[:-1] in self._scalars:
            return self._scalars[head[:-1]]
        return None

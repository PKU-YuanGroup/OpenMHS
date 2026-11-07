"""Fake serial transport of the Harvard Apparatus Model 44 driver: an in-memory pump, not upstream code.

The bridge expects a pyserial-like object (``write``/``readline``/``read``/``reset_input_buffer``/``close``).  This
class implements the commands the driver maps and keeps the pump state, so a write changes the answer of its own
query.  It does not import or run the upstream clone (which is read-only and Python 2), and it does not talk to an
instrument.

The reply frame is the one the clone reads (harvardpump/pump.py:144-165): LF, the reply text ending at CR, a status
digit and a prompt character, then LF.  ``readline`` returns up to and including LF, so the bridge sees the CR in the
second chunk and stops there; the prompt is part of that chunk and is parsed by the driver's actions.

Every number below is test data for the fake, not a device fact or a safety limit: each is marked ``# placeholder``
and none is copied into a Fact, a Limit or the reference.  Gate G7 (transport mode) checks the command mnemonics the
driver sends against the clone, not this class.
"""

from mhs.bridge.serial import FakeSerial


class FakeHarvardSyringePump(FakeSerial):
    """A pyserial-like stand-in that answers the commands of the Model 44 driver."""

    def __init__(self, **_options):
        super().__init__()
        self._buffer = bytearray()
        self._diameter = 1.0                  # placeholder
        self._flow_rate = 1.0                 # placeholder, mL/min
        self._target_volume = 0.0             # placeholder, mL
        self._accumulated_volume = 0.0        # placeholder, mL
        self._mode = "PMP"                    # placeholder
        self._direction = "INF"               # placeholder
        self._running = False
        self._version = "fake-1.0"            # placeholder

    # -- pyserial-like transport -------------------------------------------------
    def write(self, data: bytes) -> int:
        line = data.decode("ascii", "replace").replace("\r", "").replace("\n", "").strip()
        self.written.append(line)
        text = self._handle(line)
        self._buffer.extend(self._frame(text).encode("ascii"))
        return len(data)

    def readline(self) -> bytes:
        newline = self._buffer.find(b"\n")
        if newline < 0:
            chunk = bytes(self._buffer)
            self._buffer.clear()
            return chunk
        chunk = bytes(self._buffer[: newline + 1])
        del self._buffer[: newline + 1]
        return chunk

    def read(self, size: int = 1) -> bytes:
        chunk = bytes(self._buffer[:size])
        del self._buffer[:size]
        return chunk

    def reset_input_buffer(self) -> None:
        self._buffer.clear()

    def close(self) -> None:
        self.is_open = False

    # -- device behaviour --------------------------------------------------------
    def _frame(self, text: str) -> str:
        if self._direction == "REF":
            prompt = "<"
        elif self._running:
            prompt = ">"
        else:
            prompt = ":"
        return f"\n{text}\r0{prompt}\n"

    def _handle(self, line: str) -> str:
        parts = line.split()
        if not parts:
            return ""
        command, args = parts[0], parts[1:]
        if command == "DIA":
            if args:
                self._diameter = float(args[0])
                return ""
            return f"{self._diameter:g}"
        if command == "RAT":
            if len(args) >= 2:
                self._flow_rate = float(args[0])
                return ""
            return f"{self._flow_rate:g} ml/mn"
        if command == "TGT":
            if args:
                self._target_volume = float(args[0])
                return ""
            return f"{self._target_volume:g}"
        if command == "DEL":
            return f"{self._accumulated_volume:g}"
        if command == "VER":
            return self._version
        if command == "MOD":
            if args:
                self._mode = args[0]
                return ""
            return self._mode
        if command == "DIR":
            if args:
                self._direction = args[0]
                return ""
            return ""
        if command == "RUN":
            self._running = True
            return ""
        if command == "STP":
            self._running = False
            return ""
        if command == "CLD":
            self._accumulated_volume = 0.0
            return ""
        if command == "CLT":
            self._target_volume = 0.0
            return ""
        return "?"

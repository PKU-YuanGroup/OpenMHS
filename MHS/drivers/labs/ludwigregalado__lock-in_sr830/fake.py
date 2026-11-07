"""Fake serial transport of the SR830 driver: an in-memory SR830, not upstream code.

The serial bridge expects a pyserial-like object (``write``, ``readline``, ``read``, ``reset_input_buffer`` and
``close``).  This class implements the commands the driver maps and keeps the settings, so a write changes the
answer of its own query.  It does not import or run the upstream clone and it does not talk to an instrument.

Every number below is placeholder test data, not a device fact or a safety limit: each is marked ``# placeholder``
and none is copied into a Fact, a Limit or the reference.  Gate G7 (transport mode) checks the command mnemonics
the driver sends against the clone, not this class.
"""

from mhs.bridge.serial import FakeSerial


class FakeLockInSr830(FakeSerial):
    """A pyserial-like stand-in that answers the commands of the SR830 driver."""

    def __init__(self, **_options):
        super().__init__()
        self._x = 1.234e-3                       # placeholder
        self._y = -4.56e-4                       # placeholder
        self._r = 1.3156e-3                      # placeholder
        self._theta = 20.3                       # placeholder
        self._phase = 0.0                        # placeholder
        self._frequency = 1000.0                 # placeholder, Hz
        self._amplitude = 1.0                    # placeholder
        self._input_config = 0                   # placeholder
        self._ground = 0                         # placeholder
        self._coupling = 0                       # placeholder
        self._line_filter = 0                    # placeholder
        self._reserve = 0                        # placeholder
        self._time_constant_index = 0            # placeholder
        self._slope = 0                          # placeholder
        self._sync = 0                           # placeholder
        self._identity = "Stanford_Research_Systems,SR830,fake,1.0"  # placeholder

    # -- pyserial-like transport -------------------------------------------------
    def write(self, data: bytes) -> int:
        """Record the command and apply it or queue its reply."""
        line = data.decode("ascii", "replace").replace("\r", "").replace("\n", "").strip()
        self.written.append(line)
        parts = line.split()
        if not parts:
            return len(data)
        command, arguments = parts[0], parts[1:]
        if command.endswith("?"):
            self._answer(command, arguments)
        else:
            self._apply(command, arguments)
        return len(data)

    def readline(self) -> bytes:
        """Return the queued reply up to and including its newline."""
        newline = self._buffer.find(b"\n")
        if newline < 0:
            chunk = bytes(self._buffer)
            self._buffer.clear()
            return chunk
        chunk = bytes(self._buffer[:newline + 1])
        del self._buffer[:newline + 1]
        return chunk

    # -- device behaviour --------------------------------------------------------
    def _reply(self, text: str) -> None:
        self._buffer.extend((text + "\n").encode("ascii"))

    def _answer(self, command: str, arguments: list[str]) -> None:
        if command == "*IDN?":
            self._reply(self._identity)
        elif command == "OUTP?":
            index = int(arguments[0]) if arguments else 1
            values = {1: self._x, 2: self._y, 3: self._r, 4: self._theta}  # placeholder replies
            self._reply(_number(values.get(index, 0.0)))
        elif command == "PHAS?":
            self._reply(_number(self._phase))
        elif command == "FREQ?":
            self._reply(_number(self._frequency))
        elif command == "SLVL?":
            self._reply(_number(self._amplitude))
        elif command == "ISRC?":
            self._reply(str(self._input_config))
        elif command == "IGND?":
            self._reply(str(self._ground))
        elif command == "ICPL?":
            self._reply(str(self._coupling))
        elif command == "ILIN?":
            self._reply(str(self._line_filter))
        elif command == "RMOD?":
            self._reply(str(self._reserve))
        elif command == "OFLT?":
            self._reply(str(self._time_constant_index))
        elif command == "OFSL?":
            self._reply(str(self._slope))
        elif command == "SYNC?":
            self._reply(str(self._sync))
        else:
            self._reply("?")

    def _apply(self, command: str, arguments: list[str]) -> None:
        if not arguments:
            return
        value = arguments[0]
        if command == "FREQ":
            self._frequency = float(value)
        elif command == "SLVL":
            self._amplitude = float(value)
        elif command == "ISRC":
            self._input_config = int(value)
        elif command == "IGND":
            self._ground = int(value)
        elif command == "ICPL":
            self._coupling = int(value)
        elif command == "ILIN":
            self._line_filter = int(value)
        elif command == "RMOD":
            self._reserve = int(value)
        elif command == "OFLT":
            self._time_constant_index = int(value)
        elif command == "OFSL":
            self._slope = int(value)
        elif command == "SYNC":
            self._sync = int(value)


def _number(value: float) -> str:
    """A decimal reply with up to ten significant digits."""
    return f"{float(value):.10g}"

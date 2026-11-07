"""Fake backend of the KDS Gemini 88 driver: an in-memory stand-in for the upstream ``realSerial.writeSerial``.

Gate G7: the only public method defined here is ``Write``, which exists on the upstream class
``realSerial:writeSerial`` (``realSerial.py:26-33``), and the attributes the driver reaches (``input`` and ``ser``)
are the ones the upstream ``__init__`` sets.  The serial port is a small pyserial-like object; the driver reads the
status reply through it.  Every starting value and reply below is test data, not a fact about a pump: each is
marked ``# placeholder``.  Nothing here talks to a device or reproduces the pump protocol.
"""


class _FakePort:
    """The serial object the upstream object keeps as ``ser``; only ``readline``/``write``/``close`` are used."""

    def __init__(self):
        self.written = []
        self._buffer = bytearray()
        self._running = None
        self._last_command = None
        self.is_open = True

    def write(self, data):
        self.written.append(bytes(data))
        line = bytes(data).decode("ascii", "replace").strip()
        self._last_command = line
        command = line.split(" ", 1)[0]
        if command == "status":
            state = "idle" if self._running is None else f"running {self._running}"
            self._buffer.extend(f"FAKE: {state}\r\n".encode("ascii"))      # placeholder
        elif command == "run":
            self._running = line.split(" ", 1)[1] if " " in line else "ab"  # placeholder channel
        elif command == "stop":
            self._running = None
        return len(data)

    def readline(self):
        if not self._buffer:
            return b""
        newline = self._buffer.find(b"\n")
        if newline < 0:
            chunk = bytes(self._buffer)
            self._buffer.clear()
            return chunk
        chunk = bytes(self._buffer[: newline + 1])
        del self._buffer[: newline + 1]
        return chunk

    def reset_input_buffer(self):
        self._buffer.clear()

    def close(self):
        self.is_open = False


class FakeGemini88:
    """Stand-in for ``realSerial:writeSerial``: ``Write`` sends the bytes held in ``input`` plus CRLF."""

    def __init__(self, **_options):
        self.ser = _FakePort()
        self.input = b""                                                    # placeholder

    def Write(self):
        self.ser.write(self.input + b"\r\n")
        return True

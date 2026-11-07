"""Fake backend of the leicacam driver: an in-memory stand-in for leicacam.cam:CAM.

Gate G7: every public method defined here exists on leicacam.cam:CAM (src/leicacam/cam.py:133-343).  The upstream has
its own mock, ``EchoSocket`` in tests/test_cam.py:31-55: it keeps the bytes ``CAM.send`` wrote and returns them from
``recv``, so a command comes back as the message the client sent (tests/test_cam.py:64-81).  This fake reproduces that
answer in memory: every convenience method replies with the message CAM would have sent for it -- the client prefix
(src/leicacam/cam.py:49-54) plus the command's fields -- rendered as ``_parse_receive`` and ``bytes_as_dict`` render a
reply (src/leicacam/cam.py:81-104, 408-436).  The reply values are the arguments of the call and the fixed command
words of the protocol; nothing here is a statement about a real instrument.  The fake holds no socket: the upstream
constructor connects (src/leicacam/cam.py:110-121), so this class is a separate object and never derives from CAM
(G3 FAKE_IS_NATIVE).
"""

from collections import OrderedDict

#: The client prefix CAM prepends to every message (src/leicacam/cam.py:49-54).
PREFIX = (("cli", "python-leicacam"), ("app", "matrix"))


class FakeCAM:
    """Answers each CAM command in memory with the message the upstream client would have sent."""

    def __init__(self, **_options):
        self.sent = b""           # placeholder: the bytes a send() would have written
        self.closed = False

    # -- the message layer ---------------------------------------------------------------------------------------
    def send(self, commands):
        if isinstance(commands, (bytes, bytearray)):
            self.sent = bytes(commands)
        else:
            self.sent = " ".join(f"/{key}:{value}" for key, value in commands).encode()
        return len(self.sent)

    # -- convenience methods (names and signatures of src/leicacam/cam.py:210-343) ------------------------------
    def start_scan(self):
        return self._reply(("cmd", "startscan"))

    def stop_scan(self):
        return self._reply(("cmd", "stopscan"))

    def autofocus_scan(self):
        return self._reply(("cmd", "autofocusscan"))

    def pause_scan(self):
        return self._reply(("cmd", "pausescan"))

    def enable(self, slide=0, wellx=1, welly=1, fieldx=1, fieldy=1):
        return self._reply(("cmd", "enable"), ("slide", str(slide)), ("wellx", str(wellx)), ("welly", str(welly)),
                           ("fieldx", str(fieldx)), ("fieldy", str(fieldy)), ("value", "true"))

    def disable(self, slide=0, wellx=1, welly=1, fieldx=1, fieldy=1):
        return self._reply(("cmd", "enable"), ("slide", str(slide)), ("wellx", str(wellx)), ("welly", str(welly)),
                           ("fieldx", str(fieldx)), ("fieldy", str(fieldy)), ("value", "false"))

    def enable_all(self):
        return self._reply(("cmd", "enableall"), ("value", "true"))

    def disable_all(self):
        return self._reply(("cmd", "enableall"), ("value", "false"))

    def get_information(self, about="stage"):
        return self._reply(("cmd", "getinfo"), ("dev", str(about)))

    def wait_for(self, cmd, value=None, timeout=60):
        """The echo of the last message send() wrote when it carries ``cmd`` (and ``value``), else an empty message: what
        CAM.wait_for returns on the upstream echo socket (src/leicacam/cam.py:171-208, tests/test_cam.py:31-55)."""
        fields = tuple(tuple(item[1:].split(":", 1)) for item in self.sent.decode().split(" ") if ":" in item)
        if any(key == cmd and (value is None or text == value) for key, text in fields):
            return self._reply(*fields)
        return OrderedDict()

    def close(self):
        self.closed = True

    # -- helpers -------------------------------------------------------------------------------------------------
    @staticmethod
    def _reply(*fields):
        """The parsed message an echo of the command gives (tests/test_cam.py:64-81)."""
        return OrderedDict(PREFIX + tuple(fields))

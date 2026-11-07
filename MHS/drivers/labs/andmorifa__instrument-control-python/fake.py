"""Fake backend of the Red Pitaya driver: an in-memory stand-in for redpitaya_client:RedPitayaClient.

Gate G7: the public methods here are the methods of the upstream class (src/redpitaya_client.py:26-71) --
``connect``, ``send_cmd``, ``query`` and ``close`` -- and ``is_connected``/``socket`` are the attributes the upstream
``__init__`` assigns (lines 20-24).  The fake starts already connected, as the driver sees the client after the
hardware factory's ``connect``; it never talks to a device.  All numbers and the reply text below are placeholder
test data, not device facts.
"""


class _FakeSocket:
    """The socket object the upstream close() closes."""

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeRedPitaya:
    def __init__(self, **options):
        self.ip = str(options.get("ip", "127.0.0.1"))       # placeholder test data
        self.port = int(options.get("port", 5000))          # placeholder test data
        self.timeout = float(options.get("timeout", 2.0))   # placeholder test data
        self.socket = _FakeSocket()
        self.is_connected = True                            # placeholder starting state
        self._sent = []                                      # test record, not upstream state

    def connect(self):
        self.socket = _FakeSocket()
        self.is_connected = True

    def send_cmd(self, command):
        if not self.is_connected:
            raise ConnectionError("Not connected to instrument.")
        self._sent.append(str(command))

    def query(self, command, buffer_size=4096):              # placeholder signature default, not a device fact
        self.send_cmd(command)
        return "OK: " + str(command)                        # placeholder canned reply

    def close(self):
        if self.socket:
            self.socket.close()
            self.is_connected = False

"""Fake backend of the comunication-instrument driver: an in-memory stand-in for the serial client.

The fake implements the two public methods of the upstream ``Client`` class (modules/comunication_client.py:30-60)
with the same names and signatures: ``write_request(command)`` and ``read_response()``.  It also carries the ``ser``
attribute the upstream ``Client.__init__`` assigns, because the driver's e-stop calls ``Client.ser.close`` (the clone
has no stop request).  The stand-in's ``ser`` records that it was closed; a real pyserial port would refuse further
I/O, while this in-memory object keeps its canned replies so the runtime can still read the state after an e-stop.

Every reply below is test data of the stand-in, not a device fact, and each one is marked ``# placeholder``.  A real
instrument returns a new random value for every request (modules/simulated_instrument.py:61-80); this fake returns
fixed values so a test can compare them.

Gate G7: the class defines only ``write_request`` and ``read_response`` as public methods, the two methods of
``Client``.  ``ser`` is an instance attribute, like the upstream's ``serial.Serial``.  Nothing here talks to a
device, and this class never derives from ``Client``.
"""


class _FakeSerial:
    """The minimal serial object the e-stop closes (a stand-in for pyserial's Serial)."""

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeClient:
    def __init__(self, **_options):
        self.ser = _FakeSerial()
        self.commands = []
        self._pending = []
        self._replies = {
            "STA": "305419896",  # placeholder test data (the upstream range is 0 to 0xFFFFFFFF)
            "TYP": "abc",        # placeholder test data (the upstream returns a, b, c or abc)
            "VOL": "12",         # placeholder test data (the upstream range is 0 to 220)
            "TMP": "24",         # placeholder test data (the upstream range is 0 to 85)
            "CUR": "100",        # placeholder test data (the upstream range is 0 to 2000)
        }

    def write_request(self, command):
        """Record a request and queue the reply the simulated instrument would send."""
        self.commands.append(command)
        self._pending.append(self._reply(command))

    def read_response(self):
        """Return the oldest queued reply, like reading one line from the serial port."""
        if not self._pending:
            raise TimeoutError("no response is pending")
        return self._pending.pop(0)

    def _reply(self, command):
        word = str(command)[0:3]
        try:
            return self._replies[word]
        except KeyError:
            raise ValueError("Unknown command: " + word) from None

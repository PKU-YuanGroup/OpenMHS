"""Fake backend of the Zaber ASCII axis driver: an in-memory stand-in for zaber.serial.ascii:AsciiAxis.

Gate G7: every public method defined here (get_position, get_status, home, move_abs, move_rel, move_vel, stop) is a
method of ``AsciiAxis`` in ``zaber/serial/ascii.py``, with the same signatures.  The clone has no simulator or mock,
so this is an in-memory fake at the level of the upstream methods; it opens no serial port and moves nothing.
``get_position`` returns the reply data as text, like the upstream ``send('get pos').data`` (line 218); the driver
converts it to an integer.  Every number below is test data (# placeholder), not a fact about any device.
"""


class FakeAsciiAxis:
    def __init__(self, **_options):
        self._position = 0              # placeholder: test start position
        self._status = "IDLE"           # placeholder: test start status
        self._speed = 0                 # placeholder: no continuous motion

    def get_position(self):
        return str(self._position)      # placeholder: reply data as text, like AsciiReply.data

    def get_status(self):
        return self._status

    def home(self):
        self._position = 0              # placeholder: test home position
        self._status = "IDLE"
        return None

    def move_abs(self, position, blocking=True):
        self._position = int(position)
        self._status = "IDLE" if blocking else "BUSY"
        return None

    def move_rel(self, distance, blocking=True):
        self._position += int(distance)
        self._status = "IDLE" if blocking else "BUSY"
        return None

    def move_vel(self, speed, blocking=False):
        self._speed = int(speed)
        self._status = "BUSY" if self._speed != 0 else "IDLE"
        if blocking:
            self._status = "IDLE"
        return None

    def stop(self):
        self._speed = 0
        self._status = "IDLE"
        return None

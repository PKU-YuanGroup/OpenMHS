"""Fake backend of the Velmex VXM driver: an in-memory stand-in for XYZMotion:VXM.

Gate G7: every public method defined here is a method of the upstream class (XYZMotion.py:27-220), and the driver
touches nothing else.  The fake keeps the three positions and the three velocities in memory and applies a move to
the positions, so a move is visible to the next position read.  The values are test data, not a recording of a
device; the clone has no simulator and no hardware was available.  Nothing here talks to a device.

The clone can not be imported to build a fake from it: importing XYZMotion.py opens COM4, homes the stage and moves
it (XYZMotion.py:224-236).  This class is therefore written from the lines the driver calls, and the package is
blocked on the missing stop path (RESULT.json).
"""

#: Test start positions in millimetres (placeholder: not a fact of the device).
START_POSITIONS = {"X": 0.0, "Y": 0.0, "Z": 0.0}  # placeholder

#: Test start velocities in steps/s (placeholder: the upstream constructor writes 2000, but this is test data).
START_VELOCITIES = {"X": 2000.0, "Y": 2000.0, "Z": 2000.0}  # placeholder

#: A canned status reply for getresp (placeholder: the clone parses 7 digits after the sign).
READY_REPLY = "X+0000000\r"  # placeholder


class FakeVxm:
    def __init__(self, **_options):
        self._positions = dict(START_POSITIONS)
        self._velocities = dict(START_VELOCITIES)
        self._last_command = None
        self._pending = READY_REPLY  # placeholder

    # -- commands and replies (the driver's move/read paths use the methods below) --------------------------------
    def sendcmd(self, commandString, silent=True):
        self._last_command = commandString

    def getresp(self, silent=True):
        return self._pending

    def waitReady(self, silent=False):
        return None

    # -- position ------------------------------------------------------------------------------------------------
    def getPosition(self, Stage, metric_units=True, english_units=False):
        value = self._positions[Stage]
        if english_units:
            return value / 25.4
        return value

    def getAllPositions(self, metric_units=True, english_units=False):
        if english_units:
            return tuple(self._positions[axis] / 25.4 for axis in ("X", "Y", "Z"))
        return tuple(self._positions[axis] for axis in ("X", "Y", "Z"))

    # -- velocity ------------------------------------------------------------------------------------------------
    def setVelocity(self, Stage, Speed):
        self._velocities[Stage] = float(Speed)

    # -- motion --------------------------------------------------------------------------------------------------
    def moveToZero(self, Stage):
        self._positions[Stage] = 0.0  # placeholder: the reference position

    def move_mm(self, Stage, dist_mm):
        self._positions[Stage] = self._positions[Stage] + float(dist_mm)

    def move_in(self, Stage, dist_in):
        self._positions[Stage] = self._positions[Stage] + float(dist_in) * 25.4

    def home(self):
        for axis in ("X", "Y", "Z"):
            self.moveToZero(axis)

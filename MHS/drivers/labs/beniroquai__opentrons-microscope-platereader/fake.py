"""Fake backend of the NEJE laser 2 package: an in-memory stand-in for pyGraver.

Gate G7: every public method defined here is a method of ``PYTHON.opentrons_neje_laser2_controler:pyGraver`` at
the pinned commit 867f54163da7e8d17db1e6aac0bbdb0105905f22.  The fake keeps the controller state in plain
attributes and records the frame methods the driver calls; it never opens a serial port and never talks to a
device.

The start position, the progress value and the power/idle values are test data, each marked ``# placeholder``.
They are not facts about the machine and are not copied into a Fact or a Limit.
"""

# placeholder: the upstream class starts at the centre of its 490 by 490 area
_START_LOCATION = [245, 245]
# placeholder: an initial carving progress; a real controller reports its own value
_START_PROGRESS = 0


class FakePyGraver:
    def __init__(self, **_options):
        self.location = list(_START_LOCATION)
        self.carvingPercentProgress = _START_PROGRESS
        self.power = None
        self.idle = None
        self.frames = []
        self.stopped = False
        self.paused = False
        self.closed = False

    def moveXY(self, x, y):
        self.location = [x, y]
        self.frames.append(("moveXY", x, y))

    def setPWD(self, p, i):
        self.power, self.idle = p, i
        self.frames.append(("setPWD", p, i))

    def stopCarving(self):
        self.stopped = True
        self.carvingPercentProgress = 0        # placeholder: the model reports no progress after a stop
        self.frames.append(("stopCarving",))

    def pauseCarving(self):
        self.paused = True
        self.frames.append(("pauseCarving",))

    def close(self):
        self.closed = True
        self.frames.append(("close",))

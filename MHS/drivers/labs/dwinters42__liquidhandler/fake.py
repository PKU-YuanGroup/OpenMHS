"""Fake backend of the liquidhandler driver: an in-memory stand-in for liquidhandler:Robot.

Gate G7: every public method defined here is a method of the upstream ``Robot`` class in the clone's
``liquidhandler.py`` (shown in the docstring of each group).  The fake keeps the same state attributes the upstream
constructor sets: ``armaddr``, ``armlimits``, ``pumpaddr``, ``syringecontents``, ``locations`` and ``curpos``, plus
the serial object ``s`` the upstream opens (here a closed-marker stand-in, never a port).  The methods mirror the
upstream checks and do not add a stop method the clone does not have.  Numbers are test data, not device facts:
every starting value below is a ``# placeholder``.

The method names and command semantics mirror ``liquidhandler.py``, copyright (c) 2010,2011 Daniel Winters
<daniel@tydirium.org>, whose permission notice appears in ``native.py``.
"""


class _FakeSerial:
    """The serial port the upstream constructor opens; the driver only closes it."""

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeLiquidhandler:
    def __init__(self, **_options):
        # The upstream constructor's attributes (liquidhandler.py:32-45).
        self.armaddr = [18, 28]                     # placeholder
        self.armlimits = [[2500, 1000, 1200, 10], [1600, 1000, 1200, 10]]  # placeholder
        self.pumpaddr = [11]                        # placeholder
        self.syringecontents = [1000]               # placeholder: an in-memory starting volume
        self.locations = {}
        self.curpos = [[0, 0, 0], [0, 0, 0]]        # placeholder
        self.s = _FakeSerial()
        self.last_pump = None                       # placeholder: test observation only

    # -- arm commands (liquidhandler.py:77-103) ---------------------------------------------------------------
    def AddPosition(self, name, coordinates):
        self.locations[name] = list(coordinates)

    def Goto(self, location, armnum=1):
        if location not in self.locations:
            raise ValueError("No such location!")
        self.Move(self.locations[location][:], armnum)

    def Move(self, pos=[0, 0, 0], armnum=1):
        self.curpos[armnum - 1] = [int(pos[0]), int(pos[1]), int(pos[2])]

    def MoveAxis(self, axis=0, pos=10, armnum=1):
        self.curpos[armnum - 1][axis] = pos

    def ShowPosition(self, armnum=1):
        return list(self.curpos[armnum - 1])

    # -- pump commands (liquidhandler.py:107-147) -------------------------------------------------------------
    def Dispense(self, units, speed=10, pump=1):
        if int(units) > self.syringecontents[pump - 1]:
            raise ValueError("Not enough liquid in syringe!")
        self.syringecontents[pump - 1] = self.syringecontents[pump - 1] - int(units)

    def Draw(self, units, source="bottle", speed=10, pump=1):
        if source == "bottle":
            direction = "in"
        elif source == "sample":
            direction = "out"
        else:
            raise ValueError("Source must be either 'bottle' or 'sample'!")
        if self.syringecontents[pump - 1] + units > 2000:
            raise ValueError("Syringe can only contain up to 2000 units!")  # the upstream check, not a test value
        self.syringecontents[pump - 1] = self.syringecontents[pump - 1] + int(units)
        self.last_pump = (pump, speed, self.syringecontents[pump - 1], direction)

    def Pump(self, pump, speed, position, direction):
        if int(speed) < 0 or int(speed) > 20:          # the upstream check, not a test value
            raise ValueError("Pump speed must be between 0 and 20!")
        if int(position) < 0 or int(position) > 2000:  # the upstream check, not a test value
            raise ValueError("Pump position must be between 0 and 2000!")
        if direction not in ("in", "out"):
            raise ValueError("Pump direction must be 'in' or 'out'!")
        self.last_pump = (pump, int(speed), int(position), direction)

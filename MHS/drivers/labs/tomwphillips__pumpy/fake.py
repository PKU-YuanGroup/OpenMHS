"""Fake backend of the pumpy driver: an in-memory stand-in for the upstream Harvard PHD 2000 object.

Gate G7: every public method defined here exists on ``pumpy:PHD2000`` or its base ``Pump`` in the clone
(setdiameter, setflowrate, settargetvolume, infuse, withdraw, stop, waituntiltarget), and the attributes the driver
reaches (``name``, ``serialcon``, ``address``, ``diameter``, ``flowrate``, ``targetvolume``) are the ones the upstream
__init__ sets (``pumpy.py:48-54``).  The starting values are test data, not facts about a pump: every one is marked
``# placeholder``.  The methods keep the values the driver writes and never move them by themselves, so reading the
state twice gives the same state.  Nothing here talks to a device or reproduces the serial protocol.
"""


class _FakeChain:
    """The serial chain the upstream object keeps as ``serialcon``; the driver's teardown only closes it."""

    def __init__(self):
        self.port = "fake"          # placeholder
        self.is_open = True

    def close(self):
        self.is_open = False


class FakePHD2000:
    def __init__(self, **_options):
        self.name = _options.get("name", "PHD2000")        # placeholder
        self.serialcon = _FakeChain()
        self.address = "{0:02.0f}".format(int(_options.get("address", 0)))  # placeholder
        self.diameter = 10.0        # placeholder
        self.flowrate = 1000.0      # placeholder
        self.targetvolume = 100.0   # placeholder

    def setdiameter(self, diameter):
        self.diameter = float(diameter)

    def setflowrate(self, flowrate):
        self.flowrate = float(flowrate)

    def settargetvolume(self, targetvolume):
        self.targetvolume = float(targetvolume)

    def infuse(self):
        pass

    def withdraw(self):
        pass

    def stop(self):
        pass

    def waituntiltarget(self):
        pass

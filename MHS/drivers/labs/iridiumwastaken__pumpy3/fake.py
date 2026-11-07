"""Fake backend of the pumpy3 driver: an in-memory stand-in for the upstream ``pump:Pump2000`` object.

Gate G7: every public method here exists on ``pump:Pump2000`` (or its base ``Pump``) in the clone -- setdiameter,
settargetvolume, set_rate, getdiameter, getrate, gettargetvolume, ivolume, run, rev and stop.  The attributes the
driver reaches, ``state`` and ``serialcon``, are the ones the upstream __init__ sets (``pump.py:526-531``), and
``serialcon`` has the ``close`` the driver's teardown calls.  The values are test data, not facts about a pump: every
one is marked ``# placeholder``.  The methods keep the values the driver writes and never move them by themselves, so
reading the state twice gives the same state.  Nothing here talks to a device or reproduces the serial protocol.
"""


class _FakeChain:
    """The serial chain the upstream object keeps as ``serialcon``; the driver's teardown only closes it."""

    def __init__(self):
        self.port = "fake"          # placeholder
        self.is_open = True

    def close(self):
        self.is_open = False


class FakePump2000:
    def __init__(self, **_options):
        self.name = _options.get("name", "FakePHD2000")                         # placeholder
        self.serialcon = _FakeChain()
        self.address = "{0:02.0f}".format(int(_options.get("address", 0)))       # placeholder
        self.diameter = 10.0        # placeholder
        self.flowrate = 1000.0      # placeholder
        self.targetvolume = 2.0     # placeholder
        self.state = "idle"
        self._rate_units = "u/m"    # placeholder
        self._infused = 0.0         # placeholder

    def setdiameter(self, diameter):
        self.diameter = float(diameter)

    def settargetvolume(self, volume):
        self.targetvolume = float(volume)

    def set_rate(self, flowrate, units):
        self.flowrate = float(flowrate)
        self._rate_units = str(units)

    def getdiameter(self):
        return f"{self.diameter} mm"

    def getrate(self):
        return f"{self.flowrate} {self._rate_units}"

    def gettargetvolume(self):
        return f"{self.targetvolume} ml"

    def ivolume(self):
        return f"{self._infused} ml"

    def run(self):
        self.state = "infusing"

    def rev(self):
        self.state = "withdrawing"

    def stop(self):
        self.state = "idle"

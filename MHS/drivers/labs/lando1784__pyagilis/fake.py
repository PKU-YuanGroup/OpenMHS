"""Fake backend of the pyagilis driver: an in-memory stand-in for ``pyagilis.controller:AGUC2``.

Gate G7: every public method defined on :class:`FakeAGUC2` exists on AGUC2 in the clone, and the attributes the
driver reaches (``axis``, ``aliases`` and ``port``) are set in the upstream ``__init__`` or by ``addAxis``.  The
per-axis methods mirror ``pyagilis.channel.Axis``.  The counters, limit-switch replies and starting operations are
test data, not device facts: every such number is marked ``# placeholder``.  Nothing here talks to a device.
"""


class _FakePort:
    """The serial object AGUC2 owns (``AGPort``): the driver only closes it."""

    def __init__(self):
        self._open = True

    def close(self):
        self._open = False


class _FakeAxis:
    """Stand-in for ``pyagilis.channel.Axis``: the methods the driver calls, with the same command semantics."""

    def __init__(self, controller, name, step_amp):
        self.controller = controller
        self.name = name
        self.stepAmp = str(step_amp)
        self._last_op = "opened"       # placeholder: the upstream __init__ records this at power-on

    def whatDidIdo(self):
        return self._last_op

    def stop(self):
        self._last_op = "stopped"

    def amIatMyLimit(self):
        return False                    # placeholder: the fake has no limit switches

    def queryCounter(self):
        return self.controller._positions[self.name]

    def resetCounter(self):
        self.controller._positions[self.name] = 0
        self._last_op = "reset"

    def jog(self, steps=0):
        if steps == 0:
            return False
        self._last_op = "jogged: " + str(steps)
        self.controller._positions[self.name] += int(steps)
        return None


class FakeAGUC2:
    """A two-axis agUC2 with the public methods of the upstream controller class."""

    def __init__(self, **_options):
        self.port = _FakePort()
        self.axis = {}
        self.aliases = ["X", "Y"]       # placeholder: the controller's alias and amplitude options
        self._positions = {"1": 0, "2": 0}   # placeholder: counters start at zero
        self.addAxis("1", self.aliases[0], 50)   # placeholder: amplitude 50 is test data
        self.addAxis("2", self.aliases[1], 50)   # placeholder: amplitude 50 is test data

    def addAxis(self, name, alias, stepAmp):
        self.axis[alias] = _FakeAxis(self, name, stepAmp)

    def move(self, d1, d2):
        self.axis[self.aliases[0]].jog(d1)
        self.axis[self.aliases[1]].jog(d2)

    def goToZero(self):
        steps1 = self.axis[self.aliases[0]].queryCounter()
        steps2 = self.axis[self.aliases[1]].queryCounter()
        self.axis[self.aliases[0]].jog(-1 * steps1)
        self.axis[self.aliases[1]].jog(-1 * steps2)

    def setZero(self):
        self.axis[self.aliases[0]].resetCounter()
        self.axis[self.aliases[1]].resetCounter()

    def stop(self):
        for alias in self.aliases:
            self.axis[alias].stop()

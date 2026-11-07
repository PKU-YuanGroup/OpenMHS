"""Fake backend of the pymupump driver: an in-memory stand-in for the upstream Harvard Microliter object.

Gate G7: every public method defined here exists on ``pymupump.pymupump:Microliter`` in the clone (write, read,
readall, query, setdiameter, setflowrate, infuse, withdraw, stop, settargetvolume and waituntiltarget), and the
attributes the driver reaches (``name``, ``serialcon``, ``address``, ``diameter``, ``flowrate``, ``targetvolume``) are
the ones the upstream __init__ sets (``pymupump/pymupump.py:66-75``).  The starting values are test data, not facts
about a pump: every numeric one is marked ``# placeholder``.  The methods keep the values the driver writes and never
move them by themselves, so reading the state twice gives the same state.  Nothing here talks to a device or
reproduces the serial protocol.
"""


class _FakeChain:
    """The serial chain the upstream object keeps as ``serialcon``; the driver's teardown only closes it."""

    def __init__(self):
        self.port = "fake"          # placeholder
        self.is_open = True

    def close(self):
        self.is_open = False


class FakeMicroliter:
    def __init__(self, **_options):
        self.name = _options.get("name", "Microliter")         # placeholder
        self.serialcon = _FakeChain()
        self.address = "{0:02.0f}".format(int(_options.get("address", 0)))  # placeholder
        self.diameter = 1.0         # placeholder
        self.flowrate = 100.0       # placeholder
        self.targetvolume = 100.0   # placeholder
        self._running = False
        self._calls = []

    def write(self, command):
        self._calls.append(("write", command))

    def read(self, bytes=5):
        self._calls.append(("read", bytes))
        return "00:"                # placeholder

    def readall(self, wait=True):
        self._calls.append(("readall", bool(wait)))
        return "00:"                # placeholder

    def query(self, command, ans_len=-1, wait_ans=True):
        self._calls.append(("query", command, int(ans_len), bool(wait_ans)))
        return "00:"                # placeholder

    def setdiameter(self, diameter):
        self.diameter = float(diameter)

    def setflowrate(self, flowrate):
        self.flowrate = float(flowrate)

    def settargetvolume(self, targetvolume):
        self.targetvolume = float(targetvolume)

    def infuse(self):
        self._calls.append(("infuse",))

    def withdraw(self):
        self._calls.append(("withdraw",))

    def stop(self):
        self._calls.append(("stop",))

    def waituntiltarget(self):
        self._running = False

"""Fake backend of the Elveflow OB1 driver: an in-memory stand-in for pycrofluidics.elveob:OB1elve.

Gate G7: every public method defined here exists on ``pycrofluidics.elveob:OB1elve`` (``pycrofluidics/elveob.py``),
and the driver also reads the instance attribute ``insideRemote`` that the upstream __init__ sets
(``pycrofluidics/elveob.py:63``).  The methods copy the upstream guards: a pressure or sensor read and a pressure
write refuse while the remote loop runs, and startRemote/stopRemote refuse when the loop is already in that state.
The pressure and flow values start at zero and move only when the driver writes them; those numbers are test data,
not measurements or limits.
"""

# The upstream _channelCheck accepts 1 to 4 (pycrofluidics/elveob.py:468-469).
_CHANNELS = (1, 2, 3, 4)


class FakeOB1elve:
    def __init__(self, **_options):
        self.insideRemote = False
        self._pressure = [0.0, 0.0, 0.0, 0.0]   # placeholder: starting pressure of channels 1 to 4
        self._flow = [0.0, 0.0, 0.0, 0.0]       # placeholder: starting flow-sensor reading of channels 1 to 4
        self._target = [0.0, 0.0, 0.0, 0.0]     # placeholder: remote target of channels 1 to 4

    def _check(self, channel):
        if channel not in _CHANNELS:
            raise ValueError("Channel choice between 1 and 4")

    def open(self):
        return None

    def close(self):
        if self.insideRemote:
            self.stopRemote()

    def setPressure(self, channel, pressure=0):
        if self.insideRemote:
            raise ValueError("Remote loop is running; only inside loop functions allowed!")
        channel = int(channel)
        self._check(channel)
        self._pressure[channel - 1] = float(pressure)

    def getPressure(self, channel):
        if self.insideRemote:
            raise ValueError("Remote loop is running; only inside loop functions allowed!")
        channel = int(channel)
        self._check(channel)
        return self._pressure[channel - 1]

    def getSensorData(self, channel):
        if self.insideRemote:
            raise ValueError("Remote loop is running; only inside loop functions allowed!")
        channel = int(channel)
        self._check(channel)
        return self._flow[channel - 1]

    def startRemote(self):
        if self.insideRemote:
            raise ValueError("Remote loop is allready running and can thus not be started")
        self.insideRemote = True

    def stopRemote(self):
        if not self.insideRemote:
            raise ValueError("Remote loop is not running and can thus not be stopped")
        self.insideRemote = False

    def remoteGetData(self, channel):
        if not self.insideRemote:
            raise ValueError("Remote loop is not running, use regular getPressure/getSensorData functions")
        channel = int(channel)
        self._check(channel)
        return self._pressure[channel - 1], self._flow[channel - 1]

    def remoteSetTarget(self, channel, target):
        if not self.insideRemote:
            raise ValueError("Remote loop is not running, start it first to use PID-like processes.")
        channel = int(channel)
        self._check(channel)
        self._target[channel - 1] = float(target)

    def getPressureUniversal(self, channel):
        if self.insideRemote:
            return self.remoteGetData(channel)[0]
        return self.getPressure(channel)

    def getFlowUniversal(self, channel):
        if self.insideRemote:
            return self.remoteGetData(channel)[1]
        return self.getSensorData(channel)

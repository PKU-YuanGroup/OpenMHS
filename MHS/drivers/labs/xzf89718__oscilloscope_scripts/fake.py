"""Fake backend of the TBS2000B driver: an in-memory stand-in for the upstream ``Oscilloscope`` class.

Gate G7: every public method of :class:`FakeOscilloscope` exists on
``Tektronix_TBS2000B_control.oscilloscope_control:Oscilloscope`` -- ``SetChannel`` (146-172), ``MeasureFreq``
(106-114), ``MeasureAmpl`` (116-124), ``MeasureHigh`` (126-134) and ``Close`` (178-180).  ``MeasureLow`` is absent
because the upstream implementation is malformed (136-144) and the driver does not call it.  The fake keeps the same
reply shape as the upstream methods: a dict keyed by the channel argument, with the value as a string reply.

Every number below is test data of this fake, not a fact or a limit of the instrument.  Nothing here talks to a
device.
"""

# placeholder: the fake's measurement replies; test data only, never a Fact or a Limit.
_REPLIES = {
    "frequency": {"CH1": "1000.0", "CH2": "2500.0", "CH3": "5000.0", "CH4": "10000.0"},
    "amplitude": {"CH1": "1.0", "CH2": "0.5", "CH3": "2.0", "CH4": "0.25"},
    "high": {"CH1": "0.5", "CH2": "0.25", "CH3": "1.0", "CH4": "0.125"},
}

#: The channels SetChannel accepts (oscilloscope_control.py:156-167).
_CHANNELS = ("CH1", "CH2", "CH3", "CH4")


class _FakeResource:
    """The object the upstream keeps in ``self.inst``; the driver only reaches it through ``Close``."""

    def __init__(self):
        self.written = []
        self.closed = False

    def write(self, line):
        self.written.append(line)

    def close(self):
        self.closed = True


class _FakeResourceManager:
    """The object the upstream keeps in ``self.resource_manager``; the driver only reaches it through ``Close``."""

    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeOscilloscope:
    def __init__(self, **_options):
        self.resource_manager = _FakeResourceManager()
        self.inst = _FakeResource()
        self._channel = "DEFAULT"
        self.closed = False
        self.calls = []

    def SetChannel(self, channel):
        self.calls.append(("SetChannel", channel))
        if channel == "DEFAULT":
            return
        if channel not in _CHANNELS:
            raise Exception("Oscilloscope::ERROR Sampling channel not exist. Example:CH1,CH2,CH3,CH4")
        self._channel = channel

    def MeasureFreq(self, measure_channels="CH1"):
        return self._measure("frequency", "MeasureFreq", measure_channels)

    def MeasureAmpl(self, measure_channels="CH1"):
        return self._measure("amplitude", "MeasureAmpl", measure_channels)

    def MeasureHigh(self, measure_channels="CH1"):
        return self._measure("high", "MeasureHigh", measure_channels)

    def _measure(self, table, name, measure_channels):
        self.calls.append((name, measure_channels))
        reply = {}
        for channel in measure_channels.split(","):
            self.SetChannel(channel)
            reply[channel] = _REPLIES[table][channel]
        return reply

    def Close(self):
        self.calls.append(("Close", None))
        self.inst.close()
        self.resource_manager.close()
        self.closed = True

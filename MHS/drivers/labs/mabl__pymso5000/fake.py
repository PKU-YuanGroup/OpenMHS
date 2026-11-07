"""Fake backend of the MSO5000 driver: an in-memory stand-in for pymso5000.scope:Scope.

Gate G7: every public method defined here is a method of ``Scope`` in the clone (src/pymso5000/scope.py): info,
trigger_status, run, stop, get_acquisition, set_acquisition, get_channel, set_channel, get_timebase, set_timebase,
execute and close.  The returned state objects are plain dataclasses with the attributes the upstream models carry
(api/models.py, api/measurement_models.py), so a write is visible to the next read.

Every number below is test data, not a fact from the clone or a record of an instrument: each is marked
``# placeholder``.  The clone has no simulator for this class, so this file is an in-memory stand-in, not a
transcript.  Nothing here talks to a device.
"""

from dataclasses import dataclass, field

#: The only channel this package serves; the upstream class accepts 1 to 4 (parameters.py:5).
CHANNEL = 1  # placeholder

#: Test values for the acquisition state.
_SAMPLE_RATE = 1000000.0  # placeholder
_MEMORY_POINTS = {  # placeholder
    "AUTO": 1000000,  # placeholder
    "1k": 1000,  # placeholder
    "10k": 10000,  # placeholder
    "100k": 100000,  # placeholder
    "1M": 1000000,  # placeholder
    "10M": 10000000,  # placeholder
    "25M": 25000000,  # placeholder
    "50M": 50000000,  # placeholder
    "100M": 100000000,  # placeholder
    "200M": 200000000,  # placeholder
}

#: Test measurement values by item; an unknown item gets the fallback.
_MEASUREMENTS = {  # placeholder
    "VMAX": 1.25,  # placeholder
    "VMIN": -1.25,  # placeholder
    "VPP": 2.5,  # placeholder
    "FREQuency": 1000.0,  # placeholder
    "PERiod": 0.001,  # placeholder
    "PDUTy": 50.0,  # placeholder
}
_FALLBACK_MEASUREMENT = 0.5  # placeholder


@dataclass
class _Info:
    idn: str


@dataclass
class _Acquisition:
    trigger_status: str
    acquisition_type: str
    averages: int
    sample_rate_sa_s: float
    memory_depth_points: int


@dataclass
class _Channel:
    channel: int
    enabled: bool
    scale_per_div: float
    offset: float
    unit: str
    coupling: str
    probe_ratio: float
    bandwidth_limit: str


@dataclass
class _Timebase:
    mode: str
    scale_s_per_div: float
    offset_s: float


@dataclass
class _Outcome:
    state: object
    adjustments: list = field(default_factory=list)


class FakeScope:
    """A fresh in-memory scope per endpoint; all values are placeholders, not a recording."""

    def __init__(self, **_options):
        self._trig = "RUN"  # placeholder
        self._acquire_type = "NORMal"  # placeholder
        self._averages = 64  # placeholder
        self._memory_depth = "AUTO"  # placeholder
        self._memory_points = _MEMORY_POINTS["AUTO"]  # placeholder
        self._channel = _Channel(  # placeholder
            channel=CHANNEL,  # placeholder
            enabled=True,  # placeholder
            scale_per_div=0.5,  # placeholder
            offset=0.0,  # placeholder
            unit="V",  # placeholder
            coupling="DC",  # placeholder
            probe_ratio=10.0,  # placeholder
            bandwidth_limit="20M",  # placeholder
        )
        self._timebase = _Timebase(mode="YT", scale_s_per_div=0.0001, offset_s=0.0)  # placeholder
        self.closed = False

    # -- identity and run state ---------------------------------------------------------------------------------
    def info(self, *, refresh=False):
        return _Info("RIGOL TECHNOLOGIES,MSO5074,FAKE000000,00.01.00")  # placeholder

    def trigger_status(self):
        return self._trig

    def run(self):
        self._trig = "RUN"  # placeholder

    def stop(self):
        self._trig = "STOP"  # placeholder

    # -- acquisition --------------------------------------------------------------------------------------------
    def get_acquisition(self):
        return _Acquisition(
            trigger_status=self._trig,
            acquisition_type=self._acquire_type,
            averages=self._averages,
            sample_rate_sa_s=_SAMPLE_RATE,
            memory_depth_points=self._memory_points,
        )

    def set_acquisition(self, *, acquisition_type=None, averages=None, memory_depth=None):
        if acquisition_type is not None:
            self._acquire_type = acquisition_type
        if averages is not None:
            self._averages = int(averages)
        if memory_depth is not None:
            if memory_depth not in _MEMORY_POINTS:
                raise ValueError(f"unsupported memory depth {memory_depth!r}")  # placeholder text
            self._memory_depth = memory_depth
            self._memory_points = _MEMORY_POINTS[memory_depth]
        return self.get_acquisition()

    # -- one analog channel -------------------------------------------------------------------------------------
    def get_channel(self, channel):
        self._require_channel(channel)
        return self._channel

    def set_channel(self, channel, *, enabled=None, probe_ratio=None, coupling=None, bandwidth_limit=None,
                    scale_per_div=None, offset=None):
        self._require_channel(channel)
        state = self._channel
        if enabled is not None:
            state.enabled = bool(enabled)
        if probe_ratio is not None:
            state.probe_ratio = float(probe_ratio)
        if coupling is not None:
            state.coupling = str(coupling)
        if bandwidth_limit is not None:
            state.bandwidth_limit = str(bandwidth_limit)
        if scale_per_div is not None:
            state.scale_per_div = float(scale_per_div)
        if offset is not None:
            state.offset = float(offset)
        return _Outcome(state=state, adjustments=[])

    @staticmethod
    def _require_channel(channel):
        if int(channel) != CHANNEL:
            raise ValueError(f"this package serves channel {CHANNEL}, got {channel!r}")  # placeholder text

    # -- timebase -----------------------------------------------------------------------------------------------
    def get_timebase(self):
        return self._timebase

    def set_timebase(self, scale_s_per_div=None, offset_s=None):
        if scale_s_per_div is not None:
            self._timebase.scale_s_per_div = float(scale_s_per_div)
        if offset_s is not None:
            self._timebase.offset_s = float(offset_s)
        return _Outcome(state=self._timebase, adjustments=[])

    # -- generic command path -----------------------------------------------------------------------------------
    def execute(self, command, args=(), *, raw_tmc=False):
        if command != "MEASure:ITEM?":
            raise ValueError(f"the fake does not answer {command!r}")  # placeholder text
        if len(args) != 2:
            raise ValueError("MEASure:ITEM? takes an item and a source")  # placeholder text
        return _MEASUREMENTS.get(str(args[0]), _FALLBACK_MEASUREMENT)

    def close(self):
        self.closed = True

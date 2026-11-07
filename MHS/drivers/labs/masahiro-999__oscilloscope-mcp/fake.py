"""Fake backend of the RIGOL DS1000Z driver: an in-memory stand-in for the upstream class.

Gate G7: every public method here exists on
``oscilloscope_mcp.instruments.rigol_ds1000z:RigolDs1000z`` (the upstream class names them
``idn``, ``active_channel_count``, ``get_channel``, ``set_channel``, ``get_timebase``,
``set_timebase``, ``get_acquire``, ``set_acquire``, ``get_trigger``, ``set_trigger``,
``measure`` and ``run_control``).  The setup arguments are the attributes the upstream
setters read; the state results mirror the upstream dataclasses.

Every number and string in this file is test data, marked ``# placeholder``.  Nothing here
is a fact about any instrument, and nothing here talks to a device.  The values never move
by themselves, except that ``run_control`` changes the trigger status and setters apply
what they are given.
"""

#: Canned automatic measurements; every value is test data.  # placeholder
_MEASUREMENTS = {
    "VMAX": 3.31,          # placeholder
    "VMIN": -2.12,         # placeholder
    "VPP": 5.43,           # placeholder
    "VTOP": 3.28,          # placeholder
    "VBASE": -2.08,        # placeholder
    "VAMP": 5.36,          # placeholder
    "VAVG": 0.52,          # placeholder
    "VRMS": 1.91,          # placeholder
    "OVERSHOOT": 0.021,    # placeholder
    "PRESHOOT": 0.017,     # placeholder
    "PERIOD": 1.0e-3,      # placeholder
    "FREQUENCY": 1.0e3,    # placeholder
    "RTIME": 2.5e-6,       # placeholder
    "FTIME": 2.7e-6,       # placeholder
    "PWIDTH": 4.9e-4,      # placeholder
    "NWIDTH": 5.1e-4,      # placeholder
    "PDUTY": 49.0,         # placeholder
    "NDUTY": 51.0,         # placeholder
    "RDELAY": 2.5e-8,      # placeholder
    "FDELAY": 2.6e-8,      # placeholder
    "RPHASE": 9.0,         # placeholder
    "FPHASE": -9.0,        # placeholder
}

#: Trigger status after each run-control action; every value is test data.  # placeholder
_STATUS_AFTER = {
    "RUN": "RUN",          # placeholder
    "STOP": "STOP",        # placeholder
    "SINGLE": "WAIT",      # placeholder
    "FORCE": "RUN",        # placeholder
}


class _ChannelState:
    """Stand-in for the upstream ChannelState dataclass (private to the fake)."""

    def __init__(self, channel, scale_v_per_div, offset_v, coupling, display, probe,
                 bw_limit, invert, units):
        self.channel = channel
        self.scale_v_per_div = scale_v_per_div
        self.offset_v = offset_v
        self.coupling = coupling
        self.display = display
        self.probe = probe
        self.bw_limit = bw_limit
        self.invert = invert
        self.units = units


class _TimebaseState:
    def __init__(self, s_per_div, offset_s, mode):
        self.s_per_div = s_per_div
        self.offset_s = offset_s
        self.mode = mode


class _AcquireState:
    def __init__(self, type, averages, memory_depth, sample_rate):
        self.type = type
        self.averages = averages
        self.memory_depth = memory_depth
        self.sample_rate = sample_rate


class _TriggerState:
    def __init__(self, mode, status, sweep, coupling, holdoff_s):
        self.mode = mode
        self.status = status
        self.sweep = sweep
        self.coupling = coupling
        self.holdoff_s = holdoff_s
        self.params = {}


class FakeRigolDs1000z:
    def __init__(self, **_options):
        self._identity = "RIGOL TECHNOLOGIES,DS1104Z,FAKE0001,00.04.04"  # placeholder
        self._channels = {
            1: _ChannelState(1, 1.0, 0.0, "DC", True, 10.0, "OFF", False, "VOLTage"),   # placeholder
            2: _ChannelState(2, 1.0, 0.0, "DC", False, 10.0, "OFF", False, "VOLTage"),  # placeholder
            3: _ChannelState(3, 1.0, 0.0, "DC", False, 10.0, "OFF", False, "VOLTage"),  # placeholder
            4: _ChannelState(4, 1.0, 0.0, "DC", False, 10.0, "OFF", False, "VOLTage"),  # placeholder
        }
        self._timebase = _TimebaseState(1.0e-3, 0.0, "MAIN")                 # placeholder
        self._acquire = _AcquireState("NORMal", 2, "AUTO", 1.0e9)            # placeholder
        self._trigger = _TriggerState("EDGE", "RUN", "AUTO", "DC", 8.0e-9)   # placeholder

    # -- identification ---------------------------------------------------------------------------------------
    def idn(self):
        return self._identity

    def active_channel_count(self):
        return sum(1 for state in self._channels.values() if state.display)

    # -- vertical ---------------------------------------------------------------------------------------------
    def get_channel(self, channel):
        try:
            return self._channels[int(channel)]
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"channel {channel!r} is not available") from None

    def set_channel(self, setup):
        state = self.get_channel(setup.channel)
        if setup.probe is not None:
            state.probe = float(setup.probe)
        if setup.coupling is not None:
            state.coupling = str(setup.coupling)
        if setup.scale_v_per_div is not None:
            state.scale_v_per_div = float(setup.scale_v_per_div)
        if setup.offset_v is not None:
            state.offset_v = float(setup.offset_v)
        if setup.display is not None:
            state.display = bool(setup.display)
        return state

    # -- horizontal -------------------------------------------------------------------------------------------
    def get_timebase(self):
        return self._timebase

    def set_timebase(self, setup):
        if setup.mode is not None:
            self._timebase.mode = str(setup.mode)
        if setup.s_per_div is not None:
            self._timebase.s_per_div = float(setup.s_per_div)
        if setup.offset_s is not None:
            self._timebase.offset_s = float(setup.offset_s)
        return self._timebase

    # -- acquisition ------------------------------------------------------------------------------------------
    def get_acquire(self):
        return self._acquire

    def set_acquire(self, setup):
        if setup.type is not None:
            self._acquire.type = str(setup.type)
        if setup.averages is not None:
            self._acquire.averages = int(setup.averages)
        if setup.memory_depth is not None:
            self._acquire.memory_depth = setup.memory_depth
        return self._acquire

    # -- trigger ----------------------------------------------------------------------------------------------
    def get_trigger(self):
        return self._trigger

    def set_trigger(self, setup):
        if setup.mode is not None:
            self._trigger.mode = str(setup.mode)
        if setup.sweep is not None:
            self._trigger.sweep = str(setup.sweep)
        if setup.coupling is not None:
            self._trigger.coupling = str(setup.coupling)
        if setup.holdoff_s is not None:
            self._trigger.holdoff_s = float(setup.holdoff_s)
        return self._trigger

    def run_control(self, action):
        name = str(action).strip().upper()
        if name not in _STATUS_AFTER:
            raise ValueError(f"unknown run control action {action!r}")
        self._trigger.status = _STATUS_AFTER[name]
        return name

    # -- measurements -----------------------------------------------------------------------------------------
    def measure(self, items, source="CHAN1", source2=None):
        if str(source).strip().upper() not in ("CHAN1", "CHAN2", "CHAN3", "CHAN4"):
            raise ValueError(f"measurement source {source!r} is not available")
        if source2 is not None and str(source2).strip().upper() not in ("CHAN1", "CHAN2", "CHAN3", "CHAN4"):
            raise ValueError(f"measurement source {source2!r} is not available")
        return {str(item): _MEASUREMENTS.get(str(item)) for item in items}

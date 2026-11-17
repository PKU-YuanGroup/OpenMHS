"""Fake backend of the RIGOL oscilloscope driver: an in-memory stand-in for ScopeDriver.

Gate G7: every public method defined here is a method of
``rigol_oscilloscope_mcp.driver.scope:ScopeDriver`` (scope.py:836): identify, the channel, timebase and trigger
readers, the channel and timebase setters, the trigger configurator, the scalar measurement and run/stop.  State
lives in private attributes, so the fake surface is the upstream method surface.  The upstream has no simulator
for this class, so this file is an in-memory stand-in, not a recording of a session.

Every string and number below is test data, not a fact from the clone or a record of an instrument: each is marked
``# placeholder``.  Nothing here talks to a device.
"""


class _Idn:
    def __init__(self, manufacturer, model, serial, firmware):
        self.manufacturer = manufacturer
        self.model = model
        self.serial = serial
        self.firmware = firmware


class _ChannelState:
    def __init__(self, channel, enabled, scale_v_per_div, offset_v, coupling, impedance, probe_ratio,
                 bandwidth_limit):
        self.channel = channel
        self.enabled = enabled
        self.scale_v_per_div = scale_v_per_div
        self.offset_v = offset_v
        self.coupling = coupling
        self.impedance = impedance
        self.probe_ratio = probe_ratio
        self.bandwidth_limit = bandwidth_limit


class _TimebaseState:
    def __init__(self, scale_s_per_div, position_s, sample_rate_sa_per_s, memory_depth):
        self.scale_s_per_div = scale_s_per_div
        self.position_s = position_s
        self.sample_rate_sa_per_s = sample_rate_sa_per_s
        self.memory_depth = memory_depth


class _TriggerState:
    def __init__(self, type, source, level_v, slope, sweep_mode, status, settings):
        self.type = type
        self.source = source
        self.level_v = level_v
        self.slope = slope
        self.sweep_mode = sweep_mode
        self.status = status
        self.settings = settings


class _MeasurementResult:
    def __init__(self, name, key, value, quality):
        self.name = name
        self.key = key
        self.value = value
        self.quality = quality


class FakeScopeDriver:
    """A fresh in-memory oscilloscope per endpoint; all starting values are placeholders."""

    def __init__(self, **_options):
        self._channel = {
            "channel": "CH1",                 # placeholder
            "enabled": True,                  # placeholder
            "scale_v_per_div": 0.5,           # placeholder
            "offset_v": 0.0,                  # placeholder
            "coupling": "DC",                 # placeholder
            "impedance": "1M",                # placeholder
            "probe_ratio": 10.0,              # placeholder
            "bandwidth_limit": False,         # placeholder
        }
        self._timebase = {"scale_s_per_div": 0.0002, "position_s": 0.0}  # placeholder
        self._trigger = {
            "type": "edge",                   # placeholder
            "source": "CH1",                  # placeholder
            "level_v": 0.0,                   # placeholder
            "slope": "rising",                # placeholder
            "sweep_mode": "auto",             # placeholder
            "status": "STOP",                 # placeholder
        }
        self._measurements = {
            "frequency": (1000.0, "frequency_hz"),   # placeholder
            "period": (0.001, "period_s"),           # placeholder
            "vpp": (2.5, "vpp_v"),                   # placeholder
            "vmax": (1.5, "vmax_v"),                 # placeholder
            "vmin": (-1.0, "vmin_v"),                # placeholder
        }

    # -- identity ------------------------------------------------------------------------------------------------
    def identify(self):
        return _Idn("RIGOL TECHNOLOGIES", "FAKE-SCOPE", "FAKE000000", "00.00.00")  # placeholder

    # -- channel -------------------------------------------------------------------------------------------------
    def get_channel(self, channel):
        return _ChannelState(
            self._channel["channel"], self._channel["enabled"], self._channel["scale_v_per_div"],
            self._channel["offset_v"], self._channel["coupling"], self._channel["impedance"],
            self._channel["probe_ratio"], self._channel["bandwidth_limit"],
        )

    def set_channel_enabled(self, channel, enabled):
        self._channel["enabled"] = bool(enabled)
        return self._channel["enabled"]

    def set_channel_scale(self, channel, v_per_div):
        self._channel["scale_v_per_div"] = float(v_per_div)
        return self._channel["scale_v_per_div"]

    def set_channel_offset(self, channel, offset_v):
        self._channel["offset_v"] = float(offset_v)
        return self._channel["offset_v"]

    def set_channel_coupling(self, channel, coupling):
        self._channel["coupling"] = str(coupling)
        return self._channel["coupling"]

    # -- timebase ------------------------------------------------------------------------------------------------
    def get_timebase(self):
        return _TimebaseState(self._timebase["scale_s_per_div"], self._timebase["position_s"], None, None)

    def set_timebase_scale(self, s_per_div):
        self._timebase["scale_s_per_div"] = float(s_per_div)
        return self._timebase["scale_s_per_div"]

    def set_timebase_position(self, position_s):
        self._timebase["position_s"] = float(position_s)
        return self._timebase["position_s"]

    # -- trigger -------------------------------------------------------------------------------------------------
    def get_trigger(self):
        return _TriggerState(
            self._trigger["type"], self._trigger["source"], self._trigger["level_v"],
            self._trigger["slope"], self._trigger["sweep_mode"], self._trigger["status"],
            {"source": self._trigger["source"], "level_v": self._trigger["level_v"],
             "slope": self._trigger["slope"]},
        )

    def get_trigger_status(self):
        return self._trigger["status"]

    def configure_trigger(self, type=None, source=None, level_v=None, slope=None, sweep_mode=None,
                          holdoff_s=None, settings=None):
        if type is not None:
            self._trigger["type"] = str(type)
        if source is not None:
            self._trigger["source"] = str(source)
        if level_v is not None:
            self._trigger["level_v"] = float(level_v)
        if slope is not None:
            self._trigger["slope"] = str(slope)
        if sweep_mode is not None:
            self._trigger["sweep_mode"] = str(sweep_mode)
        return {"type": self._trigger["type"], "source": self._trigger["source"],
                "level_v": self._trigger["level_v"], "slope": self._trigger["slope"],
                "sweep_mode": self._trigger["sweep_mode"]}

    # -- measurement and acquisition -----------------------------------------------------------------------------
    def measure(self, channel, names, channel_b=None):
        results = []
        for name in names:
            value, key = self._measurements[str(name)]
            results.append(_MeasurementResult(str(name), key, value, "valid"))
        return results

    def run(self):
        self._trigger["status"] = "TD"   # placeholder

    def stop(self):
        self._trigger["status"] = "STOP"  # placeholder

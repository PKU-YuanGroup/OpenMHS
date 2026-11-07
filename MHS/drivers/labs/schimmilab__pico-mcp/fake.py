"""Fake backend of the PicoScope driver: an in-memory stand-in for pico_mcp.scope:Scope.

Gate G7: every public method and property defined here exists on ``Scope`` in the clone
(src/pico_mcp/scope.py): ``connected``, ``connect``, ``disconnect``, ``info``, ``set_channel``,
``set_signal_generator``, ``stop_signal_generator`` and ``capture_block``.  The state attributes carry the names of
the upstream dataclass fields (``handle``, ``resolution_bits``, ``max_adc``, ``variant``, ``serial``, ``channels``)
and the per-channel objects carry the upstream ``ChannelState`` members (``enabled``, ``coupling``,
``range_volts``).

The clone has no simulator for this class, so this file is an in-memory stand-in, not a recording of a session.
Every number and string below is test data, not a fact from the clone and not a record of an instrument: each is
marked ``# placeholder``.  Nothing here talks to a device.
"""

from dataclasses import dataclass

_RESOLUTIONS = (8, 12, 14, 15, 16)
_CHANNELS = ("A", "B", "C", "D")
_WAVES = ("sine", "square", "triangle", "ramp_up", "ramp_down", "dc")


@dataclass
class _ChannelState:
    """The members of the upstream ChannelState dataclass (scope.py:91-96)."""

    enabled: bool
    coupling: str
    range_volts: float


class FakeScope:
    """A fresh in-memory oscilloscope per endpoint; all starting values are placeholders."""

    def __init__(self, **_options):
        self.handle = object()                                  # placeholder: the unit is open
        self.resolution_bits = 12                               # placeholder: the upstream default (scope.py:104)
        self.max_adc = 32767                                    # placeholder
        self.variant = "5442B"                                  # placeholder
        self.serial = "FAKE000000"                              # placeholder
        self.channels = {
            "A": _ChannelState(True, "DC", 5.0),                # placeholder
            "B": _ChannelState(True, "DC", 5.0),                # placeholder
            "C": _ChannelState(False, "DC", 5.0),               # placeholder
            "D": _ChannelState(False, "DC", 5.0),               # placeholder
        }
        self._awg = (1000.0, 1.0, "sine", 0.0)                  # placeholder
        self._awg_enabled = False                               # placeholder

    # -- lifecycle ------------------------------------------------------------------------------------------------
    @property
    def connected(self):
        return self.handle is not None

    def connect(self, resolution_bits=12):
        if self.connected:
            return self.info()
        if resolution_bits not in _RESOLUTIONS:
            raise ValueError(f"resolution_bits must be one of {sorted(_RESOLUTIONS)}")
        self.handle = object()                                  # placeholder
        self.resolution_bits = int(resolution_bits)
        self.max_adc = 32767                                    # placeholder
        return self.info()

    def disconnect(self):
        self.handle = None
        self.channels.clear()

    def info(self):
        if not self.connected:
            raise RuntimeError("not connected")
        return {
            "model": "PS5000A",                                 # placeholder
            "variant": self.variant,
            "serial": self.serial,
            "resolution_bits": self.resolution_bits,
            "num_channels": 4,
            "max_adc": self.max_adc,
            "channels": {name: vars(state) for name, state in self.channels.items()},
        }

    # -- configuration --------------------------------------------------------------------------------------------
    def set_channel(self, channel, enabled=True, coupling="DC", range_volts=5.0, analog_offset=0.0):
        if not self.connected:
            raise RuntimeError("not connected; call connect first")
        channel = str(channel).upper()
        if channel not in _CHANNELS:
            raise ValueError(f"channel must be one of {list(_CHANNELS)}")
        coupling = str(coupling).upper()
        self.channels[channel] = _ChannelState(bool(enabled), coupling, float(range_volts))
        return {"channel": channel, "enabled": bool(enabled), "coupling": coupling,
                "range_volts": float(range_volts)}

    def set_signal_generator(self, frequency, amplitude_v=1.0, wave="sine", offset_v=0.0):
        if not self.connected:
            raise RuntimeError("not connected; call connect first")
        wave = str(wave).lower()
        if wave not in _WAVES:
            raise ValueError(f"wave must be one of {list(_WAVES)}")
        self._awg = (float(frequency), float(amplitude_v), wave, float(offset_v))
        self._awg_enabled = True
        return {"frequency_hz": float(frequency), "amplitude_v": float(amplitude_v),
                "offset_v": float(offset_v), "wave": wave}

    def stop_signal_generator(self):
        if not self.connected:
            raise RuntimeError("not connected; call connect first")
        self._awg_enabled = False
        return {"signal_generator": "off"}

    # -- capture --------------------------------------------------------------------------------------------------
    def capture_block(self, samples=5000, timebase=8, trigger_channel=None, trigger_mv=0.0,
                      trigger_direction="rising", max_points=240):
        if not self.connected:
            raise RuntimeError("not connected; call connect first")
        enabled = [name for name, state in self.channels.items() if state.enabled]
        if not enabled:
            raise RuntimeError("no channel enabled; call set_channel first")
        interval_s = 16e-9 * max(1, int(timebase) - 3)          # placeholder
        channels = {}
        for name in enabled:
            channels[name] = {
                "vpp_mv": 1000.0,                               # placeholder
                "vmin_mv": -500.0,                              # placeholder
                "vmax_mv": 500.0,                               # placeholder
                "mean_mv": 0.0,                                 # placeholder
                "rms_mv": 353.553,                              # placeholder
                "frequency_hz": 1000.0,                         # placeholder
                "over_range": False,
            }
        return {
            "samples": int(samples),
            "sample_interval_ns": interval_s * 1e9,
            "sample_rate_hz": 1.0 / interval_s,
            "duration_ms": int(samples) * interval_s * 1e3,
            "timebase": int(timebase),
            "channels": channels,
        }

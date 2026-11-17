"""Fake backend of the JDS6600 driver: an in-memory stand-in for hwtools.drivers.joyit.jds6600:JDS6600.

Gate G7: every public method defined here exists on the upstream class (jds6600.py:119-276).  The fake keeps one
configuration per channel and quantises it the way the upstream driver encodes each field on the wire: frequency
to centi-Hz, amplitude to millivolt, offset to hundredths of a volt around the 1000 code, duty to tenths of a
percent and phase to tenths of a degree (jds6600.py:191-218).  ``read_channel`` returns a copy, like the frozen
pydantic config of the upstream, and ``output_enabled`` reads the same stored flags ``enable_output`` changes.

The starting values are test data, not facts about a device; each is marked ``# placeholder``.  Nothing here
talks to a serial port, and no value moves by itself, so reading twice gives the same state.
"""

from types import SimpleNamespace
import math


def _config(channel, waveform, frequency_hz, amplitude_vpp, offset_v, duty_pct, enabled, arb_slot=None):
    return SimpleNamespace(
        channel=channel,
        waveform=waveform,
        frequency_hz=frequency_hz,
        amplitude_vpp=amplitude_vpp,
        offset_v=offset_v,
        duty_pct=duty_pct,
        enabled=enabled,
        arb_slot=arb_slot,
    )


class FakeJDS6600:
    def __init__(self, **_options):
        self._connected = False
        self._phase_deg = 0.0  # placeholder
        self._channels = {
            1: _config(1, "SINE", 1000.0, 1.0, 0.0, 50.0, False),   # placeholder
            2: _config(2, "SINE", 1000.0, 1.0, 0.0, 50.0, False),   # placeholder
        }

    # -- connection -----------------------------------------------------------
    def connect(self):
        self._connected = True

    def disconnect(self):
        self._connected = False

    def idn(self):
        return "JDS6600-15 SN:00000000"  # placeholder

    # -- configuration --------------------------------------------------------
    def configure_channel(self, config):
        channel = self._check_channel(config.channel)
        for name, low, high in (("frequency_hz", 0, 15e6), ("amplitude_vpp", 0, 20.0),
                                ("offset_v", -9.99, 9.99), ("duty_pct", 0, 100)):
            value = float(getattr(config, name))
            if not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name} is outside the upstream model/device bounds")
        if float(config.frequency_hz) <= 0:
            raise ValueError("frequency_hz must be strictly positive (siggen.py:66)")
        self._channels[channel] = _config(
            channel=channel,
            waveform=str(config.waveform),
            frequency_hz=round(float(config.frequency_hz) * 100) / 100.0,
            amplitude_vpp=round(float(config.amplitude_vpp) * 1000) / 1000.0,
            offset_v=(round(float(config.offset_v) * 100) + 1000 - 1000) / 100.0,
            duty_pct=round(float(config.duty_pct) * 10) / 10.0,
            enabled=bool(config.enabled),
            arb_slot=config.arb_slot,
        )

    def enable_output(self, channel, on):
        channel = self._check_channel(channel)
        self._channels[channel].enabled = bool(on)

    def set_phase_deg(self, degrees):
        if not 0.0 <= float(degrees) <= 360.0:
            raise ValueError("phase must be within 0..360 degrees")
        self._phase_deg = round(float(degrees) * 10) / 10.0

    # -- readback -------------------------------------------------------------
    def read_channel(self, channel):
        channel = self._check_channel(channel)
        current = self._channels[channel]
        if current.frequency_hz <= 0:
            raise ValueError("upstream read_channel validates frequency_hz > 0 (siggen.py:66)")
        return _config(
            current.channel,
            current.waveform,
            current.frequency_hz,
            current.amplitude_vpp,
            current.offset_v,
            current.duty_pct,
            current.enabled, current.arb_slot,
        )

    def output_enabled(self, channel):
        channel = self._check_channel(channel)
        return bool(self._channels[channel].enabled)

    @staticmethod
    def _check_channel(channel):
        value = int(channel)
        if value not in (1, 2):
            raise ValueError(f"the JDS6600 has channels 1 and 2, not {channel!r}")
        return value

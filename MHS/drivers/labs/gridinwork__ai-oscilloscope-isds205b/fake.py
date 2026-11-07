"""Fake backend of the ISDS205B driver: an in-memory stand-in for instrustar.device:Scope.

Gate G7: every public method and property defined here exists on instrustar.device:Scope
(instrustar/device.py:154-363), including the read-back methods the driver calls and the
``is_available`` property.  The fake never talks to a device, never imports the upstream package and never
loads the vendor DLL.  All numeric values below are placeholder test data, not facts, limits or measurements
of a unit; the real values come from the device and the returned arrays are shorter than a real capture.
"""


class _FakeCapture:
    """The attribute container the upstream CaptureResult provides to the driver."""

    def __init__(self, ch1, ch2, sample_rate_hz, requested_kb, actual_kb, elapsed_s, out_of_range, timestamp):
        self.ch1 = ch1
        self.ch2 = ch2
        self.sample_rate_hz = sample_rate_hz
        self.requested_kb = requested_kb
        self.actual_kb = actual_kb
        self.elapsed_s = elapsed_s
        self.out_of_range = out_of_range
        self.timestamp = timestamp


class FakeScope:
    def __init__(self, **_options):
        self._connected = True                                  # placeholder
        self._sample_rate = 1000000                             # placeholder
        self._memory_length_kb = 64                             # placeholder
        self._waveform = 0                                      # placeholder
        self._generator_enabled = False                         # placeholder
        self._trigger = {"mode": 0, "style": 0, "source": 0, "level_mv": 0,
                         "pretrigger_percent": 50}              # placeholder
        self._ranges = {0: (-5000, 5000), 1: (-5000, 5000)}     # placeholder
        self._resolution = {0: 0.00390625, 1: 0.00390625}       # placeholder

    @property
    def is_available(self):
        return self._connected

    def get_sample_rate(self):
        return self._sample_rate

    def set_sample_rate(self, hz):
        self._sample_rate = int(hz)                             # placeholder
        return self._sample_rate

    def get_voltage_resolution(self, channel):
        return self._resolution.get(int(channel), 0.00390625)   # placeholder

    def get_coupling(self, channel):
        return False                                            # placeholder (this unit reads DC only)

    def is_generator_enabled(self):
        return self._generator_enabled

    def has_hard_trigger(self):
        return False                                            # placeholder

    def has_dds(self):
        return True                                             # placeholder

    def has_io(self):
        return False                                            # placeholder

    def has_pretrigger_percent(self):
        return True                                             # placeholder

    def has_roll_mode(self):
        return True                                             # placeholder

    def memory_length_kb(self):
        return self._memory_length_kb

    def set_generator(self, waveform=None, frequency_hz=None, duty_cycle_percent=None):
        if waveform is not None:
            self._waveform = int(waveform)                      # placeholder
        if frequency_hz is not None:
            self._frequency_hz = int(frequency_hz)              # placeholder
        if duty_cycle_percent is not None:
            self._duty_cycle_percent = int(duty_cycle_percent)  # placeholder

    def set_trigger(self, mode=None, style=None, source=None, level_mv=None, pretrigger_percent=None):
        if mode is not None:
            self._trigger["mode"] = int(mode)                   # placeholder
        if style is not None:
            self._trigger["style"] = int(style)                 # placeholder
        if source is not None:
            self._trigger["source"] = int(source)               # placeholder
        if level_mv is not None:
            self._trigger["level_mv"] = int(level_mv)           # placeholder
        if pretrigger_percent is not None:
            self._trigger["pretrigger_percent"] = int(pretrigger_percent)  # placeholder

    def set_channel_range(self, channel, min_mv, max_mv):
        channel = int(channel)
        self._ranges[channel] = (int(min_mv), int(max_mv))      # placeholder
        self._resolution[channel] = max(abs(int(max_mv) - int(min_mv)), 1) / 256.0  # placeholder

    def capture(self, length_kb=None, force_length=False, timeout_s=6.0):
        ch1 = [0.0, 1.0, 0.0, -1.0]                             # placeholder
        ch2 = [0.5, 1.5, 0.5, -0.5]                             # placeholder
        return _FakeCapture(ch1, ch2, self._sample_rate, 64, 4, 0.0, (False, False), 0.0)  # placeholder

    def generator_enable(self, enable):
        self._generator_enabled = bool(enable)

    def disconnect(self):
        self._connected = False

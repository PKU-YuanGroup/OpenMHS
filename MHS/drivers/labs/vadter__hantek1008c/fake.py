"""Fake backend of the Hantek 1008C driver: an in-memory stand-in for pyhantek1008C:Hantek1008.

Gate G7: every public method defined here exists on Hantek1008 (or its base Hantek1008CRaw) in the clone.  The
methods mirror the upstream signatures: get_active_channels, get_time, get_vscales,
get_generator_waveform_max_length, is_paused, set_generator_on, set_generator_speed, set_generator_waveform,
pause, cancel_pause and close.  The state is the instrument's settings and its keep-alive pause flag; the sample
acquisition methods are not reached by the driver.

The starting values, the 500 time samples and the waveform bytes are test data, not device facts: the values that
are not forced by the upstream method contract are marked ``# placeholder``.  Nothing here opens USB or talks to a
device.
"""


class FakeHantek1008:
    def __init__(self, **_options):
        self._active_channels = list(range(8))              # placeholder: all eight channel ids
        self._vscales = [1.0] * 8                           # placeholder: the constructor default 1.0 for every channel
        self._generator_waveform_max_length = 1440          # placeholder: the upstream constant (pyhantek1008C.py:630)
        self._generator_on = False                          # placeholder: the upstream init1 switches it off
        self._generator_speed = 300_000                     # placeholder: the upstream init1 speed in rpm
        self._waveform = []                                 # placeholder: no waveform received yet
        self._paused = False                                # placeholder: no keep-alive thread
        self._closed = False                                # placeholder: the USB-like handle is open

    def get_active_channels(self):
        return list(self._active_channels)

    def get_time(self):
        samplerate = 100_000                                # placeholder: samples per second
        return [index / samplerate for index in range(500)]  # placeholder: test time axis

    def get_vscales(self):
        return list(self._vscales)

    def get_generator_waveform_max_length(self):
        return self._generator_waveform_max_length

    def is_paused(self):
        return self._paused

    def set_generator_on(self, turn_on):
        self._generator_on = bool(turn_on)

    def set_generator_speed(self, speed_in_rpm):
        self._generator_speed = int(speed_in_rpm)

    def set_generator_waveform(self, waveform):
        self._waveform = list(waveform)

    def pause(self):
        if self._paused:
            raise RuntimeError("Can't pause because device is already pausing")
        self._paused = True

    def cancel_pause(self):
        if not self._paused:
            raise RuntimeError("Can't cancel pause because device is not paused")
        self._paused = False

    def close(self):
        self._paused = False
        self._closed = True

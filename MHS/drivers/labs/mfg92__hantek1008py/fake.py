"""Fake backend of the Hantek 1008C driver: an in-memory stand-in for hantek1008:Hantek1008.

Gate G7: every public method defined here exists on the upstream class ``Hantek1008`` (hantek1008.py:683) or its
base ``Hantek1008Raw`` (hantek1008.py:37), and the signatures mirror the upstream ones: ``get_active_channels``
(hantek1008.py:644), ``get_vscales`` (637), ``get_zero_offset`` (750, override of 525), ``channel_count`` (434),
``is_paused`` (609), ``get_generator_waveform_max_length`` (539), ``set_generator_on`` (542),
``set_generator_speed`` (548), ``set_generator_waveform`` (564), ``pause`` (594), ``cancel_pause`` (601) and
``close`` (612).

Every number below is test data for this stand-in, never a Fact, a Limit or a reference: each one is marked
``# placeholder``.  The values never move by themselves, so reading the state twice gives the same state.  The
stand-in starts with two active channels, a vertical scale of 1.0 on every channel, a zero offset of 2048 raw
sample units on every channel and vertical scale, the pause thread stopped, and the generator off.  Nothing here
talks to a device.
"""


class FakeHantek1008:
    def __init__(self, **_options):
        self._active_channels = [0, 1]                       # placeholder test data: channels 0 and 1 active
        self._vscales = [1.0] * 8                            # placeholder test data: scale factor per channel
        self._zero_offsets = {0.02: [2048.0] * 8,            # placeholder test data: raw zero offsets
                              0.125: [2048.0] * 8,           # placeholder test data: raw zero offsets
                              1.0: [2048.0] * 8}             # placeholder test data: raw zero offsets
        self._paused = False                                 # placeholder test data: pause thread stopped
        self._generator_on = False                           # placeholder test data: generator off
        self._generator_speed = 300000                       # placeholder test data: generator speed in rpm
        self._generator_waveform = [240, 15]                 # placeholder test data: waveform bytes F0 0F
        self._closed = False                                 # placeholder test data: device open

    def get_active_channels(self):
        """The active channel ids (hantek1008.py:644)."""
        return list(self._active_channels)

    def get_vscales(self):
        """One vertical scale factor per channel (hantek1008.py:637)."""
        return list(self._vscales)

    def get_zero_offset(self, channel_id, vscale=None):
        """The zero offset of a channel at a vertical scale (hantek1008.py:750)."""
        if vscale is None:
            vscale = self._vscales[int(channel_id)]
        return self._zero_offsets[vscale][int(channel_id)]

    @staticmethod
    def channel_count():
        """The device has 8 channels (hantek1008.py:434-435)."""
        return 8                                             # placeholder test data: channel count of the stand-in

    def is_paused(self):
        """True while the pause thread runs (hantek1008.py:609)."""
        return self._paused

    @staticmethod
    def get_generator_waveform_max_length():
        """The generator API reports 1440 (hantek1008.py:539-540)."""
        return 1440                                          # placeholder test data: length of the stand-in

    def set_generator_on(self, turn_on):
        """Switch the generator outputs on or off (hantek1008.py:542)."""
        self._generator_on = bool(turn_on)

    def set_generator_speed(self, speed_in_rpm):
        """Set the generator speed (hantek1008.py:548)."""
        self._generator_speed = int(speed_in_rpm)

    def set_generator_waveform(self, waveform):
        """Upload the waveform bytes (hantek1008.py:564)."""
        self._generator_waveform = list(waveform)

    def pause(self):
        """Start the pause thread (hantek1008.py:594); the stand-in only records the state."""
        self._paused = True

    def cancel_pause(self):
        """Stop the pause thread (hantek1008.py:601); the stand-in only records the state."""
        self._paused = False

    def close(self):
        """Close the device (hantek1008.py:612)."""
        self._closed = True

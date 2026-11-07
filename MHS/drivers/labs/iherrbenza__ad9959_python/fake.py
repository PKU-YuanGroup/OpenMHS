"""Fake backend of the AD9959 driver: an in-memory stand-in for DDS_ESP32_lab.DDS_ESP32:DDS_ESP32.

Gate G7: every public method defined here exists on the upstream class in the clone (set_frequency,
set_amplitude and set_phase, DDS_ESP32_lab/DDS_ESP32.py:554-605).  The signatures mirror the upstream ones,
including the ``send`` keyword the driver passes as True.  The fake keeps the last word each method received in
private attributes; the driver does not read them and the values are test data, not device facts.  Nothing here
opens a socket or talks to a device.
"""


class FakeDDS_ESP32:
    def __init__(self, **_options):
        # placeholder: no channel word has been sent yet
        self._frequency = [None, None, None, None]
        self._amplitude = [None, None, None, None]
        self._phase = [None, None, None, None]

    def set_frequency(self, ch, freq, send=False):
        self._frequency[int(ch)] = float(freq)
        return 0  # placeholder: the driver ignores the register word the upstream method returns

    def set_amplitude(self, ch, amp, send=False):
        self._amplitude[int(ch)] = int(amp)
        return 0  # placeholder: the driver ignores the register word the upstream method returns

    def set_phase(self, ch, phase, send=False):
        self._phase[int(ch)] = float(phase)
        return 0  # placeholder: the driver ignores the register word the upstream method returns

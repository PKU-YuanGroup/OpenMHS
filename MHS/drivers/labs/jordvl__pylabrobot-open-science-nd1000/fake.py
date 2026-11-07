"""Fake backend for the NanoDrop 1000 driver: an in-memory stand-in for Code/nanodrop.py:NanoDrop1000.

Gate G7: every public method defined here exists on the upstream class (``Code/nanodrop.py:23-179``): ``connect``,
``close``, ``set_lamp``, ``set_magnet``, ``set_integration_time``, ``get_raw_spectrum``, ``take_blank`` and
``measure_absorbance``.  The methods mirror the upstream signatures, and the driver calls only those names.

Every number below is test data, marked ``# placeholder``.  The fake starts with a placeholder dark spectrum and a
placeholder blank spectrum already stored, so one stateless absorbance call completes on a fresh endpoint, the way
the gate's conformance group calls a capability; the real device starts with both spectra unset and its
``measure_absorbance`` raises ValueError until ``take_blank`` has run (``Code/nanodrop.py:157-158``).  Nothing here
talks to a USB device, and the integration time is stored but does not change the synthetic frame.
"""

import math

#: placeholder: the clone's decoder produces 2048 pixels (Code/nanodrop.py:105, 124-131).
PIXELS = 2048


def _placeholder_light(peak_scale):
    """A synthetic smooth light spectrum with two placeholder peaks near 260 nm and 280 nm."""
    values = []
    for index in range(PIXELS):
        wavelength = 220.0 + index * (530.0 / (PIXELS - 1))  # placeholder: 220 to 750 nm
        base = 800.0 + 0.2 * wavelength                      # placeholder: detector baseline
        dna = 260.0 * math.exp(-((wavelength - 260.0) / 12.0) ** 2)     # placeholder: DNA peak
        protein = 160.0 * math.exp(-((wavelength - 280.0) / 15.0) ** 2)  # placeholder: protein peak
        values.append(base + peak_scale * (dna + protein))
    return values


class FakeNanoDrop1000:
    def __init__(self, **_options):
        self.connected = False
        self._lamp = False
        self._magnet = False
        self._integration_ms = 20                          # placeholder: the clone's default exposure
        # placeholder: a linear 220 to 750 nm axis, not calibration data
        self._wavelengths = [220.0 + index * (530.0 / (PIXELS - 1)) for index in range(PIXELS)]
        self._dark_counts = [1.0 for _ in range(PIXELS)]            # placeholder: dark baseline counts
        self._blank_counts = _placeholder_light(1.0)                # placeholder: blank light counts
        self._sample_counts = _placeholder_light(1.10)              # placeholder: sample light counts
        self._active_counts = self._blank_counts
        self._dark_spectrum = list(self._dark_counts)               # placeholder: already blanked for the gate
        self._blank_spectrum = list(self._blank_counts)             # placeholder: already blanked for the gate

    # -- transport lifecycle -----------------------------------------------------------------------------------
    def connect(self):
        self.connected = True

    def close(self):
        self._lamp = False
        self._magnet = False
        self.connected = False

    # -- low-level hardware control ----------------------------------------------------------------------------
    def set_lamp(self, state):
        self._lamp = bool(state)

    def set_magnet(self, state):
        self._magnet = bool(state)

    def set_integration_time(self, ms):
        # Mirrors the clone (Code/nanodrop.py:70-81): clamp, then split the value into two bytes; as upstream, a
        # float raises TypeError at the byte split instead of being converted.
        if ms < 3:
            ms = 3
        elif ms > 65535:
            ms = 65535
        lsb = ms & 0xFF
        msb = (ms >> 8) & 0xFF
        self._integration_ms = (msb << 8) | lsb

    # -- data acquisition --------------------------------------------------------------------------------------
    def get_raw_spectrum(self):
        if self._lamp:
            return list(self._active_counts)
        return list(self._dark_counts)

    def take_blank(self, integration_ms=20):  # placeholder default, mirrors the clone
        self.set_integration_time(integration_ms)
        self.set_lamp(False)
        self.set_magnet(True)
        self._dark_spectrum = self.get_raw_spectrum()
        self._active_counts = self._blank_counts
        self.set_lamp(True)
        self._blank_spectrum = self.get_raw_spectrum()
        self.set_lamp(False)
        self.set_magnet(False)

    def measure_absorbance(self, integration_ms=20):  # placeholder default, mirrors the clone
        if self._blank_spectrum is None or self._dark_spectrum is None:
            raise ValueError("You must run take_blank() before measuring!")
        self.set_integration_time(integration_ms)
        self.set_magnet(True)
        self.set_lamp(True)
        self._active_counts = self._sample_counts
        sample = self.get_raw_spectrum()
        self.set_lamp(False)
        self.set_magnet(False)
        numerator = [max(value - dark, 1.0) for value, dark in zip(sample, self._dark_spectrum)]
        denominator = [max(value - dark, 1.0) for value, dark in zip(self._blank_spectrum, self._dark_spectrum)]
        absorbance = [-math.log10(up / down) for up, down in zip(numerator, denominator)]
        return list(self._wavelengths), absorbance

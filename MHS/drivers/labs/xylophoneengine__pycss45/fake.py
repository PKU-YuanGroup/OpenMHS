"""Fake backend of the CSS45 driver: an in-memory stand-in for ``pycss45:CSS45``.

Gate G7: every public method defined here exists on ``pycss45:CSS45`` (pycss45.py:438).  The wire
transport, the USB HID framing and the reply parsers of the upstream are not reproduced: this fake only
keeps the state the driver reads and answers ``measure()`` with a deterministic synthetic spectrum.  The
starting values and the synthetic spectrum are test data (each one is marked ``# placeholder``), not facts
about a device, and nothing here talks to hardware.  Reading the state twice gives the same state.
"""

from __future__ import annotations

#: 288 pixel wavelengths from 360 to 830 nm: test data for the driver fake.  # placeholder
_WAVELENGTHS = [360.0 + (830.0 - 360.0) * index / 287.0 for index in range(288)]
#: A deterministic synthetic spectral shape in arbitrary test units.  # placeholder
_SPECTRUM = [1.0e-4 + 2.0e-4 * ((index * 37) % 101) / 100.0 for index in range(288)]


class _Measurement:
    """The fields of ``pycss45.Measurement`` that the driver reads (test values)."""

    def __init__(self, wavelengths, spectrum, integration_time, cct, photopic, par):
        self.wavelengths = list(wavelengths)
        self.spectrum = list(spectrum)
        self.integration_time = integration_time
        self.cct = cct
        self.photopic = photopic
        self.par = par


class FakeCSS45:
    """In-memory CSS45; the public methods mirror the ones the driver calls on the upstream class."""

    def __init__(self, **_options):
        self._open = True
        self._serial_number = "000000000000000"      # placeholder
        self._firmware_version = "1.58"              # placeholder
        self._status = 0                             # placeholder, the success code
        self._temperature = 24.5                     # placeholder, deg C
        self._cct = 5000.0                           # placeholder, K
        self._photopic = 50.0                        # placeholder, lx
        self._par = 0.5                              # placeholder
        self._radiometric_unit = "W_PER_M2"          # placeholder
        self._last_integration_time = 0.16           # placeholder, s

    def measure(self):
        return _Measurement(
            _WAVELENGTHS,
            _SPECTRUM,
            self._last_integration_time,
            self._cct,
            self._photopic,
            self._par,
        )

    def get_serial_number(self):
        return self._serial_number

    def get_firmware_version(self):
        return self._firmware_version

    def get_status(self):
        return self._status

    def get_temperature(self):
        return self._temperature

    def get_cct(self):
        return self._cct

    def get_photopic(self):
        return self._photopic

    def get_par(self):
        return self._par

    def get_radiometric_unit(self):
        return self._radiometric_unit

    def get_last_integration_time(self):
        return self._last_integration_time

    def get_wl_borders(self):
        return (_WAVELENGTHS[0], _WAVELENGTHS[-1])

    def connected(self):
        return self._open

    def disconnect(self):
        self._open = False

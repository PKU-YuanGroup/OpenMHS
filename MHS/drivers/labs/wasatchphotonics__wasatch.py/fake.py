"""Fake backend of the Wasatch driver: an in-memory stand-in for the FID spectrometer.

Gate G7: every public method defined here exists on
``wasatch.FeatureIdentificationDevice:FeatureIdentificationDevice`` (the
``get_*``, ``set_*`` and ``disconnect`` methods of the upstream class).  The
one attribute the driver reaches on the backend, ``settings``, is set by the
upstream __init__ (wasatch/FeatureIdentificationDevice.py:76) and carries the
``wavelengths`` list that SpectrometerSettings builds from the EEPROM wavecal
coefficients (wasatch/SpectrometerSettings.py:325).

The values are test data, not device defaults or limits.  The detector array
here has eight pixels; the upstream reads the unit's own pixel count (1024,
2048, ...) from its EEPROM.  Nothing here talks to a device.
"""


class _Response:
    """The ``data``/``error_msg`` members the driver reads from SpectrometerResponse."""

    def __init__(self, data, error_msg=""):
        self.data = data
        self.error_msg = error_msg


class _Settings:
    """The one member of SpectrometerSettings the driver reads: the wavelength axis."""

    def __init__(self):
        self.wavelengths = [400.0 + 10.0 * index for index in range(8)]   # placeholder: test data


class FakeWasatchSpectrometer:
    def __init__(self, **_options):
        self.settings = _Settings()
        self._connected = True
        self._integration_time_ms = 100           # placeholder: test data
        self._detector_temperature_degC = 25.0    # placeholder: test data
        self._detector_tec_setpoint_degC = -10.0  # placeholder: test data
        self._tec_enabled = False                 # placeholder: test data
        self._ambient_temperature_degC = 22.0     # placeholder: test data
        self._laser_enabled = False               # placeholder: test data

    def get_integration_time_ms(self):
        return _Response(self._integration_time_ms)

    def set_integration_time_ms(self, ms):
        # The upstream rounds to whole milliseconds and never sends less than 1
        # (wasatch/FeatureIdentificationDevice.py:1701).
        self._integration_time_ms = max(1, int(round(ms)))
        return _Response(self._integration_time_ms)

    def get_detector_temperature_degC(self, raw=None):
        return _Response(self._detector_temperature_degC)

    def get_detector_tec_setpoint_degC(self):
        return _Response(self._detector_tec_setpoint_degC)

    def get_tec_enabled(self):
        return _Response(self._tec_enabled)

    def get_ambient_temperature_degC(self):
        return _Response(self._ambient_temperature_degC)

    def get_laser_enabled(self):
        return _Response(self._laser_enabled)

    def set_laser_enable(self, flag):
        self._laser_enabled = bool(flag)
        return _Response(True)

    def get_spectrum(self, trigger=True, auto_raman_params=None):
        # The upstream returns the detector's pixel intensities as response.data
        # (wasatch/FeatureIdentificationDevice.py:1652-1653).  Eight values are
        # test data, not the pixel count of any model.
        scale = max(1, self._integration_time_ms)
        return _Response([ (index + 1) * scale for index in range(8) ])   # placeholder: test data

    def disconnect(self):
        # The upstream disables the laser on disconnect (line 453-456).
        self._laser_enabled = False
        self._connected = False
        return _Response(True)

"""Fake backend of the python-seabreeze driver: an in-memory stand-in for seabreeze.spectrometers:Spectrometer.

Gate G7: every public member defined here exists on the upstream class Spectrometer
(src/seabreeze/spectrometers.py:97): ``pixels`` (366-367), ``max_intensity`` (265-271), ``serial_number`` (356-358),
``model`` (361-363), ``wavelengths`` (187-190), ``intensities`` (199-202), ``integration_time_micros`` (305-310) and
``close`` (413-414); the signatures mirror the upstream ones.  The upstream class has no separate acquisition stop,
so ``close`` is the native stop and sets a flag a reviewer can observe.

Every value below is test data of this stand-in, not a device fact, and each one is marked ``# placeholder``: a real
detector returns the number of pixels its model declares (the pyseabreeze backend declares 2048 for USB2000PLUS and
FLAMES and other counts for other models, src/seabreeze/pyseabreeze/devices.py:506) and wavelengths from its own
calibration.  The values never change by themselves, so reading the state twice gives the same state.  Nothing here
talks to a device: this class is a separate object and never derives from Spectrometer (G3 FAKE_IS_NATIVE).
"""

#: Number of pixels of this stand-in's detector (placeholder test data).
PIXELS = 16
#: Wavelength of the first pixel and the step to the next one, in nm (placeholder test data).
FIRST_WAVELENGTH_NM = 400.0
WAVELENGTH_STEP_NM = 40.0


class FakeSpectrometer:
    def __init__(self, **_options):
        self._pixels = PIXELS                                      # placeholder test data
        self._wavelengths = [FIRST_WAVELENGTH_NM + WAVELENGTH_STEP_NM * index      # placeholder test data
                             for index in range(PIXELS)]
        self._intensities = [10.0, 20.0, 30.0, 250.0, 50.0, 60.0, 70.0, 80.0,      # placeholder test data
                             90.0, 100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0]
        self._max_intensity = 65535.0          # placeholder test data: the ADC full scale of a stand-in device
        self._serial_number = "FAKE0001"       # placeholder test data
        self._model = "USB2000PLUS"            # placeholder test data: the model name this stand-in reports
        self._integration_time_micros = 100000  # placeholder test data: the integration time before any write
        self._closed = False

    # -- state ----------------------------------------------------------------------------------------------------
    @property
    def pixels(self):
        """int: the number of pixels of the detector (upstream line 366-367)."""
        return self._pixels

    @property
    def max_intensity(self):
        """float: the maximum intensity the device can return (upstream line 265-271)."""
        return self._max_intensity

    @property
    def serial_number(self):
        """str: the serial number of the device (upstream line 356-358)."""
        return self._serial_number

    @property
    def model(self):
        """str: the model type of the device (upstream line 361-363)."""
        return self._model

    # -- measurement ----------------------------------------------------------------------------------------------
    def wavelengths(self):
        """The wavelength in nm of each detector pixel (upstream line 187-190)."""
        return list(self._wavelengths)

    def intensities(self, correct_dark_counts=False, correct_nonlinearity=False):
        """The measured intensities in arbitrary units (upstream line 199-202)."""
        return list(self._intensities)

    def integration_time_micros(self, integration_time_micros):
        """Set the detector integration time in microseconds (upstream line 305-310)."""
        self._integration_time_micros = int(integration_time_micros)

    # -- native stop ----------------------------------------------------------------------------------------------
    def close(self):
        """Close the device connection (upstream line 413-414); this is the native stop of the driver."""
        self._closed = True

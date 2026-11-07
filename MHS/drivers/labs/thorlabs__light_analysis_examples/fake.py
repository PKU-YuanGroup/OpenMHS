"""Fake backend of the beam profiler driver: an in-memory stand-in for the upstream TLBC2 class.

Gate G7: every public method defined here exists on ``TLBC2`` in
``Python/Thorlabs BC207 BC210 Beam Profiler/TLBC2.py`` (TLBC2.py:156-1810), and the names are the upstream
names.  The upstream methods take ctypes output parameters; the package cannot import ctypes (G3 FORBIDDEN), so
the production adapter (``native.py``) converts a one-element Python list (or a bytearray for the image buffer)
to the ctypes pointer the DLL call expects.  This fake mirrors that adapted surface exactly: a getter fills the
list elements it was given and returns 0, and a setter receives the plain value.

Every number below is test data of the fake, not a device fact or a device limit; each is marked ``# placeholder``.
The 64 x 48 frame stands in for the real image, whose size is the sensor size (TLBC2.py:1513-1517); the fake does
not load the Thorlabs DLL and does not talk to a device.
"""


from .session import _Session, _native_call


def _put(slot, value):
    """Fill one output parameter (the adapted form of a ctypes pointer) and return the value."""
    if slot is not None:
        slot[0] = value
    return value


class FakeTLBC2(_Session):
    """The fake beam profiler; its method names are the upstream TLBC2 surface."""

    def __init__(self, **_options):
        super().__init__()
        self._pixels_x = 64                # placeholder
        self._pixels_y = 48                # placeholder
        self._pitch_x = 5.5                # placeholder
        self._pitch_y = 5.5                # placeholder
        self._roi = [0, 0, 64, 48]           # placeholder
        self._exposure = 40.0              # placeholder
        self._wavelength = 633.0           # placeholder
        self._precision = 1                # placeholder
        self._binning = 1                  # placeholder
        self._temperature = 31.0           # placeholder
        self._power = -3.0                 # placeholder
        self._measurement = 0              # placeholder: call counter
        self._beam = (12.0, 10.0, 11.0, 9.0, 15.0, 0.9)   # placeholder
        self._centroid = (3.5, 4.5)        # placeholder
        self._peak = (1234, 3, 4)          # placeholder
        self._saturation = (0.5, 0.0)      # placeholder
        self.closed = False                # placeholder: call flag of the fake

    # -- device session -----------------------------------------------------------------------------------------
    def _close_session(self):
        self.closed = True
        return 0

    def _close_sdk(self):
        return 0

    # -- configuration ------------------------------------------------------------------------------------------
    @_native_call
    def get_exposure_time(self, exposureTime=None):
        return _put(exposureTime, self._exposure)

    @_native_call
    def set_exposure_time(self, exposureTime):
        self._exposure = float(exposureTime)
        return 0

    @_native_call
    def get_wavelength(self, wavelength=None):
        return _put(wavelength, self._wavelength)

    @_native_call
    def set_wavelength(self, wavelength):
        self._wavelength = float(wavelength)
        return 0

    @_native_call
    def get_precision_mode(self, precisionMode=None):
        return _put(precisionMode, self._precision)

    @_native_call
    def set_precision_mode(self, precisionMode):
        self._precision = int(precisionMode)
        return 0

    @_native_call
    def get_binning(self, binning=None):
        return _put(binning, self._binning)

    @_native_call
    def set_binning(self, binning):
        self._binning = int(binning)
        return 0

    @_native_call
    def get_sensor_information(self, pixelCountX=None, pixelCountY=None, pixelPitchHorizontal=None,
                               pixelPitchVertical=None):
        _put(pixelCountX, self._pixels_x)
        _put(pixelCountY, self._pixels_y)
        _put(pixelPitchHorizontal, self._pitch_x)
        return _put(pixelPitchVertical, self._pitch_y)

    @_native_call
    def get_roi(self, left=None, top=None, width=None, height=None):
        _put(left, self._roi[0])
        _put(top, self._roi[1])
        _put(width, self._roi[2])
        return _put(height, self._roi[3])

    @_native_call
    def set_roi(self, left, top, width, height):
        # TLBC2.py:650-660 permits device coercion; use valid placeholder geometry.
        if min(width, height) < 32 or width % 4 or height % 4:
            raise ValueError("ROI dimensions must be multiples of four and at least 32")
        self._roi = [int(left), int(top), min(int(width), self._pixels_x), min(int(height), self._pixels_y)]
        return 0

    # -- measurement ---------------------------------------------------------------------------------------------
    @_native_call
    def request_new_measurement(self):
        self._measurement += 1
        # placeholder: canned analysis values that move only to make a new measurement observable.
        self._beam = (12.0 + self._measurement, 10.0, 11.0, 9.0, 15.0, 0.9)   # placeholder
        self._centroid = (3.5, 4.5)        # placeholder
        self._peak = (1234, 3, 4)          # placeholder
        self._saturation = (0.5, 0.0)      # placeholder
        self._power = -3.0 - self._measurement * 0.1   # placeholder
        return 0

    @_native_call
    def get_image(self, pixelData, imageWidth=None, imageHeight=None, bytesPerPixel=None):
        width, height = self._roi[2], self._roi[3]
        bpp = 2 if self._precision == 1 else 1
        _put(imageWidth, width)
        _put(imageHeight, height)
        _put(bytesPerPixel, bpp)
        size = int(width) * int(height) * int(bpp)
        if len(pixelData) < size:
            raise ValueError("the pixel buffer is smaller than the fake image")
        pixelData[:size] = bytes(((index * 7) % 256 for index in range(size)))   # placeholder
        return 0

    @_native_call
    def get_beam_width_4_sigma(self, beamWidth_4Sigma_X=None, beamWidth_4Sigma_Y=None,
                               beamWidth_4Sigma_X_Norm=None, beamWidth_4Sigma_Y_Norm=None,
                               azimuthAngle_4Sigma=None, ellipticity_4Sigma=None):
        _put(beamWidth_4Sigma_X, self._beam[0])
        _put(beamWidth_4Sigma_Y, self._beam[1])
        _put(beamWidth_4Sigma_X_Norm, self._beam[2])
        _put(beamWidth_4Sigma_Y_Norm, self._beam[3])
        _put(azimuthAngle_4Sigma, self._beam[4])
        return _put(ellipticity_4Sigma, self._beam[5])

    @_native_call
    def get_centroid(self, centroidPositionX=None, centroidPositionY=None):
        _put(centroidPositionX, self._centroid[0])
        return _put(centroidPositionY, self._centroid[1])

    @_native_call
    def get_peak(self, peakIntensity=None, peakPositionX=None, peakPositionY=None):
        _put(peakIntensity, self._peak[0])
        _put(peakPositionX, self._peak[1])
        return _put(peakPositionY, self._peak[2])

    @_native_call
    def get_saturation(self, saturation=None, saturatedPixel=None):
        _put(saturation, self._saturation[0])
        return _put(saturatedPixel, self._saturation[1])

    @_native_call
    def get_power(self, totalPower=None):
        return _put(totalPower, self._power)

    @_native_call
    def get_temperature(self, temperature=None):
        return _put(temperature, self._temperature)

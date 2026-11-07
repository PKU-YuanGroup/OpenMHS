"""Hardware backend: open a Thorlabs BC207/BC210 beam profiler through the pinned upstream TLBC2 wrapper.

The acceptance gate never imports this module and nothing here ran on hardware.  A hardware operator supplies
``module_dir`` (the directory that contains the pinned clone's ``TLBC2.py``) or installs that module on
``PYTHONPATH``; Windows also needs the Thorlabs Beam SDK DLL and the IVI VISA DLL directory, which the upstream
sample adds with ``os.add_dll_directory`` (TLBC2_sample_2D_output.py:33-35).  The DLL is loaded when the upstream
``TLBC2`` object is constructed (TLBC2.py:158-183).

``native`` in driver.py names the upstream class for provenance; this module is the production adapter.  The
upstream getters take ctypes output pointers, and the SDK forbids importing ctypes from package code (G3
FORBIDDEN), so the adapter owns the ctypes work: it imports the upstream module (which already imports the ctypes
names it needs), passes real pointers and fills one-element Python lists for the driver.  The upstream method
names and output-parameter order are preserved.
"""

import importlib.util
import os
import math
import threading

from .session import _Session, _native_call

# TLBC2.py:1513-1517; this capacity is required before the native write.
MAX_WIDTH = 2448
MAX_HEIGHT = 2048
BUFFER_BYTES = MAX_WIDTH * MAX_HEIGHT * 2
_SDK_LEASE = threading.Lock()


def _integer(value, minimum, maximum, label):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(label + " is not a representable supported integer")
    return value


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("native numeric input must be finite")
    return float(value)


class _Instrument(_Session):
    """The production adapter around one upstream TLBC2 session."""

    def __init__(self, module, device, dll_handle=None, release_lease=None):
        super().__init__()
        self._module = module
        self._device = device
        self._dll_handle = dll_handle
        self._release_lease = release_lease

    @staticmethod
    def _put(slot, value):
        if slot is not None:
            slot[0] = value
        return value

    # -- device session -----------------------------------------------------------------------------------------
    def _close_session(self):
        status = self._device.close()
        if type(status) is not int or status != 0:
            raise RuntimeError("TLBC2_close did not confirm success: %r" % status)
        return status

    def _close_sdk(self):
        try:
            result = self._device.closeSDK()
        finally:
            if self._dll_handle is not None:
                self._dll_handle.close()
                self._dll_handle = None
        # The upstream wrapper raises for negative statuses. Retain the process
        # lease after any failure; a new connection cannot erase uncertainty.
        if self._release_lease is not None:
            self._release_lease()
            self._release_lease = None
        return result

    # -- configuration ------------------------------------------------------------------------------------------
    @_native_call
    def get_exposure_time(self, exposureTime=None):
        value = self._module.c_double()
        self._device.get_exposure_time(self._module.byref(value))
        return self._put(exposureTime, value.value)

    @_native_call
    def set_exposure_time(self, exposureTime):
        return self._device.set_exposure_time(self._module.c_double(_finite(exposureTime)))

    @_native_call
    def get_wavelength(self, wavelength=None):
        value = self._module.c_double()
        self._device.get_wavelength(self._module.byref(value))
        return self._put(wavelength, value.value)

    @_native_call
    def set_wavelength(self, wavelength):
        return self._device.set_wavelength(self._module.c_double(_finite(wavelength)))

    @_native_call
    def get_precision_mode(self, precisionMode=None):
        value = self._module.c_uint8()
        self._device.get_precision_mode(self._module.byref(value))
        return self._put(precisionMode, value.value)

    @_native_call
    def set_precision_mode(self, precisionMode):
        return self._device.set_precision_mode(self._module.c_uint8(_integer(precisionMode, 0, 1, "precision mode")))

    @_native_call
    def get_binning(self, binning=None):
        value = self._module.c_uint8()
        self._device.get_binning(self._module.byref(value))
        return self._put(binning, value.value)

    @_native_call
    def set_binning(self, binning):
        if type(binning) is not int or binning not in (1, 2, 4, 8, 16):
            raise ValueError("unsupported binning")
        return self._device.set_binning(self._module.c_uint8(binning))

    @_native_call
    def get_sensor_information(self, pixelCountX=None, pixelCountY=None, pixelPitchHorizontal=None,
                               pixelPitchVertical=None):
        count_x = self._module.c_uint16()
        count_y = self._module.c_uint16()
        pitch_x = self._module.c_double()
        pitch_y = self._module.c_double()
        self._device.get_sensor_information(self._module.byref(count_x), self._module.byref(count_y),
                                            self._module.byref(pitch_x), self._module.byref(pitch_y))
        self._put(pixelCountX, count_x.value)
        self._put(pixelCountY, count_y.value)
        self._put(pixelPitchHorizontal, pitch_x.value)
        return self._put(pixelPitchVertical, pitch_y.value)

    @_native_call
    def get_roi(self, left=None, top=None, width=None, height=None):
        left_value = self._module.c_uint16()
        top_value = self._module.c_uint16()
        width_value = self._module.c_uint16()
        height_value = self._module.c_uint16()
        self._device.get_roi(self._module.byref(left_value), self._module.byref(top_value),
                             self._module.byref(width_value), self._module.byref(height_value))
        self._put(left, left_value.value)
        self._put(top, top_value.value)
        self._put(width, width_value.value)
        return self._put(height, height_value.value)

    @_native_call
    def set_roi(self, left, top, width, height):
        left = _integer(left, 0, MAX_WIDTH - 1, "ROI left")
        top = _integer(top, 0, MAX_HEIGHT - 1, "ROI top")
        width = _integer(width, 32, MAX_WIDTH, "ROI width")
        height = _integer(height, 32, MAX_HEIGHT, "ROI height")
        if width % 4 or height % 4:
            raise ValueError("ROI width and height must be multiples of four")
        return self._device.set_roi(self._module.c_uint16(left), self._module.c_uint16(top),
                                    self._module.c_uint16(width), self._module.c_uint16(height))

    # -- measurement ---------------------------------------------------------------------------------------------
    @_native_call
    def request_new_measurement(self):
        return self._device.request_new_measurement()

    @_native_call
    def get_image(self, pixelData, imageWidth=None, imageHeight=None, bytesPerPixel=None):
        if not isinstance(pixelData, bytearray) or len(pixelData) != BUFFER_BYTES:
            raise ValueError("image destination must have the vendor's fixed capacity")
        buffer = (self._module.c_uint8 * BUFFER_BYTES)()
        width = self._module.c_uint16()
        height = self._module.c_uint16()
        bpp = self._module.c_uint8()
        self._device.get_image(buffer, self._module.byref(width), self._module.byref(height),
                               self._module.byref(bpp))
        if not (1 <= width.value <= MAX_WIDTH and 1 <= height.value <= MAX_HEIGHT and bpp.value in (1, 2)):
            raise RuntimeError("TLBC2_get_image returned invalid geometry")
        used = int(width.value) * int(height.value) * int(bpp.value)
        if used > len(pixelData):
            raise RuntimeError("TLBC2_get_image reported %d bytes for a %d-byte buffer"
                               % (used, len(pixelData)))
        pixelData[:used] = memoryview(buffer).cast("B")[:used]
        self._put(imageWidth, width.value)
        self._put(imageHeight, height.value)
        return self._put(bytesPerPixel, bpp.value)

    @_native_call
    def get_beam_width_4_sigma(self, beamWidth_4Sigma_X=None, beamWidth_4Sigma_Y=None,
                               beamWidth_4Sigma_X_Norm=None, beamWidth_4Sigma_Y_Norm=None,
                               azimuthAngle_4Sigma=None, ellipticity_4Sigma=None):
        x = self._module.c_double()
        y = self._module.c_double()
        x_norm = self._module.c_double()
        y_norm = self._module.c_double()
        azimuth = self._module.c_double()
        ellipticity = self._module.c_double()
        self._device.get_beam_width_4_sigma(self._module.byref(x), self._module.byref(y),
                                            self._module.byref(x_norm), self._module.byref(y_norm),
                                            self._module.byref(azimuth), self._module.byref(ellipticity))
        self._put(beamWidth_4Sigma_X, x.value)
        self._put(beamWidth_4Sigma_Y, y.value)
        self._put(beamWidth_4Sigma_X_Norm, x_norm.value)
        self._put(beamWidth_4Sigma_Y_Norm, y_norm.value)
        self._put(azimuthAngle_4Sigma, azimuth.value)
        return self._put(ellipticity_4Sigma, ellipticity.value)

    @_native_call
    def get_centroid(self, centroidPositionX=None, centroidPositionY=None):
        x = self._module.c_double()
        y = self._module.c_double()
        self._device.get_centroid(self._module.byref(x), self._module.byref(y))
        self._put(centroidPositionX, x.value)
        return self._put(centroidPositionY, y.value)

    @_native_call
    def get_peak(self, peakIntensity=None, peakPositionX=None, peakPositionY=None):
        intensity = self._module.c_uint16()
        x = self._module.c_uint16()
        y = self._module.c_uint16()
        self._device.get_peak(self._module.byref(intensity), self._module.byref(x), self._module.byref(y))
        self._put(peakIntensity, intensity.value)
        self._put(peakPositionX, x.value)
        return self._put(peakPositionY, y.value)

    @_native_call
    def get_saturation(self, saturation=None, saturatedPixel=None):
        level = self._module.c_double()
        saturated = self._module.c_double()
        self._device.get_saturation(self._module.byref(level), self._module.byref(saturated))
        self._put(saturation, level.value)
        return self._put(saturatedPixel, saturated.value)

    @_native_call
    def get_power(self, totalPower=None):
        value = self._module.c_double()
        self._device.get_power(self._module.byref(value))
        return self._put(totalPower, value.value)

    @_native_call
    def get_temperature(self, temperature=None):
        value = self._module.c_double()
        self._device.get_temperature(self._module.byref(value))
        return self._put(temperature, value.value)


def _load_module(module_dir):
    """Load the pinned upstream TLBC2.py by path, or import TLBC2 from PYTHONPATH when no directory is given."""
    if not module_dir:
        import TLBC2

        return TLBC2
    path = os.path.join(os.path.abspath(os.fspath(module_dir)), "TLBC2.py")
    if not os.path.isfile(path):
        raise FileNotFoundError("TLBC2.py is not at %s" % path)
    spec = importlib.util.spec_from_file_location("tlbc2_upstream", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load the TLBC2 module from %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _first_resource(module, device):
    """Discover using the same owned SDK object; no unowned probe is discarded."""
    count = module.c_uint32()
    device.get_device_count(module.byref(count))
    if not 0 <= count.value <= 16:  # TLBC2.py:7 MAX_CAMERA_DEVICES
        raise RuntimeError("TLBC2 reported an invalid device count")
    for index in range(count.value):
        manufacturer = module.create_string_buffer(1024)
        name = module.create_string_buffer(1024)
        serial = module.create_string_buffer(1024)
        available = module.c_int16()
        resource = module.create_string_buffer(1024)
        device.get_device_information(module.c_uint32(index), manufacturer, name, serial,
                                       module.byref(available), resource)
        if available.value:
            return resource.value
    raise RuntimeError("no available Thorlabs beam profiler was found")


def connect(module_dir=None, resource_name=None, dll_directory=None, reset_device=True, **_options):
    """Own one SDK lifecycle; no import, discovery or DLL load occurs before this factory."""
    if type(reset_device) is not bool:
        raise ValueError("reset_device must be boolean")
    if isinstance(resource_name, str):
        resource_name = resource_name.encode("ascii")
    if isinstance(resource_name, bytes):
        resource_name.decode("ascii")
    if resource_name is not None and (not isinstance(resource_name, bytes) or not resource_name
                                      or b"\0" in resource_name or len(resource_name) >= 1024):
        raise ValueError("resource_name must be a nonempty ASCII resource identifier")
    if not _SDK_LEASE.acquire(blocking=False):
        raise RuntimeError("another owned TLBC2 SDK lifecycle is active or unresolved in this process")
    handle = None
    instrument = None
    try:
        if dll_directory:
            if not hasattr(os, "add_dll_directory"):
                raise RuntimeError("dll_directory requires Windows add_dll_directory support")
            handle = os.add_dll_directory(os.fspath(dll_directory))
        module = _load_module(module_dir)
        device = module.TLBC2()
        instrument = _Instrument(module, device, handle, _SDK_LEASE.release)
        if resource_name is None:
            resource_name = _first_resource(module, device)
        if not resource_name or b"\0" in resource_name or len(resource_name) >= 1024:
            raise ValueError("discovery returned an invalid resource identifier")
        resource_name.decode("ascii")
        device.open(resource_name, module.c_bool(True), module.c_bool(reset_device))
        return instrument
    except BaseException:
        if instrument is not None:
            try:
                instrument.closeSDK()
            except BaseException as cleanup:
                raise RuntimeError("TLBC2 connection failed and owned cleanup could not be confirmed") from cleanup
        else:
            try:
                if handle is not None:
                    handle.close()
            finally:
                _SDK_LEASE.release()
        raise

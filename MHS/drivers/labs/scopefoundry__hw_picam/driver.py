"""OpenMHS driver for gh.scopefoundry/hw_picam: a Princeton Instruments PICam camera.

A direct Driver (decorated methods) over the upstream device class ``picam:PiCAM``.  The upstream object is a thin
ctypes wrapper around the PICam C API (picam.py:20): it enumerates the camera parameters, reads and writes them by
name, reads and writes ROIs, commits the parameter set, acquires a readout and reshapes it per ROI.  The
ScopeFoundry ``PicamHW`` component is a GUI wrapper around the same object (picam_hw.py:12, 54), and the readout
measurement is the acquisition loop (picam_readout.py:8, 30-46); the camera itself is ``PiCAM``.

* reads: exposure time (ms), ADC speed (MHz), cooling status, readout stride and the six fields of the first ROI;
* writes: exposure time and the first ROI's six fields.  No text file of the clone states a numeric exposure or ROI
  range: the parameters carry a PICam constraint *type* (Range/Rois) but the limits are queried from the camera at
  run time, so every numeric write is ``Limit.operator_required`` and refused ``MHS.SAFETY.LIMITS_UNSET`` until the
  site supplies its range (``site-limits.example.json`` shows the overlay);
* action: ``cap.sensing.image.v1`` calls the upstream readout path, ``read_rois`` -> ``commit_parameters`` ->
  ``acquire`` -> ``reshape_frame_data`` (picam_readout.py:34-44), and writes the first frame to a temporary 16-bit
  PGM file.  The receipt carries its path and size, not the pixel array;
* safety: the native stop is ``close()``, which closes the camera and uninitializes the PICam library
  (picam.py:52-54); the e-stop calls it and the safe state is the closed camera.  This is an R1 camera: it is not a
  laser, robot, pump, heater or centrifuge, and it has no independent hardware stop in the upstream text.

Every Fact cites a line of the clone at the pinned commit (fab5d61440b38e04e176e66ff880d16061f23997).  This package is
model-authored and unreviewed; it is checked on the fake backend only and its evidence is ``contract_checked``,
never an MHS-Device level.  Nothing here ran on hardware: the upstream module loads a Windows PICam DLL at import
(picam.py:2, 13-14) and the camera needs the vendor runtime.
"""

import os
import tempfile

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

PICAM = "picam.py"
CTYPES = "picam_ctypes.py"
HW = "picam_hw.py"
READOUT = "picam_readout.py"

#: The six fields of ``ROI_tuple`` in their order (picam.py:18).
ROI_FIELDS = ("x", "width", "x_binning", "y", "height", "y_binning")


def _roi_parts(roi):
    """The six integers of one upstream ROI tuple, in ``ROI_tuple`` order."""
    try:
        return tuple(int(roi[index]) for index in range(len(ROI_FIELDS)))
    except (TypeError, IndexError, ValueError) as exc:
        raise DriverFailed("MHS.DEVICE.FAULTED", "read_rois returned an unusable ROI") from exc


def _first_frame(frames):
    """The first two-dimensional frame of the list ``reshape_frame_data`` returned, as a list of rows."""
    if frames is None:
        raise DriverFailed("MHS.DEVICE.FAULTED", "reshape_frame_data returned no frame")
    if hasattr(frames, "tolist"):
        frames = frames.tolist()
    if not isinstance(frames, (list, tuple)) or not frames:
        raise DriverFailed("MHS.DEVICE.FAULTED", "reshape_frame_data returned no frame")
    first = frames[0]
    if hasattr(first, "tolist"):
        first = first.tolist()
    if not isinstance(first, (list, tuple)) or not first:
        raise DriverFailed("MHS.DEVICE.FAULTED", "reshape_frame_data returned an empty frame")
    if isinstance(first[0], (list, tuple)):
        frame = first
    else:
        # A single two-dimensional array rather than a list of frames.
        frame = frames
    rows = [list(row) for row in frame]
    width = len(rows[0])
    if width < 1 or any(len(row) != width for row in rows):
        raise DriverFailed("MHS.DEVICE.FAULTED", "reshape_frame_data returned a frame with unequal rows")
    return rows


def _write_pgm(rows):
    """Write one frame as a binary 16-bit PGM in the system temporary directory; return (path, width, height)."""
    height = len(rows)
    width = len(rows[0])
    pixels = bytearray()
    for row in rows:
        for value in row:
            try:
                number = int(round(float(value)))
            except (TypeError, ValueError) as exc:
                raise DriverFailed("MHS.DEVICE.FAULTED", "the acquired frame carries a non-numeric pixel") from exc
            number = max(0, min(65535, number))
            pixels.append(number >> 8)
            pixels.append(number & 0xFF)
    handle, path = tempfile.mkstemp(prefix="picam-", suffix=".pgm")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(f"P5\n{width} {height}\n65535\n".encode("ascii"))
            stream.write(bytes(pixels))
    except BaseException:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    return path, width, height


class PicamCamera(Driver):
    device_id = "hw-picam"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R1"
    native = "picam:PiCAM"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePiCAM"}
    vendor, model = "Princeton Instruments", "PICam camera (tested upstream on a PI PIXIS)"
    display_name = "Princeton Instruments PICam camera (ScopeFoundryHW.picam)"
    tags = ["camera", "ccd", "picam", "princeton-instruments", "imaging", "scopefoundry"]
    facts = [
        Fact("PiCAM loads the PICam shared library named by the PICAM_DLL environment variable with ctypes when the "
             "module is imported", source="upstream_code", ref=f"{PICAM}:13-14"),
        Fact("read_param dispatches on the PICam parameter type and returns the value; an enumeration is returned "
             "as its short name and Rois as a list of ROI tuples", source="upstream_code", ref=f"{PICAM}:57-106"),
        Fact("write_param sets integer, floating-point and enumeration parameters through the PICam C API",
             source="upstream_code", ref=f"{PICAM}:115-142"),
        Fact("commit_parameters commits the parameter set and returns the names of the parameters that failed",
             source="upstream_code", ref=f"{PICAM}:164-173"),
        Fact("The upstream exposure value is in milliseconds", source="upstream_code", ref=f"{PICAM}:334"),
        Fact("The ScopeFoundry plug-in labels ExposureTime in ms and AdcSpeed in MHz", source="upstream_code",
             ref=f"{HW}:43-44"),
        Fact("read_rois stores the returned ROI list on self.roi_array and returns it", source="upstream_code",
             ref=f"{PICAM}:199-201"),
        Fact("write_single_roi writes one ROI_tuple through write_rois", source="upstream_code",
             ref=f"{PICAM}:231-238"),
        Fact("acquire takes readout_count readouts and returns a flat uint16 array; ReadoutStride is treated as a "
             "byte count", source="upstream_code", ref=f"{PICAM}:240-263"),
        Fact("reshape_frame_data reshapes the flat readout per ROI, dividing the ROI width and height by the "
             "binning", source="upstream_code", ref=f"{PICAM}:290-301"),
        Fact("The readout measurement reads the ROIs, commits the parameters, acquires one readout and reshapes it "
             "per ROI", source="upstream_code", ref=f"{READOUT}:34-44"),
        Fact("close closes the camera and uninitializes the PICam library", source="upstream_code",
             ref=f"{PICAM}:52-54"),
        Fact("The cooling status enumeration values are Unlocked, Locked and Faulted", source="upstream_code",
             ref=f"{CTYPES}:2906-2911"),
    ]
    safe_state = "camera closed and the PICam library uninitialized; no further readout is requested"

    # -- helpers ----------------------------------------------------------------------------------------------
    def _first_roi(self):
        """The six integers of the first ROI the camera reports."""
        rois = self.native.read_rois()
        if not isinstance(rois, (list, tuple)) or not rois:
            raise DriverFailed("MHS.DEVICE.FAULTED", "read_rois returned no ROI")
        return _roi_parts(rois[0])

    def _commit(self):
        """Commit the parameter set; a non-empty failed list is a device failure, not a success."""
        failed = self.native.commit_parameters()
        if failed:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"commit_parameters reported failed parameters: {failed}", native_code=failed)

    def _write_roi(self, **changes):
        """Write the first ROI with ``changes`` applied and return its new six fields."""
        current = dict(zip(ROI_FIELDS, self._first_roi()))
        current.update(changes)
        values = [int(current[field]) for field in ROI_FIELDS]
        self.native.write_single_roi(*values)
        self._commit()
        return dict(zip(ROI_FIELDS, self._first_roi()))

    # -- reads ------------------------------------------------------------------------------------------------
    @read("exposure_time", unit="ms", description="Requested exposure time of the camera")
    def exposure_time(self):
        return float(self.native.read_param("ExposureTime"))

    @read("adc_speed", unit="MHz", description="Analog-to-digital converter speed")
    def adc_speed(self):
        return float(self.native.read_param("AdcSpeed"))

    @read("sensor_temperature_status", type="string",
          description="Cooling status reported by the camera: Unlocked, Locked or Faulted")
    def sensor_temperature_status(self):
        return str(self.native.read_param("SensorTemperatureStatus"))

    @read("readout_stride", type="integer", unit="1",
          description="Readout stride in bytes, used by acquire to size the data pointer")
    def readout_stride(self):
        return int(self.native.read_param("ReadoutStride"))

    @read("roi_x", type="integer", unit="1", description="First ROI left column in pixels")
    def roi_x(self):
        return self._first_roi()[0]

    @read("roi_width", type="integer", unit="1", description="First ROI width in pixels")
    def roi_width(self):
        return self._first_roi()[1]

    @read("roi_x_binning", type="integer", unit="1", description="First ROI horizontal binning factor")
    def roi_x_binning(self):
        return self._first_roi()[2]

    @read("roi_y", type="integer", unit="1", description="First ROI top row in pixels")
    def roi_y(self):
        return self._first_roi()[3]

    @read("roi_height", type="integer", unit="1", description="First ROI height in pixels")
    def roi_height(self):
        return self._first_roi()[4]

    @read("roi_y_binning", type="integer", unit="1", description="First ROI vertical binning factor")
    def roi_y_binning(self):
        return self._first_roi()[5]

    # -- writes -----------------------------------------------------------------------------------------------
    @write("exposure_time", unit="ms", description="Requested exposure time of the camera, in milliseconds",
           limit=Limit.operator_required(
               "PICam declares ExposureTime with a Range constraint but the range is queried from the camera at run "
               "time; no text file of the clone states a numeric exposure range, so the site supplies it"))
    def set_exposure_time(self, value):
        self.native.write_param("ExposureTime", float(value))
        self._commit()
        return float(self.native.read_param("ExposureTime"))

    @write("roi_x", type="integer", unit="1", description="First ROI left column in pixels",
           limit=Limit.operator_required(
               "the clone declares the Rois parameter but no numeric x range; the sensor geometry is queried from "
               "the camera, so the site supplies the ROI bounds"))
    def set_roi_x(self, value):
        return self._write_roi(x=int(value))["x"]

    @write("roi_width", type="integer", unit="1", description="First ROI width in pixels",
           limit=Limit.operator_required(
               "the clone declares the Rois parameter but no numeric width range; the sensor geometry is queried "
               "from the camera, so the site supplies the ROI bounds"))
    def set_roi_width(self, value):
        return self._write_roi(width=int(value))["width"]

    @write("roi_x_binning", type="integer", unit="1", description="First ROI horizontal binning factor",
           limit=Limit.operator_required(
               "the clone declares the Rois parameter but no numeric binning range; the sensor geometry is queried "
               "from the camera, so the site supplies the ROI bounds"))
    def set_roi_x_binning(self, value):
        return self._write_roi(x_binning=int(value))["x_binning"]

    @write("roi_y", type="integer", unit="1", description="First ROI top row in pixels",
           limit=Limit.operator_required(
               "the clone declares the Rois parameter but no numeric y range; the sensor geometry is queried from "
               "the camera, so the site supplies the ROI bounds"))
    def set_roi_y(self, value):
        return self._write_roi(y=int(value))["y"]

    @write("roi_height", type="integer", unit="1", description="First ROI height in pixels",
           limit=Limit.operator_required(
               "the clone declares the Rois parameter but no numeric height range; the sensor geometry is queried "
               "from the camera, so the site supplies the ROI bounds"))
    def set_roi_height(self, value):
        return self._write_roi(height=int(value))["height"]

    @write("roi_y_binning", type="integer", unit="1", description="First ROI vertical binning factor",
           limit=Limit.operator_required(
               "the clone declares the Rois parameter but no numeric binning range; the sensor geometry is queried "
               "from the camera, so the site supplies the ROI bounds"))
    def set_roi_y_binning(self, value):
        return self._write_roi(y_binning=int(value))["y_binning"]

    # -- action -----------------------------------------------------------------------------------------------
    @action(cap="cap.sensing.image.v1",
            description="Capture one readout through read_rois, commit_parameters, acquire and reshape_frame_data, "
                        "and return the path of a 16-bit PGM file with its size",
            input={
                "width": Field("integer", unit="1",
                               description="First ROI width in pixels; omit it to keep the configured width",
                               limit=Limit.operator_required(
                                   "the clone states no numeric ROI range; the site supplies it")),
                "height": Field("integer", unit="1",
                                description="First ROI height in pixels; omit it to keep the configured height",
                                limit=Limit.operator_required(
                                    "the clone states no numeric ROI range; the site supplies it")),
                "exposure_ms": Field("number", unit="ms",
                                     description="Exposure for this capture in milliseconds; omit it to keep the "
                                                 "configured exposure",
                                     limit=Limit.operator_required(
                                         "the clone states no numeric exposure range; the site supplies it")),
            })
    def capture(self, width=None, height=None, exposure_ms=None):
        current = dict(zip(ROI_FIELDS, self._first_roi()))
        if exposure_ms is not None:
            self.native.write_param("ExposureTime", float(exposure_ms))
        if width is not None:
            current["width"] = int(width)
        if height is not None:
            current["height"] = int(height)
        if width is not None or height is not None:
            self.native.write_single_roi(*(int(current[field]) for field in ROI_FIELDS))
        self._commit()
        self.native.read_rois()
        data = self.native.acquire(readout_count=1, readout_timeout=-1)
        rows = _first_frame(self.native.reshape_frame_data(data))
        path, actual_width, actual_height = _write_pgm(rows)
        return {
            "image_ref": path,
            "width": actual_width,
            "height": actual_height,
            "media_type": "image/x-portable-graymap",
            "exposure_ms": float(self.native.read_param("ExposureTime")),
        }

    # -- safety -----------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: close the camera and uninitialize the PICam library (picam.py:52-54)."""
        self.native.close()

"""OpenMHS driver for gh.shafinulh/rax-labscript: the Nuvu EMCCD camera of the rax-labscript suite.

A direct Driver (decorated methods) over the upstream class
``user_devices.NuvuCamera.Nuvu_sdk.Nuvu_cam_utils:NuvuCamUtils``
(userlib/user_devices/NuvuCamera/Nuvu_sdk/Nuvu_cam_utils.py:23), the object the repository's BLACS worker
instantiates (userlib/user_devices/NuvuCamera/blacs_workers.py:21).  The class is a ctypes wrapper around the Nuvu
vendor SDK: importing ``NC_api`` loads ``libnuvu.so`` on Linux or ``nc_driver_x64.dll`` on Windows
(userlib/user_devices/NuvuCamera/Nuvu_sdk/NC_api.py:9-13), and the wrapper opens the camera in its constructor
(Nuvu_cam_utils.py:52).

* reads: the acquisition state the SDK reports, the exposure time, the readout mode, the trigger mode, the shutter
  mode, the calibrated EM gain and the detector and target detector temperatures; the numeric state comes from the
  wrapper's own ``getAllCamInfo`` snapshot (nc_camera.py:607-671), which is the call the repository itself uses in
  ``get_cam_data`` (blacs_workers.py:66-73);
* writes: exposure time, readout mode, trigger mode, shutter mode and calibrated EM gain. The clone documents
  milliseconds and the mode enumerations but no exposure or gain range, so those bounds are
  ``Limit.operator_required``. Temperatures are read-only raw SDK values because their unit is not stated;
* ``cap.sensing.image.v1``: one single-image acquisition.  It applies an optional exposure, calls ``cam_start(1)``,
  reads one frame with ``get_image`` (which flushes the read queue and returns a uint16 copy), aborts acquisition with
  ``cam_stop`` and publishes the frame as a 16-bit grayscale PNG in the endpoint-owned artifact store.  The upstream
  ``snap`` configures a one-image acquisition (cam_stop then cam_start) and reads it (blacs_workers.py:48-54); this
  driver also aborts the acquisition after the read, as the upstream's own example does (Nuvu_cam_utils.py:250-263);
* ``x-cap.shafinulh.stop_acquisition.v1``: the native ``cam_stop`` (``ncCamAbort``, nc_camera.py:369-378) as the
  input-free safe-state action, and the same call as the e-stop.  The upstream stop aborts acquisition only; it does
  not change the detector temperature target, the EM gain or the shutter setting.

Every Fact cites a line of the clone at the pinned commit (c31964385d2e50f8a51b0a130cdb857bbf66779a).  This package
is model-authored and unreviewed, and its hardware backend never ran: the gate checks the fake backend only.
"""

from __future__ import annotations

import struct
import zlib
from typing import Any, Mapping

import numpy as np

from mhs.artifacts import publisher_from_context
from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The upstream wrapper the driver is built on.
CAM_UTILS = "userlib/user_devices/NuvuCamera/Nuvu_sdk/Nuvu_cam_utils.py"
#: The ctypes class that implements the wrapper's method bodies.
NC_CAMERA = "userlib/user_devices/NuvuCamera/Nuvu_sdk/nc_camera.py"
#: The module that loads the vendor binary at import time.
NC_API = "userlib/user_devices/NuvuCamera/Nuvu_sdk/NC_api.py"

EXPOSURE_REASON = (
    "no line of the clone states an exposure range: the setter only says the value is in milliseconds "
    "(nc_camera.py:219-226) and passes it to ncCamSetExposureTime without a range check (nc_camera.py:226-233); the "
    "site states the exposure range of its camera")
GAIN_REASON = (
    "no line of the clone states the calibrated EM gain range: it is queried from the camera at run time with "
    "getCalibratedEmGainRange (nc_camera.py:559-568); the site states the gain range it allows")


def _chunk(tag: bytes, payload: bytes) -> bytes:
    """One PNG chunk with its CRC (RFC 2083)."""
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(
        ">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)


def _png_gray16(frame: "np.ndarray") -> bytes:
    """Encode a 2-D unsigned 8/16-bit array as a lossless 16-bit grayscale PNG."""
    rows = np.ascontiguousarray(frame, dtype=">u2")
    height, width = rows.shape
    raw = b"".join(b"\x00" + rows[row].tobytes() for row in range(height))
    header = struct.pack(">IIBBBBB", int(width), int(height), 16, 0, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(raw, 9))
            + _chunk(b"IEND", b""))


def _frame(rows: Any, width: int, height: int) -> "np.ndarray":
    """The captured frame as rows x columns, using the geometry the camera reports.

    ``nc_camera.getImg`` builds its array with shape (width, height) (nc_camera.py:393-398), which is not the
    conventional rows x columns order; the camera's own width and height decide which orientation this frame has,
    and a shape that matches neither is a device fault rather than a value to guess.
    """
    array = np.asarray(rows)
    if array.ndim != 2:
        raise DriverFailed("MHS.DEVICE.FAULTED", f"the camera returned a {array.ndim}-dimensional frame")
    if array.dtype.kind != "u" or array.dtype.itemsize > 2:
        raise DriverFailed("MHS.DEVICE.FAULTED",
                           f"the camera returned {array.dtype}, not an 8/16-bit unsigned frame")
    if array.shape == (height, width):
        return array
    if array.shape == (width, height):
        return array.T
    raise DriverFailed("MHS.DEVICE.FAULTED",
                       f"frame shape {array.shape} does not match the reported {width}x{height} geometry")


class NuvuCamera(Driver):
    device_id = "nuvu-camera"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R2"
    native = "user_devices.NuvuCamera.Nuvu_sdk.Nuvu_cam_utils:NuvuCamUtils"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeNuvuCamUtils"}
    vendor, model = "Nuvu", "EMCCD camera (Nuvu SDK)"
    display_name = "Nuvu EMCCD camera (rax-labscript NuvuCamUtils)"
    tags = ["camera", "emccd", "imaging", "nuvu", "labscript"]
    facts = [
        Fact("NuvuCamUtils inherits nc_camera", source="upstream_code",
             ref=f"{CAM_UTILS}:23"),
        Fact("The NuvuCamUtils constructor opens the camera with openCam(nbBuff=4)", source="upstream_code",
             ref=f"{CAM_UTILS}:52"),
        Fact("NC_api selects libnuvu.so for ELF, nc_driver_x64.dll for 64-bit WindowsPE and nc_driver_Win32.dll "
             "for 32-bit WindowsPE using platform.architecture()", source="upstream_code", ref=f"{NC_API}:6-14"),
        Fact("camStart(nbrImg) starts acquisition of nbrImg images, and nbrImg 0 is continuous acquisition",
             source="upstream_code", ref=f"{NC_CAMERA}:354-367"),
        Fact("camAbort stops all image acquisition on the camera", source="upstream_code",
             ref=f"{NC_CAMERA}:369-378"),
        Fact("camIsAcquring queries the SDK with ncCamIsAcquiring and returns 1 while acquiring and 0 otherwise, "
             "despite a docstring copied from camStart", source="upstream_code", ref=f"{NC_CAMERA}:335-352"),
        Fact("NuvuCamUtils.cam_stop calls camAbort and clears the wrapper's isrunning flag", source="upstream_code",
             ref=f"{CAM_UTILS}:97-99"),
        Fact("get_image uses disconnect_if_error_real, flushes the read queue and returns getImg()",
             source="upstream_code", ref=f"{CAM_UTILS}:201-205"),
        Fact("getImg reads an image and copies its uint16 pointer with shape (width, height)", source="upstream_code",
             ref=f"{NC_CAMERA}:393-398"),
        Fact("The exposure time is set in milliseconds", source="upstream_code", ref=f"{NC_CAMERA}:219-226"),
        Fact("The readout mode is documented as 0=nothing, 1=EM, 2=CONV", source="upstream_code",
             ref=f"{NC_CAMERA}:152-159"),
        Fact("The trigger mode is documented as -3=CONT_HIGH_LOW, -2=EXT_HIGH_LOW_EXP, -1=EXT_HIGH_LOW, "
             "0=INTERNAL, 1=EXT_LOW_HIGH, 2=EXT_LOW_HIGH_EXP, 3=CONT_LOW_HIGH", source="upstream_code",
             ref=f"{NC_CAMERA}:180-192"),
        Fact("The shutter mode is documented as 0=NOT SET, 1=open, 2=closed, 3=auto", source="upstream_code",
             ref=f"{NC_CAMERA}:41"),
        Fact("The target detector temperature range is queried from the camera at run time with "
             "getTargetDetectorTempRange", source="upstream_code", ref=f"{NC_CAMERA}:415-425"),
        Fact("The calibrated EM gain range is queried from the camera at run time with getCalibratedEmGainRange",
             source="upstream_code", ref=f"{NC_CAMERA}:559-568"),
        Fact("getAllCamInfo queries the camera and returns the widths, exposure, temperatures, shutter mode, "
             "calibrated EM gain, raw gain, target detector temperature and trigger mode in one dictionary",
             source="upstream_code", ref=f"{NC_CAMERA}:607-671"),
        Fact("The repository's BLACS worker reads the detector temperature, raw and calibrated EM gain, exposure "
             "time and readout mode from getAllCamInfo", source="upstream_code",
             ref="userlib/user_devices/NuvuCamera/blacs_workers.py:66-73"),
        Fact("The BLACS worker's configure_acquisition calls cam_stop before cam_start", source="upstream_code",
             ref="userlib/user_devices/NuvuCamera/blacs_workers.py:57-63"),
        Fact("errorHandling closes the camera with noRaise=True and raises NuvuException for errors other than 27; "
             "error 27 raises without closing", source="upstream_code", ref=f"{NC_CAMERA}:95-113"),
        Fact("The disconnect_if_error_real decorator closes the camera and re-raises on an exception",
             source="upstream_code", ref=f"{CAM_UTILS}:76-84"),
        Fact("The upstream example acquires one image with cam_start(1), get_image(), cam_stop() and cam_close()",
             source="upstream_code", ref=f"{CAM_UTILS}:250-263"),
        Fact("The README states that the repository implemented Nuvu Camera python drivers", source="vendor_doc",
             ref="README.md:94"),
    ]
    safe_state = ("image acquisition aborted with camAbort (cam_stop) and the SDK acquisition query reports 0; "
                  "the detector temperature target, the EM gain and the shutter setting are not changed by that call")

    # -- reads ----------------------------------------------------------------------------------------------------
    def _info(self) -> Mapping[str, Any]:
        info = self.native.getAllCamInfo()
        if not isinstance(info, Mapping):
            raise DriverFailed("MHS.DEVICE.FAULTED", "getAllCamInfo did not return a dictionary")
        return info

    @read("acquiring", type="boolean",
          description="True while the SDK reports an acquisition (camIsAcquring queries ncCamIsAcquiring)")
    def acquiring(self):
        return self._acquisition_state()

    def _acquisition_state(self):
        state = self.native.camIsAcquring()
        if type(state) is not int or state not in (0, 1):
            raise DriverFailed("MHS.DEVICE.FAULTED", f"invalid SDK acquisition state: {state!r}")
        return state == 1

    def _abort_acquisition(self):
        self.native.cam_stop()
        if self._acquisition_state():
            raise DriverFailed("MHS.DEVICE.FAULTED", "the camera still reports acquisition after cam_stop")

    @read("exposure_time", unit="ms", description="Exposure time the camera holds, in milliseconds")
    def exposure_time(self):
        return float(self._info()["exposureTime"])

    @read("readout_mode", type="integer", unit="1",
          description="Readout mode: 0=nothing, 1=EM, 2=CONV")
    def readout_mode(self):
        return int(self._info()["currentReadoutMode"])

    @read("trigger_mode", type="integer", unit="1",
          description="Trigger mode from -3 (continuous high/low) to 3 (continuous low/high), 0=internal")
    def trigger_mode(self):
        return int(self._info()["currentTriggerMode"])

    @read("shutter_mode", type="integer", unit="1",
          description="Shutter mode: 0=NOT SET, 1=open, 2=closed, 3=auto")
    def shutter_mode(self):
        return int(self._info()["shutterMode"])

    @read("em_gain", type="integer", unit="1", description="Calibrated EM gain the camera holds")
    def em_gain(self):
        return int(self._info()["calibratedEmGain"])

    @read("detector_temperature", description="Current detector temperature in the SDK's unstated unit")
    def detector_temperature(self):
        return float(self._info()["componentTemp"]["detectorTemp"])

    @read("target_detector_temperature", description="Target detector temperature in the SDK's unstated unit")
    def target_detector_temperature(self):
        return float(self._info()["targetDetectorTemp"])

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("exposure_time", unit="ms", description="Exposure time in milliseconds, in the camera's own unit",
           limit=Limit.operator_required(EXPOSURE_REASON))
    def set_exposure_time(self, value):
        self.native.set_exposure_time(float(value))

    @write("readout_mode", type="integer", unit="1", description="Readout mode: 0=nothing, 1=EM, 2=CONV",
           limit=Limit(allowed=[0, 1, 2], source="upstream_code", ref=f"{NC_CAMERA}:155",
                       reason="setReadoutMode documents exactly the modes 0=nothing, 1=EM, 2=CONV"))
    def set_readout_mode(self, value):
        self.native.set_readout_mode(int(value))

    @write("trigger_mode", type="integer", unit="1",
           description="Trigger mode: -3, -2, -1, 0=internal, 1, 2, 3",
           limit=Limit(allowed=[-3, -2, -1, 0, 1, 2, 3], source="upstream_code", ref=f"{NC_CAMERA}:181-191",
                       reason="setTriggerMode documents exactly the modes -3 to 3"))
    def set_trigger_mode(self, value):
        self.native.set_trigger_mode(int(value))

    @write("shutter_mode", type="integer", unit="1",
           description="Shutter mode: 0=NOT SET, 1=open, 2=closed, 3=auto",
           limit=Limit(allowed=[0, 1, 2, 3], source="upstream_code", ref=f"{NC_CAMERA}:41",
                       reason="the nc_camera attribute documentation states exactly the shutter modes 0 to 3"))
    def set_shutter_mode(self, value):
        self.native.set_shutter_mode(int(value))

    @write("em_gain", type="integer", unit="1", description="Calibrated EM gain",
           limit=Limit.operator_required(GAIN_REASON))
    def set_em_gain(self, value):
        self.native.set_calibrated_em_gain(int(value))

    # -- capture --------------------------------------------------------------------------------------------------
    @action(cap="cap.sensing.image.v1",
            description="Start a single-image acquisition, read one frame, abort acquisition and publish the frame "
                        "as a 16-bit grayscale PNG artifact; the raw 2-D array is not an output field",
            input={"camera": Field("string",
                                   description="Camera selector; this package serves the one camera opened at "
                                               "start-up, so a value is accepted and does not select another "
                                               "camera"),
                   "exposure_ms": Field("number", unit="ms",
                                        description="Exposure time to apply before this frame, in milliseconds; "
                                                    "omit it to keep the configured exposure",
                                        limit=Limit.operator_required(EXPOSURE_REASON))})
    def capture(self, camera=None, exposure_ms=None):
        publisher = publisher_from_context(self.ctx)
        if publisher is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY",
                               "image capture needs the endpoint-owned artifact store (serve with --artifacts)")
        if exposure_ms is not None:
            self.native.set_exposure_time(float(exposure_ms))
        self.check_cancelled()
        self.native.cam_start(1)
        try:
            rows = self.native.get_image()
            info = self._info()
        finally:
            self._abort_acquisition()
        self.check_cancelled()
        width, height = int(info["width"]), int(info["height"])
        frame = _frame(rows, width, height)
        data = _png_gray16(frame)
        if len(data) > publisher.max_bytes:
            raise DriverFailed("MHS.DEVICE.NOT_READY",
                               f"the encoded {len(data)}-byte frame exceeds the artifact store bound "
                               f"{publisher.max_bytes}")
        descriptor = publisher.publish(data, "image/png")
        return {"image_ref": descriptor["uri"], "width": int(frame.shape[1]), "height": int(frame.shape[0]),
                "media_type": "image/png", "exposure_ms": float(info["exposureTime"])}

    # -- safety ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.shafinulh.stop_acquisition.v1", safe_state=True,
            description="Abort acquisition with cam_stop and require the SDK acquisition query to report 0; "
                        "an active or invalid state fails the stop",
            output={"acquiring": Field("boolean", description="False once acquisition has been aborted")})
    def stop_acquisition(self):
        self._abort_acquisition()
        return {"acquiring": False}

    @estop(native="cam_stop")
    def stop(self):
        """Abort acquisition and confirm the SDK reports it inactive, independently of the wrapper flag."""
        self._abort_acquisition()

    def teardown(self):
        self.native.cam_close()

"""OpenMHS driver for gh.bnl-atf/ophyd-basler: a Basler camera through the upstream ophyd Device.

A direct Driver over ``ophyd_basler.basler_camera:BaslerCamera`` (``ophyd_basler/basler_camera.py:21``).  The upstream
class is an ophyd Device that owns a pypylon ``InstantCamera``.  It reads the camera metadata while the camera is open,
configures trigger mode and pixel format, and performs an acquisition through ``stage`` -> ``grab_image`` ->
``unstage``; the camera's exposure is applied by ``stage`` from the ``exposure_time`` Signal (in milliseconds).

The card's helper is ``OphydDriver`` and its candidate class is ``cap.device.configure.v1``.  This package deviates:
``OphydDriver`` compiles only classic Signal get/set bindings, and cannot express the camera's ``stage`` /
``grab_image`` / ``unstage`` capture, the pylon ``StopGrabbing`` stop, or the image artifact.  A direct Driver is used
instead, and the deviation is recorded in ``RESULT.json``.

* reads: camera model, serial number, user-defined name, image shape, pixel levels, active format, payload size, grab
  timeout, exposure time and the last frame mean;
* write: ``exposure_time`` in milliseconds.  The source states the unit but no numeric range: ``stage`` reads
  ``ExposureTimeAbs.Min`` and ``ExposureTimeAbs.Max`` from the connected camera and clamps the request, so the
  deployment supplies the range through the operator overlay (``Limit.operator_required``);
* action: ``cap.sensing.image.v1`` stages the camera, grabs one frame, records its mean and returns the frame as a
  lossless PNG artifact.  The fake returns an 8 x 8 placeholder frame; the real frame shape is the ``image_shape``
  read from pylon;
* stop: the native pylon stop is ``camera_object.StopGrabbing`` (``basler_camera.py:158``); the e-stop calls it.  The
  upstream class documents no independent hardware emergency stop, so no ``estop_physical_ref`` is claimed.

Every Fact cites the clone at pinned commit ``5573459ca330f931ce49a1e53f0e89b834db85cc``.  The package is model-authored
and unreviewed (``reviewed_by`` is null); it was checked on the fake backend only, no camera was attached, and the
upstream package was never imported or run.  The hardware backend needs ``pypylon`` and the Basler runtime.
"""

import struct

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write
from mhs.pixels import encode_png_rows

SOURCE = "ophyd_basler/basler_camera.py"
PACKAGE_INIT = "ophyd_basler/__init__.py"


def _number(value, what):
    """One finite integer pixel; a float with a fractional part and a boolean are refused, not truncated."""
    if isinstance(value, bool):
        raise DriverFailed("MHS.DEVICE.FAULTED", f"{what} returned a boolean pixel")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise DriverFailed("MHS.DEVICE.FAULTED", f"{what} returned a non-numeric pixel") from exc
    if number != value:
        raise DriverFailed("MHS.DEVICE.FAULTED", f"{what} returned a fractional pixel")
    if not 0 <= number <= 65535:
        raise DriverFailed("MHS.DEVICE.FAULTED", f"{what} returned a pixel outside 0..65535")
    return number


def _rows(value):
    """A two-dimensional integer image as a list of rows; the fake and pypylon both return rows already."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (list, tuple)) or not value:
        raise DriverFailed("MHS.DEVICE.FAULTED", "grab_image returned no frame")
    rows = []
    for row in value:
        if hasattr(row, "tolist"):
            row = row.tolist()
        if not isinstance(row, (list, tuple)) or not row:
            raise DriverFailed("MHS.DEVICE.FAULTED", "grab_image returned an empty row")
        rows.append([_number(item, "grab_image") for item in row])
    height, width = len(rows), len(rows[0])
    if not (1 <= width <= 8192 and 1 <= height <= 8192):
        raise DriverFailed("MHS.DEVICE.FAULTED", "grab_image returned an image outside the 8192 x 8192 PNG bound")
    if any(len(row) != width for row in rows):
        raise DriverFailed("MHS.DEVICE.FAULTED", "grab_image returned rows of unequal length")
    return rows


def _mean(rows):
    total = sum(sum(row) for row in rows)
    return total / (len(rows) * len(rows[0]))


def _png(rows, publisher):
    """Lossless PNG of one two-dimensional Mono frame, in 8-bit or big-endian 16-bit samples."""
    height, width = len(rows), len(rows[0])
    sixteen = any(item > 255 for row in rows for item in row)
    if sixteen:
        def samples(row):
            out = bytearray(2 * len(row))
            for index, item in enumerate(row):
                struct.pack_into(">H", out, 2 * index, item)
            return bytes(out)
        depth = 16
    else:
        def samples(row):
            return bytes(row)
        depth = 8
    try:
        return encode_png_rows(width, height, depth, 0, (samples(row) for row in rows),
                               max_bytes=publisher.max_bytes), "image/png"
    except ValueError as exc:
        raise DriverFailed("MHS.DEVICE.FAULTED", f"the captured frame cannot be encoded as a PNG: {exc}") from exc


class BaslerCameraDevice(Driver):
    device_id = "basler-camera"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R1"
    native = "ophyd_basler.basler_camera:BaslerCamera"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeBaslerCamera"}
    vendor = "Basler"
    model = "Basler camera through pypylon (ophyd-basler)"
    display_name = "Basler camera (ophyd-basler)"
    tags = ["camera", "basler", "pypylon", "ophyd", "imaging"]
    safe_state = ("camera_object.StopGrabbing, the call grab_image itself makes after a frame, is sent to end a "
                  "running pylon grab; the capture's finally block unstages, which closes the camera, and outside a "
                  "capture the upstream leaves the camera closed. An imaging sensor with no actuator: the stop proves "
                  "no physical state; its effect while RetrieveResult waits or on a closed camera is pylon behaviour "
                  "outside the clone")

    facts = [
        Fact("BaslerCamera is an ophyd Device (basler_camera.py:21) whose components are image, mean, exposure_time, "
             "user_defined_name, camera_model, serial_number, image_shape, pixel_level_min, pixel_level_max, "
             "active_format, payload_size and grab_timeout", source="upstream_code", ref=f"{SOURCE}:21-33"),
        Fact("exposure_time is a config Signal whose source comment states the unit is milliseconds",
             source="upstream_code", ref=f"{SOURCE}:24"),
        Fact("The constructor enumerates pylon devices, creates and opens a pylon.InstantCamera, reads the "
             "user-defined name, model, serial number, shape, pixel levels, pixel format and payload size, sets the "
             "trigger mode and pixel format, and closes the camera", source="upstream_code", ref=f"{SOURCE}:73-94"),
        Fact("image_shape stores the pair (camera_object.Height(), camera_object.Width())",
             source="upstream_code", ref=f"{SOURCE}:85"),
        Fact("set_custom_images configures the pylon emulated camera from an image array or an image directory",
             source="upstream_code", ref=f"{SOURCE}:108-144"),
        Fact("grab_image starts grabbing one frame, retrieves it with grab_timeout, raises when GrabSucceeded is "
             "false, stops grabbing and returns the pylon array", source="upstream_code", ref=f"{SOURCE}:146-162"),
        Fact("trigger calls grab_image, writes the frame into the HDF5 dataset, publishes the datum id and the frame "
             "mean", source="upstream_code", ref=f"{SOURCE}:164-192"),
        Fact("stage creates the HDF5 resource and dataset, opens the camera, and writes ExposureTimeAbs (1e3 times "
             "exposure_time) only when that value lies within ExposureTimeAbs.Min..Max; a value outside is replaced "
             "in the exposure_time Signal by the minimum or maximum with a warning and is not written in that call",
             source="upstream_code", ref=f"{SOURCE}:194-263"),
        Fact("stage opens a new HDF5 file with mode 'x' at root_dir/YYYY/MM/DD/<uid>.h5 and creates its image "
             "dataset with a first frame filled with NaN", source="upstream_code", ref=f"{SOURCE}:196-227"),
        Fact("The upstream test fixture creates the dated directory tree under /tmp/basler with make_dir_tree",
             source="upstream_code", ref="ophyd_basler/tests/conftest.py:37-38"),
        Fact("unstage closes the pylon camera and the HDF5 file", source="upstream_code", ref=f"{SOURCE}:265-271"),
        Fact("The verbose output labels the grab_timeout value in milliseconds",
             source="upstream_code", ref=f"{SOURCE}:104"),
        Fact("The module imports pylon from pypylon at import time",
             source="upstream_code", ref=f"{SOURCE}:14"),
        Fact("available_devices enumerates the pylon transport layer's devices",
             source="upstream_code", ref=f"{PACKAGE_INIT}:27-34"),
        Fact("ExternalFileReference is an ophyd Signal that describes an image stored in an external file",
             source="upstream_code", ref=f"{PACKAGE_INIT}:11-24"),
    ]

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("camera_model", type="string", description="Camera model reported by pylon")
    def camera_model(self):
        return str(self.native.camera_model.get())

    @read("serial_number", type="string", description="Camera serial number reported by pylon")
    def serial_number(self):
        return str(self.native.serial_number.get())

    @read("user_defined_name", type="string", description="User-defined camera name reported by pylon")
    def user_defined_name(self):
        return str(self.native.user_defined_name.get())

    @read("image_shape", type="array", items="integer", length=2, unit="1",
          description="Current pylon frame shape as (height, width) in pixels")
    def image_shape(self):
        shape = self.native.image_shape.get()
        try:
            height, width = shape
        except (TypeError, ValueError) as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED", "image_shape is not a two-element sequence") from exc
        return [int(height), int(width)]

    @read("pixel_level_min", type="integer", unit="1", description="Minimum pixel level reported by pylon")
    def pixel_level_min(self):
        return int(self.native.pixel_level_min.get())

    @read("pixel_level_max", type="integer", unit="1", description="Maximum pixel level reported by pylon")
    def pixel_level_max(self):
        return int(self.native.pixel_level_max.get())

    @read("active_format", type="string", description="Active pylon pixel format")
    def active_format(self):
        return str(self.native.active_format.get())

    @read("payload_size", type="integer", unit="1",
          description="GigE transport payload size in bytes reported by pylon")
    def payload_size(self):
        return int(self.native.payload_size.get())

    @read("grab_timeout", type="integer", unit="ms",
          description="Timeout passed to pylon's RetrieveResult, in milliseconds")
    def grab_timeout(self):
        return int(self.native.grab_timeout.get())

    @read("exposure_time", unit="ms", description="Exposure time configured in the ophyd Signal, in milliseconds")
    def exposure_time(self):
        return float(self.native.exposure_time.get())

    @read("mean", unit="1", description="Mean pixel level of the last frame the driver captured")
    def mean(self):
        value = self.native.mean.get()
        return None if value is None else float(value)

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("exposure_time", unit="ms", description="Exposure time in milliseconds; the next capture applies it",
           limit=Limit.operator_required(
               "the clone states the exposure is in milliseconds (basler_camera.py:24) but no numeric range: the "
               "stage applies ExposureTimeAbs.Min/Max queried from the connected camera and clamps the request "
               "(basler_camera.py:237-263), so the site supplies the range of its camera"))
    def set_exposure_time(self, value):
        self.native.exposure_time.put(float(value))
        return float(self.native.exposure_time.get())

    # -- action ---------------------------------------------------------------------------------------------------
    @action(cap="cap.sensing.image.v1",
            input={"camera": Field("string",
                                   description="Camera selector; this package serves one configured camera, so the "
                                               "value is accepted and does not change the connection")},
            description="Stage the camera, grab one frame, record its mean and return it as a lossless PNG artifact")
    def capture(self, camera=None):
        from mhs.artifacts import publisher_from_context

        publisher = publisher_from_context(self.ctx)
        if publisher is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "capture requires an endpoint-owned artifact store")
        staged = False
        try:
            self.native.stage()
            staged = True
            self.check_cancelled()
            rows = _rows(self.native.grab_image())
            self.check_cancelled()
            self.native.mean.put(_mean(rows))
            self.check_cancelled()
        finally:
            if staged:
                self.native.unstage()
        data, media_type = _png(rows, publisher)
        descriptor = publisher.publish(data, media_type)
        return {"image_ref": descriptor["uri"], "width": len(rows[0]), "height": len(rows),
                "media_type": media_type}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="camera_object.StopGrabbing")
    def stop(self):
        """The pylon acquisition stop: StopGrabbing aborts the current single-frame grab."""
        self.native.camera_object.StopGrabbing()

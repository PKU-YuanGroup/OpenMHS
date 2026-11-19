"""OpenMHS driver for gh.pythondev0/zscan-optical-system: the Thorlabs DCC1545M camera.

A direct Driver (decorated methods) with a checked SDK adapter for the upstream class
``camera:ThorlabsCamera`` (``camera.py:9``). The source uses pyueye to initialize the camera, request a
1280 x 1024 Mono8 buffer and freeze one frame (``camera.py:20-72``). The adapter checks every SDK status;
a failed freeze cannot publish old buffer contents. The camera is the repository's measurement instrument:
``zscan.py:49`` calls ``capture_image`` once at every stage position.

The card lists two independent entry symbols and names ``PythonObjectDriver``.  This package serves the camera entry
symbol with a direct Driver because the camera's primary output is a frame that has to be published as an image
artifact, which the config-only PythonObjectDriver command table cannot express.  The other entry symbol, the
Aerotech stage (``stage.py:9``), is NOT COVERED: one package has one ``native`` class, and the stage is a separate
device and control path.  This deviation is recorded in RESULT.json.

* reads: the configured allocation width and height the upstream constructor stores;
* one action: ``cap.sensing.image.v1`` calls the checked native ``capture_image``, validates the returned Mono8 array, encodes
  it as a lossless PNG and publishes it through the endpoint-owned artifact store.  The fake returns an 8 x 8
  placeholder frame; the real camera frame is 1280 x 1024;
* no Limit: the camera has no numeric command input.  The only optional catalogue input this package serves is the
  camera selector, which is accepted and does not change the one configured camera;
* no physical actuator: the camera captures data only, so the declared risk is R0 (MHS/spec/04-safety.md lists camera
  capture as R0).  The endpoint's software e-stop latches and refuses further captures; this driver does not claim a
  native stop, because the only native stop-shaped call is ``release``, which frees the image memory and exits the
  camera and cannot be undone without constructing a new ThorlabsCamera.  ``release`` is the teardown.

Every Fact cites the clone at the pinned commit ``114c2838f5c3cc7a5a211ed34b38f0745c386f74``.  This package is
model-authored and unreviewed (``reviewed_by`` is null).  It was checked on the fake backend only; no camera was
attached, the upstream package was never imported or run while authoring, and no hardware run is claimed.  The hardware
backend needs ``pyueye``, the IDS uEye SDK and the upstream ``camera.py`` on the deployment's source path.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, action, read
from mhs.pixels import encode_png_rows

SOURCE = "camera.py"
NOTEBOOK = "zscan.py"
README = "README.md"


def _number(value):
    """One finite Mono8 sample; a boolean, a fraction or a value outside 0..255 is refused, never truncated."""
    if isinstance(value, bool):
        raise DriverFailed("MHS.DEVICE.FAULTED", "capture_image returned a boolean pixel")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise DriverFailed("MHS.DEVICE.FAULTED", "capture_image returned a non-numeric pixel") from exc
    if number != value:
        raise DriverFailed("MHS.DEVICE.FAULTED", "capture_image returned a fractional pixel")
    if not 0 <= number <= 255:
        raise DriverFailed("MHS.DEVICE.FAULTED", "capture_image returned a pixel outside the Mono8 range 0..255")
    return number


def _rows(value):
    """A two-dimensional Mono8 image as a list of rows; the native array and the fake list are both accepted."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (list, tuple)) or not value:
        raise DriverFailed("MHS.DEVICE.FAULTED", "capture_image returned no frame")
    rows = []
    for row in value:
        if hasattr(row, "tolist"):
            row = row.tolist()
        if not isinstance(row, (list, tuple)) or not row:
            raise DriverFailed("MHS.DEVICE.FAULTED", "capture_image returned an empty row")
        rows.append([_number(item) for item in row])
    height, width = len(rows), len(rows[0])
    if not (1 <= width <= 8192 and 1 <= height <= 8192):
        raise DriverFailed("MHS.DEVICE.FAULTED", "capture_image returned an image outside the 8192 x 8192 PNG bound")
    if any(len(row) != width for row in rows):
        raise DriverFailed("MHS.DEVICE.FAULTED", "capture_image returned rows of unequal length")
    return rows


def _png(rows, publisher):
    """Lossless 8-bit grayscale PNG of one Mono8 frame, bounded by the endpoint's per-artifact limit."""
    height, width = len(rows), len(rows[0])
    try:
        return encode_png_rows(width, height, 8, 0, (bytes(row) for row in rows),
                               max_bytes=publisher.max_bytes)
    except ValueError as exc:
        raise DriverFailed("MHS.DEVICE.FAULTED",
                           f"the captured frame cannot be encoded as a PNG: {exc}") from exc


class ZscanCamera(Driver):
    device_id = "zscan-camera"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R0"
    native = "camera:ThorlabsCamera"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeThorlabsCamera"}
    vendor = "Thorlabs"
    model = "DCC1545M"
    display_name = "Thorlabs DCC1545M camera (zscan-optical-system)"
    tags = ["camera", "monochrome", "ueye", "pyueye", "zscan", "imaging"]
    facts = [
        Fact("The project synchronizes a Thorlabs DCC1545M camera with an Aerotech ANT130LZ nanopositioner",
             source="vendor_doc", ref=f"{README}:10"),
        Fact("The hardware table names the Thorlabs DCC1545M (CMOS Monochrome, 1280 x 1024) and pyueye (uEye SDK) "
             "as the camera and its driver", source="vendor_doc", ref=f"{README}:18"),
        Fact("The installation note says pyueye requires the IDS uEye SDK to be installed on the system",
             source="vendor_doc", ref=f"{README}:85"),
        Fact("camera.py imports ueye from pyueye", source="upstream_code", ref=f"{SOURCE}:5"),
        Fact("camera.py defines the camera interface class ThorlabsCamera", source="upstream_code", ref=f"{SOURCE}:9"),
        Fact("ThorlabsCamera.__init__ takes a device_id argument whose default is 0; the default is a constructor "
             "default, not a device bound", source="upstream_code", ref=f"{SOURCE}:20-25"),
        Fact("The constructor sets width to 1280 and height to 1024 pixels", source="upstream_code",
             ref=f"{SOURCE}:28-29"),
        Fact("The constructor calls is_SetColorMode with IS_CM_MONO8 without checking its return status",
             source="upstream_code", ref=f"{SOURCE}:40"),
        Fact("The constructor calls is_AllocImageMem for a 1280 x 1024 8-bit buffer and is_SetImageMem without "
             "checking either return status",
             source="upstream_code", ref=f"{SOURCE}:43-47"),
        Fact("capture_image calls is_FreezeVideo(IS_WAIT) without checking its return status, then copies the "
             "active image memory with get_data and reshapes it to (height, width)",
             source="upstream_code", ref=f"{SOURCE}:62-67"),
        Fact("release calls is_FreeImageMem and is_ExitCamera without checking either return status",
             source="upstream_code", ref=f"{SOURCE}:69-72"),
        Fact("The experiment calls camera.capture_image once for each stage position", source="upstream_code",
             ref=f"{NOTEBOOK}:44-49"),
        Fact("The experiment constructs ThorlabsCamera(device_id=0) and AerotechStage(axis_name='Z') as separate "
             "objects", source="upstream_code", ref=f"{NOTEBOOK}:75-76"),
        Fact("AerotechStage is a separate stage class in stage.py", source="upstream_code", ref="stage.py:9"),
        Fact("requirements.txt lists pyueye as the camera dependency", source="upstream_code",
             ref="requirements.txt:5"),
    ]
    safe_state = ("no actuator: the camera captures only; a latched endpoint refuses further captures, and a native "
                  "is_FreezeVideo call that has already started is not aborted by this driver")

    # -- reads -------------------------------------------------------------------------------------------------
    @read("configured_width", type="integer", unit="1",
          description="Image width in pixels the upstream constructor allocates (camera.py:28,43-46)")
    def configured_width(self):
        return int(self.native.width)

    @read("configured_height", type="integer", unit="1",
          description="Image height in pixels the upstream constructor allocates (camera.py:29,43-46)")
    def configured_height(self):
        return int(self.native.height)

    # -- action ------------------------------------------------------------------------------------------------
    @action(cap="cap.sensing.image.v1",
            input={"camera": Field("string",
                                   description="Camera selector; this package serves one configured camera, so the "
                                               "value is accepted and does not change the connection")},
            description="Capture one frozen Mono8 frame and publish it as a lossless 8-bit grayscale PNG artifact")
    def capture(self, camera=None):
        from mhs.artifacts import publisher_from_context

        publisher = publisher_from_context(self.ctx)
        if publisher is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "capture requires an endpoint-owned artifact store")
        self.check_cancelled()
        frame = self.native.capture_image()
        self.check_cancelled()
        rows = _rows(frame)
        self.check_cancelled()
        data = _png(rows, publisher)
        self.check_cancelled()
        descriptor = publisher.publish(data, "image/png")
        return {"image_ref": descriptor["uri"], "width": len(rows[0]), "height": len(rows),
                "media_type": "image/png"}

    # -- lifecycle ---------------------------------------------------------------------------------------------
    def teardown(self):
        """Free the native image memory and exit the camera when the endpoint closes."""
        self.native.release()

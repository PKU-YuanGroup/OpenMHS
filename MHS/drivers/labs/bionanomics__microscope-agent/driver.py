"""OpenMHS driver for gh.bionanomics/microscope-agent: a Baumer GenICam camera.

A direct Driver (decorated methods) over the upstream class
``acquisition.backends.baumer_genicam:BaumerGenICam`` (``acquisition/backends/baumer_genicam.py:73``).  The class is
the repository's primary capture path: it opens a GenTL producer through ``harvesters``, streams frames from the
Baumer VCXU-23C and writes each captured frame as a timestamped RGB PNG (``baumer_genicam.py:16-21,183-258``).  It is
explicitly capture-only and has no stage control (``baumer_genicam.py:73-80``).

The card names ``McpClientDriver`` because the repository also ships an MCP server.  That helper describes a finite
MCP tool contract over an injected peer; it cannot express this camera class's constructor, settings node map or
``capture()`` -> ``Path`` method without inventing a transport.  The confirmed entry symbol is a plain Python camera
class, so this package uses a direct Driver and records the deviation in ``RESULT.json``.

* reads: exposure time (us), gain (unitless), pixel format, balance-white-auto mode and the camera-reported exposure
  and gain ranges, all from ``get_settings()``;
* writes: exposure time and gain through ``set_settings()``.  The clone's ``get_settings`` docstring records the live
  VCXU-23C ranges (``baumer_genicam.py:111-117``): exposure 28 to 60,000,000 us and gain 1.0 to 251.1875.  The method
  itself re-checks the connected camera's live min/max and raises ValueError rather than clamping
  (``baumer_genicam.py:150-179``);
* action: ``cap.sensing.image.v1`` calls ``capture()`` and publishes the exact PNG bytes it wrote as a lossless image
  artifact.  The image dimensions come from the PNG's own IHDR, not from a constructor default;
* stop: the native stop is ``close()``, which stops and destroys the acquirer and resets the harvester
  (``baumer_genicam.py:260-263``).  The class offers no independent hardware emergency stop, so no
  ``estop_physical_ref`` is claimed.  The declared risk is R1, the card floor: a camera acquisition does not move a
  stage, dispense fluid, heat a sample, emit a laser or drive a robot.  Only the constructor creates the acquirer
  (``baumer_genicam.py:101-102``), so after an e-stop the upstream object cannot read settings or capture again; an
  operator reset clears the latch but not that, and the backend must be loaded again.  The default fake keeps serving
  after ``close`` (the gate reads the state after its e-stop); its ``destroy_on_close`` switch models the upstream
  object and the package tests use it.

Scope: the repository's MCP server drives a Nikon Ti2-E stage and this camera (README.md:3-5).  The stage
(``acquisition/backends/nis_sdk.py``), its file-flag e-stop and the MCP tools are NOT COVERED; this package serves the
card's one entry symbol, the camera.  ``capture`` drains queued frames with a 0.01 s fetch timeout until a fetch fails
(``baumer_genicam.py:206-211``), so it ends only once the camera delivers frames less often than every 0.01 s.

Every Fact cites the pinned clone at commit ``3aef391397deb42f0a1b814091eb2e4b3fe8ed5a``.  This package is
model-authored and unreviewed (``reviewed_by`` is null).  It was checked on the fake backend only; no camera was
attached, the upstream package was never imported or run, and no hardware run is claimed.  The hardware backend needs
the upstream camera optional dependencies (``harvesters``, ``genicam`` and ``opencv-python``) and a GenTL producer.
"""

import os
import struct

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write
from mhs.pixels import PNG_SIGNATURE

SOURCE = "acquisition/backends/baumer_genicam.py"

# The clone's get_settings docstring records these live VCXU-23C ranges (SOURCE:111-117).  They are used as limits only
# for the two settings the class exposes; set_settings re-checks the camera's own reported node-map min/max.
EXPOSURE_MIN_US = 28
EXPOSURE_MAX_US = 60_000_000
GAIN_MIN = 1.0
GAIN_MAX = 251.1875


def _settings(native):
    """The upstream get_settings() dict, with the keys this driver reads checked for presence."""
    settings = native.get_settings()
    if not isinstance(settings, dict):
        raise DriverFailed("MHS.DEVICE.FAULTED", "BaumerGenICam.get_settings did not return a dict")
    return settings


def _number(value, what):
    """One finite number from a settings dict; a boolean or non-number is refused, never coerced."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DriverFailed("MHS.DEVICE.FAULTED", f"{what} returned a non-numeric value")
    return float(value)


def _pair(value, what):
    """A two-element numeric range as a list of two finite numbers."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise DriverFailed("MHS.DEVICE.FAULTED", f"{what} did not return a two-element range")
    return [_number(item, what) for item in value]


def _capture_file(path):
    """Read the complete PNG that BaumerGenICam.capture wrote, with bounded size and dimensions."""
    if not isinstance(path, (str, bytes, os.PathLike)):
        raise DriverFailed("MHS.DEVICE.FAULTED", "BaumerGenICam.capture did not return a filesystem path")
    try:
        with open(path, "rb") as stream:
            data = stream.read()
    except OSError as exc:
        raise DriverFailed("MHS.DEVICE.FAULTED",
                           f"the captured PNG cannot be read: {exc}", native_code=getattr(exc, "errno", None)) from exc
    if not isinstance(data, (bytes, bytearray)) or not bytes(data).startswith(PNG_SIGNATURE):
        raise DriverFailed("MHS.DEVICE.FAULTED", "BaumerGenICam.capture did not write a PNG file")
    if len(data) < 33 or bytes(data[12:16]) != b"IHDR":
        raise DriverFailed("MHS.DEVICE.FAULTED", "the captured PNG has no complete IHDR header")
    width, height = struct.unpack(">II", bytes(data[16:24]))
    if not (1 <= width <= 8192 and 1 <= height <= 8192):
        raise DriverFailed("MHS.DEVICE.FAULTED",
                           f"the captured PNG is {width} x {height}, outside the 8192 pixel image bound")
    return bytes(data), width, height


class BaumerCamera(Driver):
    device_id = "baumer_camera"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R1"
    native = "acquisition.backends.baumer_genicam:BaumerGenICam"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeBaumerGenICam"}
    vendor = "Baumer"
    model = "VCXU-23C through GenICam/GenTL (harvesters)"
    display_name = "Baumer VCXU-23C GenICam camera"
    tags = ["camera", "baumer", "genicam", "gentl", "imaging", "microscope"]
    safe_state = ("the GenTL acquirer is stopped and destroyed by BaumerGenICam.close, so no further frame is "
                  "requested; nothing re-creates it, so reads and captures fail until the backend is loaded again")

    facts = [
        Fact("The clone's module comment makes BaumerGenICam.capture the primary capture path, called by "
             "mcp_server.loop_tools.get_image()", source="upstream_code", ref=f"{SOURCE}:16-21"),
        Fact("BaumerGenICam is capture-only and explicitly has no stage control",
             source="upstream_code", ref=f"{SOURCE}:73-80"),
        Fact("The constructor finds GenTL .cti producers and raises RuntimeError when no producer or no camera is "
             "found; it then creates and starts one acquirer", source="upstream_code", ref=f"{SOURCE}:82-103"),
        Fact("get_settings reads the live GenICam node map: ExposureTime value and min/max, Gain value and min/max, "
             "PixelFormat and, when exposed, BalanceWhiteAuto", source="upstream_code", ref=f"{SOURCE}:105-140"),
        Fact("The get_settings docstring records a live VCXU-23C ExposureTime range of 28 to 60,000,000 us and a "
             "unitless Gain range of 1.0 to 251.1875", source="upstream_code", ref=f"{SOURCE}:111-117"),
        Fact("set_settings forces ExposureAuto and GainAuto to Off and raises ValueError, never clamping, when a "
             "requested exposure or gain is outside the camera-reported range",
             source="upstream_code", ref=f"{SOURCE}:142-181"),
        Fact("capture drains queued frames, fetches a live frame with a 5 s timeout, dispatches on PixelFormat and "
             "saves an RGB PNG named with a timestamp and the capture count",
             source="upstream_code", ref=f"{SOURCE}:183-258"),
        Fact("capture supports BGR8, RGB8, Mono8 and Bayer formats and raises RuntimeError for any other "
             "PixelFormat", source="upstream_code", ref=f"{SOURCE}:218-255"),
        Fact("close stops and destroys the acquirer and resets the harvester",
             source="upstream_code", ref=f"{SOURCE}:260-263"),
        Fact("The constructor creates the acquirer with harvester.create(0) and starts it",
             source="upstream_code", ref=f"{SOURCE}:101-102"),
        Fact("capture's drain loop fetches with a 0.01 s timeout and leaves the loop only when a fetch raises",
             source="upstream_code", ref=f"{SOURCE}:206-211"),
        Fact("The README describes an MCP server for a Nikon Ti2-E microscope and a Baumer GenICam camera",
             source="vendor_doc", ref="README.md:3-5"),
        Fact("CAPTURE_DIR is acquisition.paths.captures_dir(), so the output directory follows the upstream data-root "
             "selection rather than this driver", source="upstream_code", ref=f"{SOURCE}:41-44"),
        Fact("The camera path depends on the optional harvesters, genicam and opencv-python packages",
             source="upstream_code", ref=f"{SOURCE}:24-28"),
    ]

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("exposure_time_us", unit="us", description="Current camera exposure time in microseconds")
    def exposure_time_us(self):
        return _number(_settings(self.native).get("exposure_time_us"), "exposure_time_us")

    @read("exposure_time_range_us", type="array", items="number", length=2, unit="us",
          description="Camera-reported valid exposure range as (minimum, maximum) in microseconds")
    def exposure_time_range_us(self):
        return _pair(_settings(self.native).get("exposure_time_range_us"), "exposure_time_range_us")

    @read("gain", unit="1", description="Current camera gain on the camera's own unitless scale")
    def gain(self):
        return _number(_settings(self.native).get("gain"), "gain")

    @read("gain_range", type="array", items="number", length=2, unit="1",
          description="Camera-reported valid gain range on the camera's own unitless scale")
    def gain_range(self):
        return _pair(_settings(self.native).get("gain_range"), "gain_range")

    @read("pixel_format", type="string", description="PixelFormat currently declared by the camera node map")
    def pixel_format(self):
        value = _settings(self.native).get("pixel_format")
        if not isinstance(value, str):
            raise DriverFailed("MHS.DEVICE.FAULTED", "pixel_format returned a non-string value")
        return value

    @read("balance_white_auto", type=Field("string", nullable=True,
                                           description="BalanceWhiteAuto mode, or null when this camera does not "
                                                       "expose the node"))
    def balance_white_auto(self):
        value = _settings(self.native).get("balance_white_auto")
        if value is not None and not isinstance(value, str):
            raise DriverFailed("MHS.DEVICE.FAULTED", "balance_white_auto returned a non-string value")
        return value

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("exposure_time_us", unit="us", description="Exposure time in microseconds; the next capture applies it",
           limit=Limit(min=EXPOSURE_MIN_US, max=EXPOSURE_MAX_US, source="upstream_code", ref=f"{SOURCE}:112"))
    def set_exposure_time_us(self, value):
        settings = self.native.set_settings(exposure_time_us=float(value))
        if not isinstance(settings, dict):
            settings = _settings(self.native)
        return _number(settings.get("exposure_time_us"), "exposure_time_us")

    @write("gain", unit="1", description="Gain on the camera's own unitless scale; the next capture applies it",
           limit=Limit(min=GAIN_MIN, max=GAIN_MAX, source="upstream_code", ref=f"{SOURCE}:112-113"))
    def set_gain(self, value):
        settings = self.native.set_settings(gain=float(value))
        if not isinstance(settings, dict):
            settings = _settings(self.native)
        return _number(settings.get("gain"), "gain")

    # -- action ---------------------------------------------------------------------------------------------------
    @action(cap="cap.sensing.image.v1",
            input={"camera": Field("string",
                                   description="Camera selector; this package serves one configured camera, so the "
                                               "value is accepted and does not change the connection")},
            description="Capture one live frame and publish the PNG BaumerGenICam wrote as a lossless image "
                        "artifact")
    def capture(self, camera=None):
        from mhs.artifacts import publisher_from_context

        publisher = publisher_from_context(self.ctx)
        if publisher is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "capture requires an endpoint-owned artifact store")
        path = self.native.capture()
        self.check_cancelled()
        data, width, height = _capture_file(path)
        if len(data) > publisher.max_bytes:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"the captured PNG is {len(data)} bytes, above the endpoint artifact bound of "
                               f"{publisher.max_bytes} bytes")
        descriptor = publisher.publish(data, "image/png")
        return {"image_ref": descriptor["uri"], "width": width, "height": height, "media_type": "image/png"}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="close")
    def stop(self):
        """The native stop this class offers: stop and destroy the acquirer, then reset the harvester."""
        self.native.close()

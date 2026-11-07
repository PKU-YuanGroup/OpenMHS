"""OpenMHS driver for gh.fretchen/synqs_devices: the Andor Solis camera of the SynQS labscript devices.

The upstream package is a collection of independent labscript devices.  This package serves the camera device named
by the card's first entry symbol, ``AndorSolis.blacs_workers:AndorCamera`` (blacs_workers.py:16), a direct Driver over
the upstream object: the interface is a dictionary of acquisition attributes plus methods, not a table of serial
command words, so the card's SerialDriver cannot express it (DEVIATION FROM THE CARD, recorded in RESULT.json).

* reads: the acquisition attributes of the camera (exposure, frame size, binning, accumulations, kinetics,
  acquisition/trigger modes, cooling state and temperature set point);
* writes: exposure time and temperature set point are ``Limit.operator_required`` because the clone derives their
  ranges from the camera at run time (``GetAcquisitionTimings`` and ``GetTemperatureRange``) and no text file states
  a numeric bound; the acquisition and trigger words are limited to the modes the clone's dictionaries accept;
* action: ``cap.sensing.image.v1`` calls the upstream ``snap``, which configures, acquires and downloads one image;
  its optional ``width``, ``height`` and ``exposure_ms`` inputs are also ``Limit.operator_required`` (the clone
  states no numeric ROI or exposure range), and the image is written to a temporary 8-bit PGM file whose path and
  size are the receipt;
* the native stop is ``abort_acquisition`` (blacs_workers.py:105-107): the e-stop aborts the current acquisition.

NOT COVERED: the image array itself.  The receipt carries an ``image_ref`` path (the catalogue's image class), not
the pixel data; the fake returns an 8 x 8 placeholder frame while the upstream default acquisition attributes name a
2560 x 2160 frame.  The hardware backend loads the proprietary Andor SDK3 (atmcd64d.dll/atmcd32d.dll) and is
Windows-only; the clone's README also does not document the AndorSolis device.  Nothing here ran on hardware.

Every Fact and Limit cites a line of the clone at the pinned commit (ec4bb24639e9d0d4cb707e1c2a6296a47dfe9f02).
This package is model-authored and unreviewed; it is checked on the fake backend only and its evidence is
``contract_checked``, never an MHS-Device level.
"""

import os
import tempfile

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

WORKERS = "AndorSolis/blacs_workers.py"
UTILS = "AndorSolis/andor_sdk/andor_utils.py"
SDK = "AndorSolis/andor_sdk/andor_solis.py"

#: The acquisition modes of AndorCam.setup_acquisition (andor_utils.py:322-327).
ACQUISITION_MODES = ["single", "accumulate", "kinetic_series", "fast_kinetics", "run_till_abort"]
#: The trigger modes of AndorCam.setup_trigger (andor_utils.py:439-444).
TRIGGER_MODES = ["internal", "external", "external_start", "external_exposure"]
#: The trigger edges of AndorCam.setup_trigger (andor_utils.py:446).
TRIGGER_EDGES = ["rising", "falling"]


def _first_frame(image):
    """The first 2-D frame of the object ``AndorCamera.snap`` returned (it may be a stack of images)."""
    if image is None:
        raise DriverFailed("MHS.DEVICE.FAULTED", "snap returned no image")
    if hasattr(image, "tolist"):
        image = image.tolist()
    if not isinstance(image, (list, tuple)) or not image:
        raise DriverFailed("MHS.DEVICE.FAULTED", f"snap returned an unusable image ({type(image).__name__})")
    # A stack of frames (the upstream docstring says this may be a 3-D array): use the first frame.
    if isinstance(image[0], (list, tuple)) and image[0] and isinstance(image[0][0], (list, tuple)):
        image = image[0]
    if isinstance(image[0], (list, tuple)):
        rows = [list(row) for row in image]
    else:
        rows = [list(image)]
    if not rows or not rows[0]:
        raise DriverFailed("MHS.DEVICE.FAULTED", "snap returned an empty frame")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise DriverFailed("MHS.DEVICE.FAULTED", "snap returned a frame whose rows have different widths")
    return rows


def _write_pgm(rows):
    """Write one frame as a binary PGM file in the system temporary directory and return (path, width, height)."""
    height, width = len(rows), len(rows[0])
    pixels = bytearray()
    for row in rows:
        for value in row:
            try:
                number = int(round(float(value)))
            except (TypeError, ValueError) as exc:
                raise DriverFailed("MHS.DEVICE.FAULTED", "snap returned a non-numeric pixel") from exc
            pixels.append(max(0, min(255, number)))
    handle, path = tempfile.mkstemp(prefix="andor-solis-", suffix=".pgm")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(f"P5\n{width} {height}\n255\n".encode("ascii"))
            stream.write(bytes(pixels))
    except BaseException:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    return path, width, height


class AndorSolis(Driver):
    device_id = "andor-solis"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R1"
    native = "AndorSolis.blacs_workers:AndorCamera"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeAndorCamera"}
    vendor = "Andor Technology"
    model = "Andor Solis camera (Andor SDK3)"
    display_name = "Andor Solis camera (synqs_devices)"
    tags = ["camera", "andor", "solis", "labscript", "blacs", "imaging"]
    facts = [
        Fact("AndorCamera wraps the upstream AndorCam object and takes its default acquisition attributes as the "
             "attribute dictionary", source="upstream_code", ref=f"{WORKERS}:20-22"),
        Fact("get_attribute returns the current value of one named acquisition attribute", source="upstream_code",
             ref=f"{WORKERS}:33-34"),
        Fact("set_attribute stores a named acquisition attribute in the dictionary", source="upstream_code",
             ref=f"{WORKERS}:27-28"),
        Fact("configure_acquisition hands the whole attribute dictionary to AndorCam.setup_acquisition",
             source="upstream_code", ref=f"{WORKERS}:44-45"),
        Fact("snap configures the acquisition, acquires, downloads the images and returns them", source="upstream_code",
             ref=f"{WORKERS}:36-42"),
        Fact("abort_acquisition calls the camera's abort and records that the abort happened", source="upstream_code",
             ref=f"{WORKERS}:105-107"),
        Fact("stop_acquisition is a no-op (pass); abort_acquisition is the upstream stop path", source="upstream_code",
             ref=f"{WORKERS}:102-107"),
        Fact("AndorCam.setup_acquisition accepts the acquisition modes single, accumulate, kinetic_series, "
             "fast_kinetics and run_till_abort", source="upstream_code", ref=f"{UTILS}:322-328"),
        Fact("AndorCam.setup_acquisition sets the exposure time with SetExposureTime and reads the actual timings "
             "back with GetAcquisitionTimings", source="upstream_code", ref=f"{UTILS}:350-358"),
        Fact("AndorCam.setup_trigger accepts the trigger modes internal, external, external_start and "
             "external_exposure, and the edges rising and falling", source="upstream_code",
             ref=f"{UTILS}:439-446"),
        Fact("enable_cooldown refuses a temperature set point outside self.temperature_range, which "
             "initialize_camera fills from GetTemperatureRange()", source="upstream_code", ref=f"{UTILS}:93-94"),
        Fact("enable_cooldown compares the requested set point with self.temperature_range before switching the "
             "cooler on", source="upstream_code", ref=f"{UTILS}:141-147"),
        Fact("AndorCam.shutdown refuses to shut down while the camera is armed", source="upstream_code",
             ref=f"{UTILS}:656-662"),
        Fact("The SDK binding loads atmcd64d.dll or atmcd32d.dll with ctypes and names the Andor SDK3 install "
             "directory only on Windows", source="upstream_code", ref=f"{SDK}:21-44"),
        Fact("The upstream default acquisition attributes configure a 2560 x 2160 frame, 1 x 1 binning and a "
             "20 ms exposure; they are defaults, not device limits", source="upstream_code",
             ref=f"{UTILS}:13-45"),
    ]
    safe_state = "acquisition aborted by abort_acquisition; the camera is disarmed and captures no further frame"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("exposure_time", unit="s", description="Requested exposure time of the acquisition attributes")
    def exposure_time(self):
        return float(self.native.get_attribute("exposure_time"))

    @read("frame_width", type="integer", unit="1", description="Configured frame width in pixels")
    def frame_width(self):
        return int(self.native.get_attribute("width"))

    @read("frame_height", type="integer", unit="1", description="Configured frame height in pixels")
    def frame_height(self):
        return int(self.native.get_attribute("height"))

    @read("x_binning", type="integer", unit="1", description="Horizontal binning factor")
    def x_binning(self):
        return int(self.native.get_attribute("xbin"))

    @read("y_binning", type="integer", unit="1", description="Vertical binning factor")
    def y_binning(self):
        return int(self.native.get_attribute("ybin"))

    @read("accumulations", type="integer", unit="1", description="Number of accumulations per acquisition")
    def accumulations(self):
        return int(self.native.get_attribute("number_accumulations"))

    @read("kinetics", type="integer", unit="1", description="Number of kinetic frames per acquisition")
    def kinetics(self):
        return int(self.native.get_attribute("number_kinetics"))

    @read("acquisition_mode", type="string", description="Acquisition mode word used by setup_acquisition")
    def acquisition_mode(self):
        return str(self.native.get_attribute("acquisition"))

    @read("trigger_mode", type="string", description="Trigger mode word used by setup_trigger")
    def trigger_mode(self):
        return str(self.native.get_attribute("trigger"))

    @read("trigger_edge", type="string", description="Trigger edge word used by setup_trigger")
    def trigger_edge(self):
        return str(self.native.get_attribute("trigger_edge"))

    @read("cooldown", type="boolean", description="True when setup_acquisition enables the cooler")
    def cooldown(self):
        return bool(self.native.get_attribute("cooldown"))

    @read("temperature_setpoint", unit="Cel", description="Detector temperature set point used when cooling is on")
    def temperature_setpoint(self):
        return float(self.native.get_attribute("temperature"))

    # -- writes -----------------------------------------------------------------------------------------------
    @write("exposure_time", unit="s", description="Requested exposure time, applied by the next snap",
           limit=Limit.operator_required(
               "the clone passes the exposure to SetExposureTime and reads the actual timing back with "
               "GetAcquisitionTimings, but no text file states a numeric exposure range; the site sets it"))
    def set_exposure_time(self, value):
        self.native.set_attribute("exposure_time", float(value))
        return float(self.native.get_attribute("exposure_time"))

    @write("temperature_setpoint", unit="Cel",
           description="Detector temperature set point, applied by the next snap when cooling is on",
           limit=Limit.operator_required(
               "enable_cooldown validates the set point against self.temperature_range, which is queried from the "
               "camera with GetTemperatureRange() at initialization; the clone states no fixed range, so the site "
               "sets it"))
    def set_temperature_setpoint(self, value):
        self.native.set_attribute("temperature", float(value))
        return float(self.native.get_attribute("temperature"))

    @write("acquisition_mode", type="string", description="Acquisition mode word used by setup_acquisition",
           limit=Limit(allowed=ACQUISITION_MODES, source="upstream_code", ref=f"{UTILS}:322-327"))
    def set_acquisition_mode(self, value):
        self.native.set_attribute("acquisition", str(value))
        return str(self.native.get_attribute("acquisition"))

    @write("trigger_mode", type="string", description="Trigger mode word used by setup_trigger",
           limit=Limit(allowed=TRIGGER_MODES, source="upstream_code", ref=f"{UTILS}:439-444"))
    def set_trigger_mode(self, value):
        self.native.set_attribute("trigger", str(value))
        return str(self.native.get_attribute("trigger"))

    @write("trigger_edge", type="string", description="Trigger edge word used by setup_trigger",
           limit=Limit(allowed=TRIGGER_EDGES, source="upstream_code", ref=f"{UTILS}:446"))
    def set_trigger_edge(self, value):
        self.native.set_attribute("trigger_edge", str(value))
        return str(self.native.get_attribute("trigger_edge"))

    @write("cooldown", type="boolean", description="Enable the detector cooler in setup_acquisition")
    def set_cooldown(self, value):
        self.native.set_attribute("cooldown", bool(value))
        return bool(self.native.get_attribute("cooldown"))

    # -- action -----------------------------------------------------------------------------------------------
    @action(cap="cap.sensing.image.v1",
            description="Capture one image through the upstream snap (configure, acquire, download) and return the "
                        "path of a PGM file with its width and height",
            input={
                "width": Field("integer", unit="1",
                               description="Frame width in pixels; omit it to use the configured frame width",
                               limit=Limit.operator_required(
                                   "the clone states no numeric ROI range; the operator supplies it (class minimum 1)")),
                "height": Field("integer", unit="1",
                                description="Frame height in pixels; omit it to use the configured frame height",
                                limit=Limit.operator_required(
                                    "the clone states no numeric ROI range; the operator supplies it (class minimum 1)")),
                "exposure_ms": Field("number", unit="ms",
                                     description="Exposure for this capture in milliseconds; omit it to use the "
                                                 "configured exposure time",
                                     limit=Limit.operator_required(
                                         "the clone passes the exposure to SetExposureTime but states no numeric "
                                         "range; the operator supplies it (class minimum 0)")),
            })
    def snap(self, width=None, height=None, exposure_ms=None):
        if exposure_ms is not None:
            self.native.set_attribute("exposure_time", float(exposure_ms) / 1000.0)
        if width is not None:
            self.native.set_attribute("width", int(width))
        if height is not None:
            self.native.set_attribute("height", int(height))
        image = self.native.snap()
        path, actual_width, actual_height = _write_pgm(_first_frame(image))
        return {
            "image_ref": path,
            "width": actual_width,
            "height": actual_height,
            "media_type": "image/x-portable-graymap",
            "exposure_ms": self.exposure_time() * 1000.0,
        }

    # -- safety -----------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The upstream stop path: abort the acquisition (blacs_workers.py:105-107)."""
        self.native.abort_acquisition()

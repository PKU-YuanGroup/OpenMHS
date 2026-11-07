"""OpenMHS driver for gh.bernardokyotoku/pydcu: an IDS uEye camera through the clone's ctypes wrapper.

A direct Driver (decorated methods) over the upstream device class ``ueye:camera``, the low-level SDK handle
wrapper.  The clone is a Python 2 ctypes binding for the IDS uEye camera family: on POSIX it loads the vendor
library ``ueye_api`` at import time (ueye.py:23-29) and wraps the SDK calls in ``CALL`` (ueye.py:32-45).  ``pycam``
is the README's convenience object (README:12-15); it only holds a ``camera`` plus an ``image`` facade and forwards
to the same methods (ueye.py:118-132), so the driver binds the ``camera`` class the card also lists, which carries
the SDK surface directly.

* reads: the current AOI width and height, queried through ``SetImageSize`` with the IS query codes
  (ueye.py:344-362), and the current AOI x and y position, queried through ``SetImagePos`` (ueye.py:453-457);
* writes: the same four AOI fields.  No text file of the clone states a pixel range: the size range is queried from
  the installed sensor at run time (ueye.py:348-357) and the position range depends on the AOI, so all four writes
  are ``Limit.operator_required``: every write is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the
  range of its camera (``site-limits.example.json`` shows the overlay);
* action: ``cap.sensing.image.v1`` follows the clone's snapshot path -- ``CaptureVideo(wait=IS.WAIT)``,
  ``StopLiveVideo(wait=IS.WAIT)``, ``SaveImage(filename)`` (ueye.py:128-132) -- and saves one BMP frame to a system
  temporary file.  The receipt carries its path and the current AOI size, not the pixel array;
* the native stop is ``ExitCamera`` (ueye.py:509-511): the e-stop closes the camera and the safe state is the closed
  camera.

The clone's ``ueye.py`` is Python 2 source (a print statement at ueye.py:27 and ``unicode`` at ueye.py:40); it cannot
be imported by the Python 3 runtime, so no hardware factory is shipped and the only backend is the package fake.
The acceptance gate checks the fake backend only.  This package is model-authored and unreviewed; nothing in it ran
on a camera and no hardware run is claimed.

Every Fact cites a line of the clone at the pinned commit ff9557e701e348c4be9a01dbf7a84fd467f8c20d.
"""

import os
import tempfile

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

# IS.py query and wait codes used by the upstream methods: GET_IMAGE_SIZE_X/Y (IS.py:341-342),
# GET_IMAGE_POS_X/Y (IS.py:349-350) and WAIT (IS.py:237).  They are protocol constants, not device bounds.
GET_IMAGE_SIZE_X = 0x8000
GET_IMAGE_SIZE_Y = 0x8001
GET_IMAGE_POS_X = 0x8001
GET_IMAGE_POS_Y = 0x8002
WAIT = 0x0001

WIDTH_REASON = (
    "no text file of the clone states an AOI width range: SetImageSize only says the minimum, maximum and increment "
    "are queried from the camera with IS.GET_IMAGE_SIZE_X_MIN/MAX/INC (ueye.py:344-362), and the usable range "
    "depends on the installed sensor; the site supplies the range of its camera")

HEIGHT_REASON = (
    "no text file of the clone states an AOI height range: SetImageSize only says the minimum, maximum and "
    "increment are queried from the camera with IS.GET_IMAGE_SIZE_Y_MIN/MAX/INC (ueye.py:344-362), and the usable "
    "range depends on the installed sensor; the site supplies the range of its camera")

POS_X_REASON = (
    "no text file of the clone states an AOI x-position range: SetImagePos forwards two integers to the SDK "
    "(ueye.py:453-457) and the position depends on the current AOI and sensor; the site supplies the range")

POS_Y_REASON = (
    "no text file of the clone states an AOI y-position range: SetImagePos forwards two integers to the SDK "
    "(ueye.py:453-457) and the position depends on the current AOI and sensor; the site supplies the range")

EXPOSURE_REASON = (
    "no text file of the clone states an exposure range: Exposure only says 'Sets the exposure time (in ms)' "
    "(ueye.py:542-544) and the usable range depends on the installed camera; the site supplies the range")


class UEyeCamera(Driver):
    device_id = "ueye-camera"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R1"
    native = "ueye:camera"
    backends = {"fake": ".fake:FakeUEyeCamera"}
    vendor, model = "IDS Imaging Development Systems", "uEye camera through the pydcu ctypes wrapper"
    display_name = "IDS uEye camera (pydcu ueye.camera)"
    tags = ["camera", "ids", "ueye", "ctypes", "imaging", "aoi"]
    facts = [
        Fact("The README points the user to the IDS uEye driver package, to /usr/lib/libueye_api.so, and to "
             "`from uc480 import pycam`, `camera = pycam()`, `camera.snapshot('some_name.bmp')`",
             source="vendor_doc", ref="README:1-15"),
        Fact("On POSIX the module resolves the vendor library name ueye_api and loads it with ctypes at import time; "
             "when find_library returns None the module prints an error and LoadLibrary(None) fails",
             source="upstream_code", ref="ueye.py:23-29"),
        Fact("The module is Python 2 source: line 27 is a print statement and line 40 compares with unicode, so the "
             "Python 3 ast parser cannot read the file", source="upstream_code", ref="ueye.py:27-40"),
        Fact("class pycam creates a camera(camera_id) and an image wrapper and then allocates and activates image "
             "memory", source="upstream_code", ref="ueye.py:118-123"),
        Fact("pycam.snapshot captures a frame with IS.WAIT, stops live video with IS.WAIT and calls "
             "SaveImage(filename)", source="upstream_code", ref="ueye.py:128-132"),
        Fact("class camera wraps the SDK handle and initializes it with is_InitCamera", source="upstream_code",
             ref="ueye.py:140-145"),
        Fact("The camera constructor sets width 1024 and height 768 and allocates a NumPy image buffer; these are "
             "constructor defaults, not a sensor limit", source="upstream_code", ref="ueye.py:146-149"),
        Fact("SetImageSize reads the current AOI width or height when the x argument has the 0x8000 bit set and "
             "returns the queried value, otherwise it sets the size", source="upstream_code",
             ref="ueye.py:344-362"),
        Fact("SetImagePos reads the current AOI x or y position when x has the 0x8000 bit set and returns the "
             "queried value, otherwise it sets the position", source="upstream_code", ref="ueye.py:453-457"),
        Fact("CaptureVideo digitizes a frame into the image memory allocated by AllocImageMem and activated by "
             "SetImageMem; IS.WAIT waits until acquisition begins", source="upstream_code", ref="ueye.py:459-483"),
        Fact("StopLiveVideo stops live video; with IS.WAIT it waits until the image is completely acquired",
             source="upstream_code", ref="ueye.py:493-507"),
        Fact("SaveImage writes the active image memory to the named file through is_SaveImage",
             source="upstream_code", ref="ueye.py:437-441"),
        Fact("ExitCamera closes the camera handle through is_ExitCamera", source="upstream_code",
             ref="ueye.py:509-511"),
        Fact("The IS module defines GET_IMAGE_SIZE_X 0x8000 and GET_IMAGE_SIZE_Y 0x8001 for the size queries and "
             "GET_IMAGE_POS_X 0x8001 and GET_IMAGE_POS_Y 0x8002 for the position queries",
             source="upstream_code", ref="IS.py:341-350"),
        Fact("The IS module defines WAIT 0x0001 and DONT_WAIT 0x0000", source="upstream_code", ref="IS.py:237-238"),
        Fact("setup.py installs only the top-level modules ueye and IS and declares no licence",
             source="upstream_code", ref="setup.py:1-6"),
    ]
    safe_state = "camera closed through is_ExitCamera; no further frame is captured"

    # -- helpers ----------------------------------------------------------------------------------------------
    def _image_size(self):
        """The camera's current AOI (width, height) in pixels, read through the SDK query codes."""
        return (int(self.native.SetImageSize(x=GET_IMAGE_SIZE_X)),
                int(self.native.SetImageSize(x=GET_IMAGE_SIZE_Y)))

    def _image_position(self):
        """The camera's current AOI (x, y) top-left position in pixels, read through the SDK query codes."""
        return (int(self.native.SetImagePos(x=GET_IMAGE_POS_X)),
                int(self.native.SetImagePos(x=GET_IMAGE_POS_Y)))

    # -- reads ------------------------------------------------------------------------------------------------
    @read("width", type="integer", unit="1", description="Current AOI width of the camera in pixels")
    def width(self):
        return self._image_size()[0]

    @read("height", type="integer", unit="1", description="Current AOI height of the camera in pixels")
    def height(self):
        return self._image_size()[1]

    @read("image_x", type="integer", unit="1", description="Current AOI left column in sensor pixels")
    def image_x(self):
        return self._image_position()[0]

    @read("image_y", type="integer", unit="1", description="Current AOI top row in sensor pixels")
    def image_y(self):
        return self._image_position()[1]

    # -- writes -----------------------------------------------------------------------------------------------
    @write("width", type="integer", unit="1",
           description="AOI width in pixels; the height is kept at its current value",
           limit=Limit.operator_required(WIDTH_REASON))
    def set_width(self, value):
        height = self._image_size()[1]
        self.native.SetImageSize(x=int(value), y=height)
        return self._image_size()[0]

    @write("height", type="integer", unit="1",
           description="AOI height in pixels; the width is kept at its current value",
           limit=Limit.operator_required(HEIGHT_REASON))
    def set_height(self, value):
        width = self._image_size()[0]
        self.native.SetImageSize(x=width, y=int(value))
        return self._image_size()[1]

    @write("image_x", type="integer", unit="1",
           description="AOI left column in sensor pixels; the y position is kept at its current value",
           limit=Limit.operator_required(POS_X_REASON))
    def set_image_x(self, value):
        y = self._image_position()[1]
        self.native.SetImagePos(x=int(value), y=y)
        return self._image_position()[0]

    @write("image_y", type="integer", unit="1",
           description="AOI top row in sensor pixels; the x position is kept at its current value",
           limit=Limit.operator_required(POS_Y_REASON))
    def set_image_y(self, value):
        x = self._image_position()[0]
        self.native.SetImagePos(x=x, y=int(value))
        return self._image_position()[1]

    # -- action -----------------------------------------------------------------------------------------------
    @action(cap="cap.sensing.image.v1",
            description="Capture one frame through CaptureVideo(wait=IS.WAIT), StopLiveVideo(wait=IS.WAIT) and "
                        "SaveImage, and return the path of the BMP file and the current AOI size",
            input={
                "width": Field("integer", unit="1",
                               description="AOI width for this capture in pixels; omit it to keep the current width",
                               limit=Limit.operator_required(WIDTH_REASON)),
                "height": Field("integer", unit="1",
                                description="AOI height for this capture in pixels; omit it to keep the current "
                                            "height",
                                limit=Limit.operator_required(HEIGHT_REASON)),
                "exposure_ms": Field("number", unit="ms",
                                     description="Exposure for this capture in milliseconds; omit it to keep the "
                                                 "camera's configured exposure",
                                     limit=Limit.operator_required(EXPOSURE_REASON)),
            })
    def capture(self, width=None, height=None, exposure_ms=None):
        self.check_cancelled()
        if width is not None or height is not None:
            current_width, current_height = self._image_size()
            self.native.SetImageSize(x=current_width if width is None else int(width),
                                     y=current_height if height is None else int(height))
        if exposure_ms is not None:
            self.native.Exposure(float(exposure_ms))
        self.check_cancelled()
        width_now, height_now = self._image_size()
        handle, path = tempfile.mkstemp(prefix="ueye-", suffix=".bmp")
        os.close(handle)
        try:
            self.native.CaptureVideo(wait=WAIT)
            self.check_cancelled()
            self.native.StopLiveVideo(wait=WAIT)
            self.check_cancelled()
            self.native.SaveImage(path)
        except BaseException:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise
        if not os.path.isfile(path) or os.path.getsize(path) <= 0:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise DriverFailed("MHS.DEVICE.FAULTED", "SaveImage produced no image file")
        return {"image_ref": path, "width": width_now, "height": height_now, "media_type": "image/bmp"}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: close the camera handle through is_ExitCamera (ueye.py:509-511)."""
        self.native.ExitCamera()

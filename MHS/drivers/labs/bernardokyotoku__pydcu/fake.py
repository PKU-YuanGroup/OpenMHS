"""Fake backend of the uEye camera driver: an in-memory stand-in for the upstream ``ueye:camera`` class.

Gate G7: every public method of :class:`FakeUEyeCamera` exists on ``ueye.camera`` in the clone:
``SetImageSize`` (ueye.py:344-362), ``SetImagePos`` (ueye.py:453-457), ``CaptureVideo`` (ueye.py:459-483),
``StopLiveVideo`` (ueye.py:493-507), ``Exposure`` (ueye.py:542-552), ``SaveImage`` (ueye.py:437-441) and
``ExitCamera`` (ueye.py:509-511).  The query codes follow the upstream branch: an ``x`` argument with the 0x8000 bit
set is a query that returns the value (IS.py:341-350); otherwise the call sets the size or position.

Every number below is test data, not a fact about any uEye model, and every one is marked ``# placeholder``.  The
state changes only through the methods above, so reading it twice gives the same values.  ``SaveImage`` writes a
1 x 1 BMP placeholder file, not a frame from a camera; the receipt reports the fake's current AOI size instead.
Nothing here imports the upstream module (it is Python 2) or talks to a device.
"""

import os
import struct


def _placeholder_bmp():
    """A valid 1 x 1, 24-bit BMP with one black pixel; a placeholder, not an acquired frame."""
    width = height = 1                     # placeholder (test data, not the AOI of any camera)
    row = b"\x00\x00\x00\x00"              # one BGR pixel plus one pad byte (placeholder)
    file_header = struct.pack("<2sIHHI", b"BM", 14 + 40 + len(row), 0, 0, 54)
    info_header = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0, len(row), 0, 0, 0, 0)
    return file_header + info_header + row


class FakeUEyeCamera:
    """The upstream camera's SDK-facing surface, backed by in-memory test state."""

    def __init__(self, **_options):
        self._width = 1024                 # placeholder (test data, not the AOI of any camera)
        self._height = 768                 # placeholder (test data, not the AOI of any camera)
        self._sensor_width = 1280          # placeholder (test data, not the sensor of any camera)
        self._sensor_height = 1024         # placeholder (test data, not the sensor of any camera)
        self._x = 0                        # placeholder (test data, not the AOI of any camera)
        self._y = 0                        # placeholder (test data, not the AOI of any camera)
        self._exposure = 10.0              # placeholder (test data, not the exposure of any camera)
        self._capturing = False
        self._closed = False
        self._frames = 0

    def SetImageSize(self, x=0x8000, y=0):
        code = int(x)
        if code & 0x8000:
            if code == 0x8000:             # IS.GET_IMAGE_SIZE_X
                return self._width
            if code == 0x8001:             # IS.GET_IMAGE_SIZE_Y
                return self._height
            if code == 0x8006:             # IS.GET_IMAGE_SIZE_X_MAX
                return self._sensor_width
            if code == 0x8007:             # IS.GET_IMAGE_SIZE_Y_MAX
                return self._sensor_height
            return 0
        width, height = int(x), int(y)
        if width < 1 or height < 1:
            raise ValueError("the AOI width and height must be positive")
        self._width, self._height = width, height
        return 0

    def SetImagePos(self, x=0, y=0):
        code = int(x)
        if code & 0x8000:
            if code == 0x8001:             # IS.GET_IMAGE_POS_X
                return self._x
            if code == 0x8002:             # IS.GET_IMAGE_POS_Y
                return self._y
            return 0
        self._x, self._y = int(x), int(y)
        return 0

    def CaptureVideo(self, wait=0):
        if self._closed:
            raise RuntimeError("the camera is closed")
        self._capturing = True
        self._frames += 1
        return 0

    def StopLiveVideo(self, wait=0):
        self._capturing = False
        return 0

    def Exposure(self, time):
        if self._closed:
            raise RuntimeError("the camera is closed")
        self._exposure = float(time)

    def SaveImage(self, filename):
        if self._closed:
            raise RuntimeError("the camera is closed")
        if filename is None:
            raise ValueError("SaveImage needs a filename")
        name = os.fsdecode(filename) if isinstance(filename, bytes) else str(filename)
        with open(name, "wb") as stream:
            stream.write(_placeholder_bmp())
        return 0

    def ExitCamera(self):
        self._capturing = False
        self._closed = True
        return 0

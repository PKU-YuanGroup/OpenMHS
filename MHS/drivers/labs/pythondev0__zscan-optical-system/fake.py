"""Fake backend of the zscan camera driver: an in-memory stand-in for camera:ThorlabsCamera.

The upstream class (``camera.py:9``) initializes an IDS uEye camera through ``pyueye``, stores ``h_cam``, ``width``,
``height``, ``mem_ptr`` and ``mem_id``, captures frames with ``capture_image`` and frees the camera with ``release``.
This fake keeps exactly those public attributes and methods and never imports pyueye, numpy or the upstream package.
It never opens a camera.

Every number and pixel below is a placeholder for the tests, not a fact about the DCC1545M and not a bound:
``width`` and ``height`` repeat the upstream constructor's allocation size (``camera.py:28-29``), and
``capture_image`` returns a small 8 x 8 frame so the receipts stay small.  The real frame is 1280 x 1024 Mono8
(``README.md:18``, ``camera.py:43-46``).  The released flag is the existing ``mem_ptr`` attribute set to None, which
models ``release`` freeing the image memory (``camera.py:69-72``); it is not a new native member.
"""


class FakeThorlabsCamera:
    """Source-shaped fake of ``camera:ThorlabsCamera`` with only its constructor attributes and two methods."""

    def __init__(self, device_id=0):
        self.h_cam = int(device_id)          # placeholder; the upstream stores a ueye.HIDS handle
        self.width = 1280                    # placeholder; the upstream allocation width (camera.py:28)
        self.height = 1024                   # placeholder; the upstream allocation height (camera.py:29)
        self.mem_ptr = object()              # placeholder; the upstream starts with a ueye.c_mem_p object
        self.mem_id = 0                      # placeholder; the upstream starts with a ueye.INT object

    def capture_image(self):
        """Return a small deterministic Mono8 frame; the real frame comes from the uEye camera."""
        if self.mem_ptr is None and self.mem_id is None:
            raise RuntimeError("the fake camera memory is already released")   # placeholder failure
        return [[((row * 31) + (column * 17)) % 256 for column in range(8)] for row in range(8)]  # placeholder

    def release(self):
        """Model is_FreeImageMem and is_ExitCamera by clearing the stored image memory."""
        self.mem_ptr = None
        self.mem_id = None

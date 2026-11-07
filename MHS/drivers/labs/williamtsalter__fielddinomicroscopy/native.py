"""Hardware backend: opens a Dino-Lite microscope through the upstream ctypes wrapper.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  This package is
model-authored and unreviewed and is R1; the loader refuses the hardware backend of an unreviewed model-written
package only at R2 and R3, so at R1 it does not refuse this one.  That is not a review claim: nothing in this package
or its gate ran the hardware path.

Options of the backend:

* ``dll_path`` (required): the path of the vendor ``DNX64.dll``.  The upstream app hard-codes
  ``C:\\Program Files\\DNX64\\DNX64.dll`` (app.py:61) and the README says the Dino-Lite SDK installs it there
  (README.MD:115-120).  The SDK is a separate, licence-gated vendor download; this repository does not install it and
  the driver package never imports it at gate time.
* ``device_index``: the video device index passed to ``SetVideoDeviceIndex`` before ``Init`` (default 0, the app's
  default at app.py:63).  The README tells the user to edit that index per machine (README.MD:203-204); it is a
  deployment choice, not a device bound.

The upstream module is the top-level ``dnx64.py`` of the clone; put the clone root on ``PYTHONPATH`` (or make the
module importable another way) before the hardware backend can be opened.  The wrapper imports OpenCV at module
import (dnx64.py:3), so the requirements file has to be installed as well.  The hardware path is Windows only
(README.MD:39, README.MD:115-120).
"""


def connect(dll_path, device_index=0):
    """Open the vendor control object, select the device and initialize it."""
    from dnx64 import DNX64

    device = DNX64(dll_path)
    device.SetVideoDeviceIndex(int(device_index))
    if not device.Init():
        raise RuntimeError(
            "DNX64 Init() failed: check that the Dino-Lite microscope is connected and that dll_path names the "
            "installed DNX64.dll")
    return device

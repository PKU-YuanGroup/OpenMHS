"""Hardware backend of the Nuvu camera driver: opens NuvuCamUtils through the upstream package.

This module is imported only when the driver is loaded with ``backend="hardware"``.  The acceptance gate never imports
it, and nothing here ran: the package is model-authored and unreviewed, and the loader refuses the hardware backend of
an unreviewed model-written R2 package until a human sets ``reviewed_by`` in driver.lock.json.

The upstream module is ``userlib/user_devices/NuvuCamera/Nuvu_sdk/Nuvu_cam_utils.py`` of the clone and imports
``user_devices...`` absolutely, so the clone's ``userlib`` directory has to be the import root a labscript deployment
already uses.  ``userlib`` selects that directory explicitly; when it is omitted the import uses the process's
existing ``sys.path``.  Importing the SDK loads the vendor binary named by NC_api.py:9-13 (``libnuvu.so`` on Linux,
``nc_driver_x64.dll`` on Windows); the vendor runtime is not part of the clone and is not installed by this package.
``logger`` is passed to the NuvuCamUtils constructor (Nuvu_cam_utils.py:38-52).

NC_api.py:6-14 selects ELF and WindowsPE libraries (including a separate 32-bit Windows DLL); it defines no Mach-O
branch. The hardware path is therefore not established on macOS by the card's ``platform: any``. Importing
Nuvu_cam_utils also requires NumPy and matplotlib. SDK failures normally close the camera handle before raising
(nc_camera.py:95-113), and get_image has an additional close-on-error decorator
(Nuvu_cam_utils.py:76-84,201-205). After such an error, recovery requires a new native session; releasing the MHS
latch does not reopen the camera. No hardware import, SDK call or camera check was performed during model review.
"""


def connect(userlib=None, logger=None, **options):
    """Open the camera: NuvuCamUtils(logger) calls openCam(nbBuff=4) in its constructor."""
    if options:
        raise TypeError(f"unknown Nuvu camera backend option(s): {sorted(options)}")
    if userlib is not None:
        import sys

        root = str(userlib)
        if root not in sys.path:
            sys.path.insert(0, root)
    if logger is None:
        import logging

        logger = logging.getLogger("mhs.nuvu")
    from user_devices.NuvuCamera.Nuvu_sdk.Nuvu_cam_utils import NuvuCamUtils

    return NuvuCamUtils(logger)

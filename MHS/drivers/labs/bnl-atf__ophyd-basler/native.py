"""Hardware backend of the Basler camera: the upstream ophyd Device over pypylon.

The gate never imports this module.  ``connect`` runs only when an operator loads the hardware backend
(``mhs.adapter.load_driver(..., backend="hardware", allow_hardware=True, state_dir=...)``); it is then the only code
that imports ``ophyd_basler``, and through it pypylon, ophyd, h5py, event-model and the rest of the upstream runtime.
The upstream package is not installed in this workspace and was never imported or run here.

``connect`` forwards the operator's options to the upstream constructor, so its own defaults (``cam_num=0``,
``pixel_format="Mono8"``, ``trigger_mode="Off"``, ``root_dir="/tmp/basler"``) remain the upstream's defaults, not
limits or facts of a deployed camera.  The ``stage`` path writes an HDF5 file under ``root_dir`` and applies the
current ``exposure_time`` only when it lies within the camera's own ``ExposureTimeAbs.Min`` and ``Max`` (outside them it
corrects the Signal and writes nothing in that call).  ``stage`` opens the HDF5 file in mode ``"x"`` under a dated
``root_dir/YYYY/MM/DD`` directory that must already exist (the upstream test fixture creates it with
``make_dir_tree``); the driver never calls ``trigger``, so each capture leaves one file with a NaN-filled first frame.
The camera must be visible to the Basler pylon transport layer; ``pypylon`` and the vendor runtime are deployment
requirements.  Nothing here was run against a camera.
"""


def connect(**options):
    """Build the upstream ``BaslerCamera``; keyword options are the upstream constructor's."""
    name = options.pop("name", "basler_camera")
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError("name must be a Python identifier (it names the ophyd Device and its Signals)")
    from ophyd_basler.basler_camera import BaslerCamera

    return BaslerCamera(name=name, **options)

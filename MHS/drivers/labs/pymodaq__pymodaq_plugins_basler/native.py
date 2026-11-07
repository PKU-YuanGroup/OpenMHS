"""Hardware backend: opens one Basler camera through the upstream BaslerCamera class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed.  It is R1, so the loader's refusal of an unreviewed model-written hardware backend (which applies
at R2 and R3) does not apply here: nothing in the SDK blocks this module at R1, and the module was never run.  The
acceptance gate runs the fake backend and never imports this module or the upstream package.

Options of the backend: ``serial`` selects the device whose pylon serial number equals it; ``model`` selects the
first device whose model name equals it; ``index`` (default 0) selects by position in the pylon enumeration.  The
native class opens the device in its constructor and reads the per-model attribute configuration
(src/pymodaq_plugins_basler/hardware/basler.py:53-102); a missing configuration file makes the upstream constructor
ask whether to create one.
"""


def connect(serial=None, model=None, index=0, callback=None, **_options):
    from pymodaq_plugins_basler.hardware.basler import BaslerCamera

    devices = BaslerCamera.list_cameras()
    if not devices:
        raise RuntimeError("pypylon enumerated no Basler camera")
    if serial is not None:
        matches = [device for device in devices if device.GetSerialNumber() == serial]
        if not matches:
            raise RuntimeError(f"no enumerated Basler camera has serial number {serial!r}")
        info = matches[0]
    elif model is not None:
        matches = [device for device in devices if device.GetModelName() == model]
        if not matches:
            raise RuntimeError(f"no enumerated Basler camera has model name {model!r}")
        info = matches[0]
    else:
        info = devices[int(index)]
    return BaslerCamera(info=info, callback=callback)

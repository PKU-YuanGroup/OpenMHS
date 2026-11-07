"""Hardware backend: opens a PI GCS2 controller through the upstream PIWrapper.

Used only with backend="hardware" and a human operator decision; the acceptance gate runs the fake backend and never
imports this module or the upstream package.  This package is model-authored and unreviewed, so its hardware backend
must not be used before ``reviewed_by`` is signed in driver.lock.json: the loader refuses the hardware backend of an
unreviewed model-written package at R2 and R3.  This package is R1, so that loader rule alone does not stop hardware
use; the operator must review it first.

The wrapper connects over USB, TCP/IP or RS232 (pi_wrapper.py:233-259); an RS232 line is opened at 19200 baud
(pi_wrapper.py:242-244).  ``device_id`` is one of the device names the upstream ``get_devices_and_dlls`` enumerates
(utils.py:25-70), so it must be the name the operator's configuration reports, not a made-up default (the upstream
constructor default is not a property of a unit).  ``daisy_id`` is needed only for a daisy chain.
"""


def connect(device_id, connection_type="USB", is_daisy=False, is_daisy_master=False, daisy_id=0, **_options):
    from pymodaq_plugins_physik_instrumente.hardware.pi_wrapper import ConnectionEnum, PIWrapper

    wrapper = PIWrapper()
    wrapper.is_daisy = bool(is_daisy)
    wrapper.is_daisy_master = bool(is_daisy_master)
    wrapper.daisy_id = int(daisy_id)
    wrapper.connection_type = ConnectionEnum[str(connection_type)]
    wrapper.device_id = str(device_id)
    if wrapper.device_id is None:
        raise ValueError(f"device_id {device_id!r} is not one of the device names the upstream configuration "
                         "enumerates")
    wrapper.connect_device()
    return wrapper

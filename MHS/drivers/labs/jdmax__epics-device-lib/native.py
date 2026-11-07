"""Hardware backend: opens the Lake Shore 336 connection through the upstream protocol class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json.  The acceptance gate runs the fake backend and never imports this module or the clone.

The clone is a soft-IOC device library designed to be mounted as the package ``devices`` (README.md:5,
README.md:102-119), so the upstream class is ``devices.instruments.ls336.DeviceConnection``.  Its base
``TelnetConnection`` opens a TCP socket to
host:port in the constructor (telnet_base.py:27-36) and every command goes through ``self.tn``
(instruments/ls336.py:99-272).  The upstream soft-IOC settings pass ``ip``, ``port`` and ``timeout``
(instruments/ls336.py:37-42); the driver's own deployment options (``channel``, ``setpoint_unit``,
``reenable_mode``) are read by driver.py and are not connection arguments.
"""


def connect(host, port, timeout=2.0, **_options):
    """Open the upstream DeviceConnection; raise if the socket could not be created."""
    from devices.instruments.ls336 import DeviceConnection

    device = DeviceConnection(str(host), int(port), float(timeout))
    if getattr(device, "tn", None) is None:
        raise OSError(f"cannot open the Lake Shore 336 connection to {host}:{port}")
    return device

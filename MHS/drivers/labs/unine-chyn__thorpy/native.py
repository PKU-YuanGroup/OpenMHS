"""Hardware backend of the Thorpy driver: open the upstream APT serial port.

This module is used only with ``backend="hardware"`` and ``allow_hardware=True``, an operator decision.  The
acceptance gate never imports it and never opens a device.  ``Port.create`` selects the single-controller port for
every serial number except the card-slot families the clone does not implement (``thorpy/comm/port.py:181-193``).
"""


def connect(**options):
    from thorpy.comm.port import Port

    port = options.pop("port", None)
    serial_number = options.pop("serial_number", None)
    if options:
        raise TypeError(f"unknown hardware backend option(s): {sorted(options)}")
    if not port:
        raise ValueError("the hardware backend needs the serial port option 'port'")
    if serial_number is None:
        raise ValueError("the hardware backend needs the controller serial number option 'serial_number'")
    return Port.create(port, str(serial_number))

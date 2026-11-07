"""Hardware backend for the Aero Hand Open SDK class.

Used only with ``backend="hardware"`` and ``allow_hardware=True``; this package is
model-authored and unreviewed at R2, so the loader refuses that backend until a
human sets ``reviewed_by`` in ``driver.lock.json``.  The acceptance gate runs the
fake backend and never imports this module or the upstream package.

The upstream constructor opens a serial port with a 0.01 s read/write timeout
(``sdk/src/aero_open_sdk/aero_hand.py:53-64``).  ``port`` is the serial device
path; when it is omitted the upstream tries to auto-detect the ESP32 USB JTAG
port under ``/dev/serial/by-id``.  ``baudrate`` is forwarded as the constructor
argument; the upstream default is 921600, but the deployment must select the
value of its configured unit.
"""


def connect(port=None, baudrate=921600, **options):
    from aero_open_sdk.aero_hand import AeroHand

    if options:
        raise TypeError(f"unsupported Aero Hand backend options: {sorted(options)}")
    return AeroHand(port=port, baudrate=baudrate)

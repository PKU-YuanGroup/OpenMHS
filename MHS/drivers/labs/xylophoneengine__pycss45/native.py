"""Hardware backend: opens a Gigahertz-Optik CSS45 through the upstream ``pycss45.CSS45`` class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is
model-authored and unreviewed; it is R0, so the loader does not require a human ``reviewed_by`` signature
before a hardware backend starts (that rule applies to model-authored R2 and R3 packages only).  Nothing in
this package ran on a device, and the acceptance gate runs the fake backend without importing this module or
the pycss45 package.

Options of the backend are the keyword arguments of the upstream constructor (pycss45.py:448-461):
``transport`` ("hid" default or "serial"), ``path`` (a HID path), ``serial_port`` (required for the serial
transport), ``baudrate``, ``vid``, ``pid``, ``startsign``, ``endsign``, ``checksum`` and ``echo``.  The
constructor opens the transport and verifies the device identity before it returns (pycss45.py:577-604).
"""


def connect(**options):
    from pycss45 import CSS45

    return CSS45(**options)

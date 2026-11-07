"""Hardware backend: opens a Thorlabs Kinesis motor controller through pylablib.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
no human has reviewed it.  The loader refuses the hardware backend of such a package only at R2 and above; this one is
R1, so nothing stops an operator from enabling it: run it first with a person at the device
(MHS/handoff/REVIEW.md, section 1).  The acceptance
gate runs the fake backend and never imports this module or pylablib.

Options of the backend: ``conn`` (required) is the connection parameter of the upstream class, usually the 8-digit
device serial number, which pylablib's comm_backend opens over its FTDI backend (kinesis.py:1175-1176, kinesis.py:1181).
``scale``, ``default_channel`` and ``is_rack_system`` are the other constructor options of KinesisMotor
(kinesis.py:1195); the driver itself asks for every position and velocity with ``scale=False``, so ``scale`` only
decides how pylablib converts the values that this driver never asks for.
"""


def connect(conn, scale="step", default_channel=1, is_rack_system=False):
    from pylablib.devices import Thorlabs

    return Thorlabs.KinesisMotor(conn, scale=scale, default_channel=default_channel,
                                 is_rack_system=is_rack_system)

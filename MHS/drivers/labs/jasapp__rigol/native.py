"""Hardware backend: opens a RIGOL DP832A through the upstream class in the clone.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed and it is R1: the loader refuses the hardware backend of an unreviewed model-written package only at
R2 and R3, so nothing mechanical prevents a hardware run here and a human must review the package first.  The
acceptance gate runs the fake backend and never imports this module or the upstream rigol module.

The backend option is ``device``: the USB TMC device file the upstream RigolDP832A opens
(rigol.py:13, 30-32, 41-59).  It defaults to the upstream DEFAULT_DEVICE, /dev/usbtmc2.  The upstream module has no
dependencies beyond the Python standard library (os and time, rigol.py:7-8), but the clone root must be importable
(the operator puts it on PYTHONPATH); the gate never installs or imports it.
"""


def connect(device=None, **options):
    from rigol import DEFAULT_DEVICE, RigolDP832A

    return RigolDP832A(device or DEFAULT_DEVICE)

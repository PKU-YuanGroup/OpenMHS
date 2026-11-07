"""Hardware backend: opens a Hantek 6022BE through the upstream pyhantek6022BE:Hantek class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The upstream class opens the
USB device and loads its firmware in its constructor (pyhantek6022BE.py:10-108); it needs pyusb and numpy
(pyhantek6022BE.py:1-4, README.md:1) and, on Linux, the udev rule 60-hantek-6022BE.rules of the clone
(README.md:3).  The upstream module is imported here only, on the operator-enabled hardware backend; the gate and
the fake backend never import it.

This package is model-authored and unreviewed (driver.lock.json reviewed_by is null).  It is R1, so the loader's
R2/R3 refusal of an unreviewed hardware backend does not apply: an operator must still enable the hardware backend
explicitly and no hardware run is claimed.
"""


def connect():
    from pyhantek6022BE import Hantek

    return Hantek()

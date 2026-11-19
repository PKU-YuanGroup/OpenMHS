"""Hardware backend: builds the upstream CompactERAS ophyd Device for an EPICS prefix.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is
model-authored and unreviewed and is R0, so the loader does not refuse its hardware backend at R2 or
R3; that is not a review.  A human must review the package before anyone opens a real Soft IOC, and no
hardware run or upstream import is claimed here: the acceptance gate runs the fake backend and never
imports this module or the sophys-common package.

The upstream class is an ophyd Device; ``CompactERAS(prefix, name=...)`` creates its Components from
the EPICS prefix (src/sophys/common/devices/compacteras.py:49-69).  The deployment supplies the prefix
of its Soft IOC and a name for the ophyd Device; any further keyword argument is passed to the
upstream constructor unchanged.
"""


def connect(prefix, name="compacteras", **options):
    from sophys.common.devices.compacteras import CompactERAS

    return CompactERAS(prefix, name=name, **options)

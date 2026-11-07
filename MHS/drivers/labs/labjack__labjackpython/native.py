"""Hardware backend: opens a LabJack U3 through the upstream LabJackPython class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, but it is R1: the loader refuses the hardware backend of an unreviewed model-written package only
at R2 and R3, so this note does not claim such a refusal for R1.  A human must review the package before hardware
use; the acceptance gate runs the fake backend and never imports this module or the u3 package.

The upstream U3 constructor opens the first U3 when ``autoOpen`` is true (the default) and forwards its keyword
arguments to ``U3.open`` (src/u3.py:73-106), which accepts ``firstFound``, ``serial``, ``localId``, ``devNumber``,
``handleOnly`` and ``LJSocket``.  The factory passes every backend option through unchanged; ``serial`` selects a
device by serial number and ``LJSocket`` selects an LJSocket host.  The device object returned is the native U3 the
driver calls.
"""


def connect(**options):
    from u3 import U3

    return U3(**options)

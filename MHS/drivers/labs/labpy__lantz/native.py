"""Hardware backend: opens a LabJack U12 through the Lantz U12 wrapper.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The package is model-authored and
unreviewed; driver.lock.json has ``reviewed_by`` null.  The loader's reviewed_by refusal applies only to a
model-written package at R2 or R3, so this R1 package does not claim that protection: a human must review this code
before the hardware backend is used.  The acceptance gate runs the fake backend and never imports this module or the
upstream Lantz package.

Options go to the upstream constructor ``U12(id=-1, serialNumber=None, debug=False)`` (u12.py:402): ``id`` selects a
local ID, ``serialNumber`` selects a serial number, and ``debug`` enables the wrapper's debug prints.  The upstream
module loads the LabJack driver library when it is imported (u12.py:351-386), so the import is inside ``connect``.
"""


def connect(**options):
    from lantz.drivers.labjack._internal.u12 import U12

    return U12(**options)

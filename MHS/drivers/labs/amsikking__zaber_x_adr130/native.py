"""Hardware backend: opens a Zaber X-ADR130 through the upstream zaber_X_ADR130:Controller.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored,
unreviewed and R1: the loader refuses an unreviewed model-written hardware backend only at R2 and R3, so this module
does not claim that protection; an operator must review the package and the site's stop arrangement before hardware
use.  The acceptance gate runs the fake backend and never imports this module or the upstream module.

Options of the backend: ``which_port`` (required) is the serial port of the stage (the upstream example uses COM15,
line 291); the other options are the matching keywords of the upstream constructor: ``name``, ``verbose`` and
``very_verbose`` (lines 8-15).  The upstream module is a single file at the root of the clone, so it must be
importable as ``zaber_X_ADR130`` (the README says to download and run that file, line 6).  The upstream opens the
port at 115200 baud with a 1 s timeout (lines 31-32) and checks the device id itself (lines 37-56).
"""


def connect(which_port, name="X-ADR130", verbose=False, very_verbose=False):
    from zaber_X_ADR130 import Controller

    return Controller(which_port=which_port, name=name, verbose=verbose, very_verbose=very_verbose)

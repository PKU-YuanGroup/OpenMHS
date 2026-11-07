"""Hardware backend: opens the Benning MM12 through the upstream serial wrapper.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed; it is R0, so the loader's ``reviewed_by`` refusal for unreviewed model-written R2/R3 packages does
not apply here.  The acceptance gate runs the fake backend and never imports this module or the clone.  No hardware
was attached while this package was written, and no hardware run is claimed.

The upstream clone is a script bundle, not an installable package: ``Benning_MM12_class.py`` sits at the clone root
and imports pyserial (Benning_MM12_class.py:9).  Make the module importable either by passing ``clone_root`` (the
clone directory) or by putting the clone root on PYTHONPATH before using this backend.  The constructor opens the
port itself with 9600 baud, 8 data bits, no parity, one stop bit and a 2 s timeout (Benning_MM12_class.py:193); the
class catches a connection error and stores ``status`` instead of raising (lines 188-201), so this factory checks
that status and raises when the port did not open.  Other keyword options are accepted for the loader but are not
used: the upstream constructor has no option for them.
"""


def connect(port, clone_root=None, **_options):
    """Open the upstream serial wrapper and return it once it reports a connection."""
    import sys

    if clone_root not in (None, "") and str(clone_root) not in sys.path:
        sys.path.insert(0, str(clone_root))
    from Benning_MM12_class import Benning_MM12_Serial

    device = Benning_MM12_Serial(port)
    if getattr(device, "status", None) != "Connected":
        raise RuntimeError(f"the Benning MM12 serial port did not open: {getattr(device, 'status', None)!r}")
    return device

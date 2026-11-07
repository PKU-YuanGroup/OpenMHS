"""Hardware backend: opens the HelixCycler serial controller ``tc_send_code:HardwareController``.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance
gate runs the fake backend and never imports this module or the upstream files, and no hardware was ever attached.

Options of the backend: ``port`` (required) is the serial port name the upstream ``HardwareController.connect``
accepts (for example ``/dev/ttyACM0`` or ``COM4``); the upstream opens it at 115200 baud with 2 s read and write
timeouts (tc_send_code.py:44).  ``clone_root`` is the root of the helixcycler checkout that contains tc_send_code.py;
by default the repository clone named by the task card is used.  The clone is not an installed package, so its
directory is put on sys.path only while this operator-invoked factory runs.
"""

import sys
from pathlib import Path


def connect(port, *, clone_root=None):
    """Open ``port`` with the upstream HardwareController and return it connected."""
    root = Path(clone_root) if clone_root is not None else (
        Path(__file__).resolve().parents[4] / "labs" / "helixworks-technologies" / "helixcycler")
    if not (root / "tc_send_code.py").is_file():
        raise RuntimeError(f"tc_send_code.py is not in {root}; pass clone_root=<the helixcycler checkout>")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from tc_send_code import HardwareController

    controller = HardwareController()
    if not controller.connect(port):
        raise RuntimeError(f"HardwareController.connect({port!r}) returned False: the serial port did not open")
    return controller

"""Hardware backend: opens an IKA RET Control Visc through its upstream serial class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance
gate runs the fake backend and never imports this module or the upstream package, and no hardware was ever attached.

The upstream class lives at ``<clone>/platform_server/modules/serial_labware/IKA_RET_Stirrer/
IKA_RET_Control_Visc.py``.  Its ``SerialDevice`` base is imported as ``SerialDevice.serial_labware``, so the
``platform_server/modules/serial_labware`` directory must be importable; the upstream files do the same kind of
``sys.path`` insertion for their own sibling imports (IKA_RET_Control_Visc.py:31-35).  Pass ``clone_root`` or put
that directory on PYTHONPATH.  The class only constructs a serial connection on Windows: ``SerialDevice.__init__``
raises OSError on other platforms (SerialDevice/serial_labware.py:104-108).  The serial settings are the upstream
defaults: 9600 baud, 7 data bits, even parity and RTS/CTS (IKA_RET_Control_Visc.py:60-64).
"""

import sys
from pathlib import Path


def connect(port, *, clone_root=None, **options):
    """Open the hotplate stirrer on ``port``; ``clone_root`` is the root of the chemputersoftware clone."""
    if clone_root is not None:
        modules = Path(clone_root) / "platform_server" / "modules" / "serial_labware"
        if str(modules) not in sys.path:
            sys.path.insert(0, str(modules))
    from IKA_RET_Stirrer.IKA_RET_Control_Visc import IKARETControlVisc

    return IKARETControlVisc(port=port, connect_on_instantiation=True, **options)

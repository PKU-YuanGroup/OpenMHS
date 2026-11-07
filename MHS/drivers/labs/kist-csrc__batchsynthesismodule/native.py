"""Hardware backend: opens the upstream IKA RET control-visc serial port.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance
gate runs the fake backend and never imports this module or the upstream package.

Options of the backend: ``port`` (required) is the serial port name the upstream ``SerialDevice`` accepts, and
``device_name`` names the unit in the upstream debug log.  The upstream class opens the connection on
instantiation (``Stirrer/IKA_RET_Control_Visc.py:115-116``) with the fixed serial settings at ``:68-72``.

Platform note: the upstream ``SerialDevice`` raises OSError on an operating system other than Windows
(``Stirrer/serial_labware/serial_labware.py:104-108``), so this factory can only open a port on Windows.  That is an
upstream restriction, not a tested hardware path.
"""


def connect(port, device_name="IKA_RET", **options):
    import sys
    from pathlib import Path

    clone = Path(__file__).resolve().parents[4] / "labs" / "kist-csrc" / "batchsynthesismodule"
    for entry in (str(clone), str(clone / "Stirrer" / "serial_labware")):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    from Stirrer.IKA_RET_Control_Visc import IKARETControlVisc

    return IKARETControlVisc(port=port, device_name=device_name, connect_on_instantiation=True, **options)

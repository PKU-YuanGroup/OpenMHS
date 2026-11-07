"""Hardware backend: opens an Owon/Abestop DS1102 through the upstream pyusb class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed; it is R0, and the loader's reviewed_by refusal applies only at R2 and R3, so nothing here claims that
protection.  The acceptance gate runs the fake backend and never imports this module or the upstream package; no
hardware was attached and no hardware run is claimed.

The clone is a set of top-level modules (``ds1102_mcp`` imports ``ds1102_logic``), so deploying the hardware backend
needs the clone root on ``sys.path`` and the dependencies of its ``requirements.txt`` installed.  ``ScopeController``
finds the scope by VID 0x5345 / PID 0x1234, claims USB interface 0 and sends commands with the upstream 4-byte
little-endian length header to endpoint 0x01 (ds1102_mcp.py:29-30, 48-64, 82-92).
"""


def connect(**_options):
    from ds1102_mcp import ScopeController

    device = ScopeController()
    if device.get_device() is None:
        raise RuntimeError("DS1102 not found on USB (VID 0x5345, PID 0x1234); check the PC USB mode")
    return device

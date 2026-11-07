"""Hardware backend factory of the Tecan Genesis driver (never imported by the gate).

``tecan_funcs`` opens ``/dev/ttyUSB0`` at import (``tecan_funcs.py:10``) with the pyserial-2 keyword names
``writeTimeout`` and ``interCharTimeout``.  The factory installs a temporary ``serial.Serial`` shim that drops those
two names and applies the requested port and baud rate, imports the upstream module once, then restores pyserial.
The returned ``Cmd_delayed`` uses the module global ``ser`` that the import created.  No hardware backend of this
model-authored package has been reviewed or run.
"""


def connect(**options):
    """Open the serial link and return ``tecan_funcs.Cmd_delayed`` (the upstream transport is the module global)."""
    import serial

    port = options.pop("port", "/dev/ttyUSB0")
    baudrate = int(options.pop("baudrate", 9600))
    timeout = float(options.pop("timeout", 1))
    if options:
        raise TypeError(f"unsupported hardware options: {sorted(options)}")
    original = serial.Serial

    def _serial(*args, **kwargs):
        kwargs.pop("writeTimeout", None)
        kwargs.pop("interCharTimeout", None)
        kwargs.setdefault("port", port)
        kwargs.setdefault("baudrate", baudrate)
        kwargs.setdefault("timeout", timeout)
        return original(*args, **kwargs)

    serial.Serial = _serial
    try:
        import tecan_funcs
    finally:
        serial.Serial = original
    return tecan_funcs.Cmd_delayed()

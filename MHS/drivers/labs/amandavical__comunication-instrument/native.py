"""Hardware backend: open the serial port and wrap it in the upstream Client.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The upstream ``Client`` takes an
open ``serial.Serial`` (modules/comunication_client.py:21-28), and the clone's collection modules open it as
``serial.Serial("COM1", 9600, timeout=2)`` (data_collection/temperature_collection.py:20-21).  This factory uses the
same two values as defaults, but an operator can pass a different port, baudrate or timeout because the upstream
does not state that every device is configured that way.

This package is model-authored and unreviewed, and it is R1: the loader refuses the hardware backend of an
unreviewed model-written package only at R2 and R3, so an operator can select it here.  The acceptance gate runs the
fake backend and never imports this module, the upstream package or pyserial.  Nothing here ran on hardware.
"""


def connect(port, *, baudrate=9600, timeout_s=2.0, **options):
    """Open ``port`` and return the upstream ``Client`` around the serial port."""
    import serial
    from modules.comunication_client import Client

    ser = serial.Serial(port=port, baudrate=int(baudrate), timeout=float(timeout_s), **options)
    return Client(ser)

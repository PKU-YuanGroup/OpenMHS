"""Hardware backend: opens one axis of a Zaber device through the upstream ASCII serial classes.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed; the acceptance gate runs the fake backend and never imports this module or the upstream package.
The hardware path was not run.

Options of the backend: ``port`` (required) is the serial port name or URL passed to ``AsciiSerial``
(``zaber/serial/ascii.py:824``); ``address`` (required) is the device address, which the upstream constructor
requires to be between 1 and 99 (``ascii.py:407-413``); ``axis`` (required) is the axis number, which the upstream
constructor requires to be between 1 and 9 (``ascii.py:29-35``).  The remaining keyword options go to
``AsciiSerial`` (for example ``baud``, ``timeout`` or ``inter_char_timeout``; see ``ascii.py:824-858``).  The
upstream class does not define a close method on the axis, so the caller owns the serial port's lifetime.
"""


def connect(port, address, axis, **options):
    from zaber.serial import AsciiDevice, AsciiSerial

    serial_port = AsciiSerial(port, **options)
    return AsciiDevice(serial_port, address).axis(axis)

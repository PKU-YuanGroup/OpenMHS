"""Hardware backend: opens a Thorlabs Elliptec shutter through the upstream serial controller.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed, so the loader refuses its hardware backend (R2) until driver.lock.json carries ``reviewed_by``.  The
acceptance gate runs the fake backend and never imports this module or the elliptec package.

An Elliptec device is a Motor served by a Controller over a serial port (src/elliptec/controller.py:13-46); the
Shutter object sends its commands through that controller (src/elliptec/shutter.py:13-15).  ``port`` is required
(the serial device, for example "COM3" or "/dev/ttyUSB0"); ``address`` is the 0-F bus address the device was given
(README.md:99-137 tells how several devices share one bus); ``inverted`` swaps open and closed
(src/elliptec/shutter.py:50-60).  The other options go to Controller: baudrate (default 9600), bytesize (8), parity
(serial.PARITY_NONE), stopbits (serial.STOPBITS_ONE), timeout (2 s) and write_timeout (0.5 s)
(src/elliptec/controller.py:17-25).
"""


def connect(port, address="0", inverted=False, **options):
    """Open the device on ``port`` and return the upstream Shutter object."""
    from elliptec import Controller, Shutter

    controller = Controller(port, **options)
    return Shutter(controller, address=address, inverted=inverted)

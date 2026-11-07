"""Hardware backend: opens a Cobolt laser on its serial line through the upstream class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2 (a model review raised it from the card's R1: a laser above class 1): the loader refuses its
hardware backend until a human signs ``reviewed_by`` in driver.lock.json, and nothing here ran.  The acceptance gate runs the fake backend and never imports this module or the microscope package.

Options of the backend: ``com`` (required) is the serial port of the laser controller; ``baud`` (default 115200)
and ``timeout`` (default 0.1, in seconds) are the serial options of the upstream constructor
(microscope/lights/cobolt.py:46-55).  The clone builds the line as 8N1 without parity.  The upstream
``initialize`` is called by the constructor, so a connected device is left with autostart forced on (@cob1).
"""


def connect(com, baud=115200, timeout=0.1):
    from microscope.lights.cobolt import CoboltLaser

    return CoboltLaser(com=com, baud=baud, timeout=timeout)

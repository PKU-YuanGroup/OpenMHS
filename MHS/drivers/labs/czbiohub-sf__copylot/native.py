"""Hardware backend: opens a Vortran Stradus laser through the upstream serial wrapper.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The acceptance gate runs the fake
backend and never imports this module or the copylot package.  The wrapper constructor opens the COM port and
identifies the head with ``?LI`` (vortran.py:50, 116-151, 240-251); the ``serial`` package it needs is installed with
the upstream package.

This package is model-authored and unreviewed.  Its risk class is R2 (a model review raised it from the card's R1:
a laser above class 1), so the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json.

Options of the backend: ``port`` (the COM port, required), ``baudrate`` (the wrapper default is 19200,
vortran.py:50) and ``serial_number`` (when given, the wrapper only accepts a head with that serial number,
vortran.py:145-147).
"""


def connect(port=None, baudrate=19200, serial_number=None):
    from copylot.hardware.lasers.vortran.vortran import VortranLaser

    return VortranLaser(serial_number=serial_number, port=port, baudrate=int(baudrate))

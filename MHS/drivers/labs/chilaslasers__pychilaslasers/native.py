"""Hardware backend: opens a Chilas Atlas or Comet laser through pychilaslasers.laser:Laser.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance
gate runs the fake backend and never imports this module or the upstream package.

Options of the backend: ``com_port`` (required) is the serial port of the laser, for example ``"COM7"`` or
``"/dev/ttyUSB0"`` (laser.py:104-107); ``calibration_file`` (optional) is the path to the calibration file supplied
with the unit (laser.py:108-109).  The upstream constructor opens the serial connection, negotiates a supported
baudrate (comm.py:63-100) and turns the laser on while it reads the component limits (laser.py:99-102), so opening
this backend changes the device state.  Nothing here was run against hardware.
"""


def connect(com_port, calibration_file=None):
    from pychilaslasers import Laser

    return Laser(com_port=com_port, calibration_file=calibration_file)

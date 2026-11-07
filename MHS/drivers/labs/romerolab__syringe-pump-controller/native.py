"""Hardware backend: open the serial line the upstream GUI opens (pyserial).

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  This package is
model-authored and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs
``reviewed_by`` in driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not
claim it).  The acceptance gate runs the fake backend and never imports this module.

The upstream package is Python 2 and imports PyQt4, so it cannot be imported by this hardware factory.  The
factory opens the same serial line the GUI opens at ``pump_control.py:22`` with pyserial and returns the
pyserial-like object (``write``/``readline``/``close``) the driver speaks to.  Options: ``port`` (required),
``baudrate`` (19200 in ``pump_control.py:22``) and ``timeout_s`` (0.1 s there); ``address`` is read by the
driver, not by this factory.  No hardware run was made by the author of this package.
"""


def connect(port, baudrate=19200, timeout_s=0.1, **options):
    import serial

    link = serial.Serial(port=port, baudrate=int(baudrate), timeout=float(timeout_s),
                         write_timeout=float(timeout_s), **options)
    link.reset_input_buffer()
    return link

"""Hardware backend: opens the upstream HAMEG_HM1507 class on a serial port.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The upstream clone has no setup
metadata and is a single module, so its root must be importable (for example on PYTHONPATH) and pyserial must be
installed (HAMEG_HM1507.py:1).  The option ``port`` is the serial device the upstream ``connect`` takes; the clone
also fixes 19200 baud, RTS/CTS, two stop bits and no parity (HAMEG_HM1507.py:65-67).  The acceptance gate runs the
fake backend and never imports this module or the upstream package, so this package's hardware path has never been
tried.  This package is model-authored and unreviewed, and it is R1, so no human review is claimed.
"""


def connect(port=None, **_options):
    if not isinstance(port, str) or not port:
        raise ValueError("the hardware backend needs the serial port option, for example port='COM7'")
    from HAMEG_HM1507 import HAMEG_HM1507

    device = HAMEG_HM1507()
    device.connect(port)
    return device

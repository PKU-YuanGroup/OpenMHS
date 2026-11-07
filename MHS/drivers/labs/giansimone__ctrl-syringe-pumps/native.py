"""Hardware backend: opens the upstream ctrl_syringe_pumps Control over pyserial.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision); the acceptance gate runs the
fake backend and never imports this module or the upstream package.  This package is model-authored and unreviewed;
it is R2, so the loader refuses its hardware backend until a human sets ``reviewed_by`` in driver.lock.json.

Options of the backend are the upstream constructor's: ``port`` (the serial device, for example
``/dev/tty.usbserial-10``, the clone's default at ``ctrl_syringe_pumps/control.py:7``), ``baud_rate`` (9600 by
default, ``control.py:9``) and ``timeout`` (0.5 s, ``control.py:11``).  The driver talks to the first pump, whose
address the upstream keeps in ``adr1`` (0 by default, ``interface.py:4``).
"""


def connect(**options):
    from ctrl_syringe_pumps.control import Control

    return Control(**options)

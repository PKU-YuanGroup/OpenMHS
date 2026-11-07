"""Hardware backend: open an HP 6632B through the upstream serial class.

Used only with backend="hardware" and the operator's hardware permission.  This package is model-authored and
unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json.  The acceptance gate runs the fake backend and never imports this module or the py6632B package.

``port`` is the serial device the upstream constructor opens (for example ``/dev/ttyUSB0``).  The upstream module is
Python 2-era code (``xrange`` at py6632B/py6632B.py:160, ``isAlive`` at py6632B/py6632B.py:87) and its package
``__init__`` uses an implicit relative import (py6632B/__init__.py:1); this hardware path has never been run.  The
driver never starts the upstream logging thread, so ``log_interval`` and ``log_enable`` only initialise the upstream
fields; the value below is the one the upstream example script passes (lab_script.py:43).
"""


def connect(port, log_interval=5.0, log_enable=False, **_options):
    from py6632B.py6632B import HP6632B

    return HP6632B(port, log_interval, log_enable)

"""Hardware backend: opens the upstream Newport ESP 301 serial class ``esp:esp``.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  The upstream clone is a
single module ``esp.py`` with no packaging metadata, so the operator must make it importable (for example by putting
its clone directory on ``PYTHONPATH``); this factory does not modify or copy the clone.  The acceptance gate runs the
fake backend and never imports this module or the upstream class.

Options: ``dev`` is the serial device path, ``baudrate`` the baud rate and ``axis`` the served axis; further keyword
options (``reset``, ``initpos``, ``useaxis``) are passed to the upstream constructor unchanged.  This package is
model-authored and unreviewed, and its hardware backend is never started here.
"""


def connect(dev, baudrate, axis, **options):
    from esp import esp

    return esp(dev=dev, b=baudrate, axis=axis, **options)

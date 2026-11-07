"""Hardware backend: opens a Cobolt laser through the upstream PythonMicroscope class.

Used only with backend="hardware" and allow_hardware=True, which is an operator decision.  This package is
model-authored and unreviewed and it is R3, so the loader refuses its hardware backend until a human signs
``reviewed_by`` in driver.lock.json.  The acceptance gate runs the fake backend and never imports this module or the
upstream package.

The upstream class lives at ``PythonMicroscope/microscope/lights/cobolt.py`` in the clone; PythonMicroscope is
installed as the ``microscope`` package, so the import below is the installed name.  ``com`` is the serial port of
the controller and the other options follow the upstream constructor (cobolt.py:47-56): ``baud`` (default 115200),
``timeout`` (default 0.1 s) and the pyserial settings.  The constructor opens the port and reads the head maximum
with ``gmlp?`` (cobolt.py:49-65).
"""


def connect(com, baud=115200, timeout=0.1, **options):
    from microscope.lights.cobolt import CoboltLaser

    return CoboltLaser(com=com, baud=baud, timeout=timeout, **options)

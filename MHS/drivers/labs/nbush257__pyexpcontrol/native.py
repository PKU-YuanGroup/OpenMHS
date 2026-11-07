"""Hardware backend: opens a nebPod NPX rig controller through the upstream class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R3: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance
gate runs the fake backend and never imports this module or the upstream package.

The upstream clone keeps the class in ``python/nebPod.py``.  At deployment that ``python/`` directory (or an installed
``nebPod`` module) must be importable; this factory does not modify ``sys.path``.  ``nebPod`` imports PyQt5,
matplotlib and pandas at module import time and tries to add a Windows SpikeGLX SDK path (python/nebPod.py:40-80), so
the hardware host needs those dependencies from the card's install commands.  ``port`` is the Teensy serial port (for
example ``COM11`` or ``/dev/ttyACM0``); ``Controller`` opens it at 115200 baud (python/nebPod.py:267-270).  Remaining
options are passed to ``Controller`` (``gas_map``, ``cobalt_mode``, ``null_voltage``, ``record_control``).
"""


def connect(port, **options):
    from nebPod import Controller

    return Controller(port, **options)

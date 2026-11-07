"""Hardware backend of the NanoDrop 1000 driver: the clone's Code/nanodrop.py:NanoDrop1000 class.

Used only with backend="hardware" (after a human review); the acceptance gate runs the fake backend and never imports
this module.  The clone keeps the class in ``Code/nanodrop.py``, a directory that is not an importable package, so
the deployment adds the clone's ``Code`` directory to ``PYTHONPATH`` and the upstream module is imported as
``nanodrop``.  The upstream requires ``pyusb`` and ``numpy``; the gate's install block is the card's and does not
install them.
"""


def connect(**_options):
    from nanodrop import NanoDrop1000

    device = NanoDrop1000()
    device.connect()
    return device

"""Hardware backend: opens a Temi client through the upstream package's own WebSocket client.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance
gate runs the fake backend and never imports this module or the temi package; nothing here ran on a robot.

The Temi class takes the WebSocket URI of the Temi-side Android server (``src/temi/api.py:9-11``,
``src/temi/README.md:2-3``); the operator supplies it as ``uri``.  There is no default: the address belongs to the
deployment, not to the library.  Any other option goes to the ``Temi`` constructor (``logger`` and ``loglevel`` at
``src/temi/api.py:10``).  The driver connects in its ``setup()`` hook, so this factory only constructs the client.
"""


def connect(uri, **options):
    from temi.api import Temi

    return Temi(uri, **options)

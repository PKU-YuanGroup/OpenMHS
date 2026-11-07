"""Hardware backend: opens a Harvard Apparatus Microliter OEM pump through the upstream pymupump serial classes.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored,
unreviewed and R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in driver.lock.json
(the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance gate runs the fake
backend and never imports this module or the pymupump package.

Options of the backend: ``port`` (required) is the serial device of the pump, for example ``COM3`` on Windows or
``/dev/ttyUSB0`` on Linux.  ``address`` is the pump address configured on the pump (default 0), and ``name`` is the
logging name.  The upstream Chain fixes the serial framing itself: two stop bits, no parity and a 2 s timeout
(``pymupump/pymupump.py:51``); the constructor queries VER and checks the address (``pymupump/pymupump.py:83-88``).
"""


def connect(port, address=0, name="Microliter"):
    import pymupump

    chain = pymupump.Chain(port)
    try:
        return pymupump.Microliter(chain, address=address, name=name)
    except BaseException:
        chain.close()
        raise

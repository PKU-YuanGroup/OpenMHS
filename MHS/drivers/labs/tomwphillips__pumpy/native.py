"""Hardware backend: opens a Harvard PHD 2000 pump through the upstream pumpy serial classes.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored,
unreviewed and R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in driver.lock.json
(the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance gate runs the fake
backend and never imports this module or the pumpy package.

Options of the backend: ``port`` (required) is the serial device of the pump, for example ``COM3`` on Windows or
``/dev/ttyUSB0`` on Linux.  ``address`` is the pump address configured on the pump (default 0), and ``name`` is the
logging name.  The upstream Chain fixes the serial framing itself: two stop bits, no parity and a 2 s timeout
(``pumpy.py:33``); the constructor queries VER to check the pump and its address (``pumpy.py:56-71``).
"""


def connect(port, address=0, name="PHD2000"):
    import pumpy

    chain = pumpy.Chain(port)
    try:
        return pumpy.PHD2000(chain, address=address, name=name)
    except BaseException:
        chain.close()
        raise

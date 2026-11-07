"""Hardware backend: opens a Harvard PHD 2000 pump through the upstream pumpy3 serial classes.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored,
unreviewed and R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in driver.lock.json
(the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance gate runs the fake
backend and never imports this module or the pumpy3 module.

Options of the backend: ``port`` (required) is the serial device of the pump, for example ``COM3`` on Windows or
``/dev/ttyUSB0`` on Linux.  ``address`` is the pump address configured on the instrument (default 0) and ``name`` is
the logging name (``pump.py:524``).  The upstream Chain fixes the serial framing itself: two stop bits, no parity,
eight data bits, an optional baudrate (default 115200) and a 2 s timeout (``pump.py:96-104``).  The PHD 2000
constructor queries VER to check the pump and its address (``pump.py:539-556``).  The upstream imports pyserial; the
task card records no install command, so the operator supplies the environment.
"""


def connect(port, address=0, name="PhD2000"):
    from pump import Chain, Pump2000

    chain = Chain(port)
    try:
        return Pump2000(chain, address=address, name=name)
    except BaseException:
        chain.close()
        raise

"""Hardware backend: opens a New Era syringe pump through the upstream SyrPump serial class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is
model-authored and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs
``reviewed_by`` in driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not
claim it).  The acceptance gate runs the fake backend and never imports this module or the syrpp package.

``port`` (required) and the serial settings (``baudrate``, ``bytesize``, ``parity``, ``stopbits``,
``timeout``) are the keyword arguments of ``syrpp.pump_conn:SyrPump`` (src/syrpp/pump_conn.py:167-183); the
``address`` option belongs to this driver and is consumed here, not passed to the constructor.  The pump
address and baud rate are set on the pump manually before use (README.md:17).
"""


def connect(port, address=0, **options):
    from syrpp.pump_conn import SyrPump

    return SyrPump(port, **options)

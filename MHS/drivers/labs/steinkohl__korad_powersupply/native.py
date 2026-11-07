"""Hardware backend: opens a Korad KC3405P supply through the upstream UDP class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance
gate runs the fake backend and never imports this module or the upstream ``korad`` module.

The upstream is a single module, ``korad.py``, at the root of the clone; it has no packaging metadata, so the
operator makes it importable (for example the clone root on ``PYTHONPATH``).  ``connect(host, port)`` builds the
upstream ``KC3405P(ip_address, port)`` (korad.py:33-36), which opens a UDP socket and binds it locally to the same
port.  The constructor default port is 18190 (korad.py:33).  There is no upstream simulator; the fake backend is an
in-memory stand-in.
"""


def connect(host, port=18190, **options):
    """Open the supply at ``host``; ``options`` (for example ``channel``) is consumed by the driver, not here."""
    from korad import KC3405P

    return KC3405P(host, int(port))

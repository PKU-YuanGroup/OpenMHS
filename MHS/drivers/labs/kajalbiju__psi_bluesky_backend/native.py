"""Hardware backend: opens the upstream MercuryITC class from the pinned clone over PyVISA.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance gate
runs the fake backend and never imports this module or the upstream module.

The upstream module is not an installed package: it is the ``Bluesky4`` directory of the pinned clone, and
``mercury_itc.py`` imports ``instrument_base`` by a bare module name, so that directory must be on sys.path.  The
driver calls the upstream methods; the upstream ``query`` and ``write`` open and close a PyVISA resource for each
call, so the factory only constructs the object and the first command opens the link.

Options of the backend: ``visa_address`` (required) is the PyVISA resource string of the Mercury iTC; the upstream
example uses a TCPIP SOCKET resource (Bluesky4/main.py:25-26).  The clone root is
``<repository>/labs/kajalbiju/psi_bluesky_backend`` at the pinned commit.
"""

from pathlib import Path


def connect(visa_address, **_options):
    import sys

    bluesky4 = Path(__file__).resolve().parents[4] / "labs" / "kajalbiju" / "psi_bluesky_backend" / "Bluesky4"
    if str(bluesky4) not in sys.path:
        sys.path.insert(0, str(bluesky4))
    from mercury_itc import MercuryITC

    return MercuryITC(visa_address)

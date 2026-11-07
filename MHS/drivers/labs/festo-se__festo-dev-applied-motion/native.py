"""Hardware backend: opens the FPosBAPI TCP client of a Festo CECC-X PLC.

Used only with backend="hardware" and allow_hardware=True (an operator
decision).  This package is model-authored and unreviewed, and it is R2:
the loader refuses its hardware backend until a human signs ``reviewed_by``
in driver.lock.json (the loader does this at R2 and R3 only).  The
acceptance gate runs the fake backend and never imports this module or the
``applied_motion`` package.

Options of the backend: ``ip`` (required) is the IPv4 address of the
CECC-X PLC; ``port`` (default 1234) is the FPosBAPI TCP port; ``timeout``
is the socket timeout in seconds (upstream default: ``None``, blocking).
The factory only opens the socket; it sends no motion command.  The drives
must already be enabled and the machine commissioned before the driver is
used.
"""


def connect(ip, port=1234, timeout=None):
    from applied_motion.backends.fposbapi_client import FPosBAPIClient

    return FPosBAPIClient(ip=ip, port=port, timeout=timeout)

"""Hardware backend: opens an Opentrons OT-2 through the upstream HTTP wrapper.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance
gate runs the fake backend and never imports this module or ``ot2_api``.

``host`` is the robot address the upstream constructor accepts: an IP or name, optionally with ``:port`` or as a
whole URL; without it the upstream reads ``OT2_HOST`` and then its link-local default (ot2_api.py:71-81).  ``port``
overrides the port inside ``host``.  ``timeout`` bounds every HTTP request, including the run stop the e-stop sends;
the upstream default is None (wait as long as the robot takes), so this factory chooses a finite default.  It is a
connection setting, not a bound of the device.  The upstream file is not a package: put its clone root on
PYTHONPATH (or an equivalent import path) before using this backend.
"""


def connect(host=None, port=None, timeout=10.0):
    from ot2_api import OpentronsAPI

    return OpentronsAPI(host=host, port=port, timeout=timeout)

"""Hardware backend: opens a Toptica DLCpro through the upstream ``dlccontrol.DLCcontrol`` wrapper.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, and it is R3: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance
gate runs the fake backend and never imports this module, the clone or the Toptica SDK.

The upstream clone is a convenience wrapper around ``toptica.lasersdk`` (dlccontrol.py:15-17); the hardware
environment therefore needs that vendor SDK and ``numpy`` in addition to the clone itself.  The factory passes
``ip`` and every other option to ``DLCcontrol`` (dlccontrol.py:138-159); its default ``open_on_init=True`` calls
``open()``, which queries the device limits and settings (dlccontrol.py:167-178).
"""


def connect(ip, **options):
    from dlccontrol import DLCcontrol

    return DLCcontrol(ip=ip, **options)

"""Hardware backend: open the Luminosa Measurement object through the installed pqlumi.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).
The acceptance gate runs the fake backend and never imports this module or pqlumi.  This
package is model-authored and unreviewed: only the fake backend has been exercised, and no
hardware run is claimed.

The upstream module falls back to ``is_fake = True`` with no-op/canned accessors when the
Delphi bridge ``delphi_pqlumi`` cannot be imported (libs/pqlumi.py:13-18).  That fallback
must never be served as a hardware backend, so this factory refuses it instead of silently
returning a device that only pretends to read the instrument.
"""


def connect(**_options):
    import pqlumi

    if getattr(pqlumi, "is_fake", True):
        raise RuntimeError(
            "pqlumi is running its is_fake fallback (delphi_pqlumi is not importable); refusing a hardware "
            "backend that cannot reach a Luminosa system")
    return pqlumi.measurement

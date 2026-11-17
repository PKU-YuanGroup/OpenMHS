"""Hardware backend: open a LeCroy MAUI oscilloscope through the upstream ``LeCroyScope`` class.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  The factory imports
the pinned upstream module inside the call, so the fake backend of this package and the acceptance gate never
import or run the clone.  ``resource_string`` is the VISA address the upstream constructor accepts
(oscilloscope.py:209-236); ``LeCroyScope`` connects lazily, so the factory calls ``connect()`` and returns the
connected object.  The upstream sets a 10 s VISA timeout at connect (oscilloscope.py:230).

This package is model-authored and unreviewed.  It is R1, so the loader does not gate its hardware backend on a
``reviewed_by`` signature; nothing in this package ran on an instrument.
"""


def connect(resource_string=None, **options):
    from oscilloscope import LeCroyScope

    scope = LeCroyScope(resource_string, **options)
    scope.connect()
    return scope

"""Hardware backend: opens a Keysight InfiniiVision 1200 X-Series oscilloscope through the upstream class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The factory imports the pinned
upstream package inside the call, so the fake backend of this package and the acceptance gate never import or run
the clone.  ``resource_name`` is the VISA address the upstream constructor expects (instrument.py:64-96); the
optional ``timeout_ms`` is passed through, and the upstream default applies when it is absent.

This package is model-authored and unreviewed.  It is R1, so the loader does not gate its hardware backend on a
``reviewed_by`` signature; nothing in this package ran on an instrument.
"""


def connect(resource_name, timeout_ms=None, **options):
    from keysight_dsox1200.instrument import DSOX1200

    if timeout_ms is None:
        return DSOX1200(resource_name, **options)
    return DSOX1200(resource_name, timeout_ms=int(timeout_ms), **options)

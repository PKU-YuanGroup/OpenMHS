"""Hardware backend: opens a Zaber stage through the upstream pymista package.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed.  It is R1, so the SDK loader does not refuse its hardware backend for lack of a signature; a human
must review the package and its hardware path before any hardware use, and this module was never run.  The
acceptance gate runs the fake backend and never imports this module or the pymista package.

The only option is ``port``: the serial device the Zaber connection opens.  With ``port=None`` the upstream
``ZaberStage`` calls ``_getZaberPort()`` and autodetects the adapter by its USB VID/PID (pymista/zaber.py:17-33,
60-71).  The upstream package is installed from the clone with its ``zaber`` extra; importing it imports
``zaber_motion`` and ``serial`` (pymista/zaber.py:5, 9-10).
"""


def connect(port=None, **options):
    if options:
        raise TypeError(f"the ZaberStage factory takes only 'port', not {sorted(options)}")
    from pymista.zaber import ZaberStage

    return ZaberStage(port=port)

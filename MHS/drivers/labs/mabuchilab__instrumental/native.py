"""Hardware backend: opens a Thorlabs DCx (UC480) camera through Instrumental.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed, but it is R1: the loader's refusal of an unreviewed model-written hardware backend applies at R2
and R3 only, so this factory is not covered by it.  The acceptance gate runs the fake backend and never imports
this module or the instrumental package.  Nothing here ran on hardware.

The upstream module is Windows-only (src/instrumental/drivers/cameras/uc480.py:4-5); the UC480 page gives the
Windows-oriented install steps and needs the Thorlabs uc480 API DLL on PATH, pywin32 and nicelib
(docs/uc480-cameras.rst:14-27).  An instrument is opened through the upstream factory with the
driver module ``cameras.uc480``; the identifier options are the ones the class reads from its paramset: ``id``,
``serial`` or ``model`` (src/instrumental/drivers/cameras/uc480.py:578-602).  Without an identifier the upstream
factory accepts the first camera it finds.
"""


def connect(serial=None, id=None, model=None, reopen_policy="strict"):
    """Open a UC480 camera with the upstream Instrumental factory.

    ``reopen_policy`` is the upstream policy for an already-open instrument (src/instrumental/drivers/__init__.py:
    1106-1149); the default is strict, so a second open of the same camera is refused rather than shared.
    """
    from instrumental import instrument

    params = {"module": "cameras.uc480"}
    if serial is not None:
        params["serial"] = serial
    if id is not None:
        params["id"] = int(id)
    if model is not None:
        params["model"] = model
    return instrument(reopen_policy=reopen_policy, **params)

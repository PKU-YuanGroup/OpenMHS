"""Hardware backend: open a Tektronix AFG through the upstream ``tektronix_func_gen:FuncGen``.

Used only with ``backend="hardware"`` and ``allow_hardware=True`` (an operator decision).  This package is
model-authored and unreviewed, and its hardware backend was never run; the acceptance gate runs the fake backend
and never imports this module or the upstream package.

Options of the backend:
``visa_address`` (required) is the VISA resource string the upstream ``FuncGen`` opens (README.md:52).
``impedance`` is ``"highZ"`` or ``"50ohm"`` for both channels, or a pair such as ``["highZ", "50ohm"]``; it tells
the upstream limits which output impedance is in use because the instrument cannot report it (README.md:195-200).
``timeout`` is the VISA timeout in milliseconds (tektronix_func_gen.py:68-69).  ``verify_param_set``, 
``override_compatibility`` and ``verbose`` are passed to the upstream constructor; this package leaves
verification off and printing off.
"""


def connect(visa_address, impedance=("highZ", "highZ"), timeout=1000, verify_param_set=False,
            override_compatibility="", verbose=False):
    from tektronix_func_gen import FuncGen

    if isinstance(impedance, str):
        impedance = (impedance, impedance)
    return FuncGen(visa_address, impedance=tuple(impedance), timeout=timeout,
                   verify_param_set=verify_param_set, override_compatibility=override_compatibility,
                   verbose=verbose)

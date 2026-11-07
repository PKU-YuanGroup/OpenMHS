"""Hardware backend: attaches to a running Tecan FluentControl through the upstream Tecan class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored,
unreviewed and R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in driver.lock.json
(the loader does this at R2 and R3 only).  The acceptance gate runs the fake backend and never imports this module or
the upstream package.

The upstream module imports ``clr`` and adds the .NET reference ``Tecan.VisionX.API.V2`` at import time
(tecan_fluent/tecan_ctrl.py:1-7); it needs pythonnet and a Windows FluentControl installation under
C:/Program Files (x86)/Tecan/FluentControl (README.md:29-36).  ``Tecan()`` raises RuntimeError when FluentControl is
not running (tecan_fluent/tecan_ctrl.py:20-23).  The FluentControl script must have reached its ``Create API Channel``
command before a command can run; the driver does not wait for it, so a missing channel is a precondition failure.

No hardware was attached or run by this package.
"""


def connect(**_options):
    if _options:
        raise TypeError(f"the Tecan Fluent hardware backend takes no options, got {sorted(_options)}")
    from tecan_fluent.tecan_ctrl import Tecan

    return Tecan()

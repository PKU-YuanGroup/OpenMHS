"""Hardware backend: open the MSOX2024A through the upstream ``scope:Scope`` class.

Used only with ``backend="hardware"`` and ``allow_hardware=True``, which is an operator decision.  This package is
model-authored and unreviewed (``driver.lock.json`` ``reviewed_by`` is null) and nothing in it ever ran against an
instrument.  The loader refuses the hardware backend of an unreviewed model-written package at R2 and R3 only; this
package is R1, so that loader guard does not apply to it and must not be claimed here.

The upstream clone ships ``scope.py`` as a top-level module and opens the VISA resource itself
(TCPIP0::<ip>::inst0::INSTR, scope.py:15-16).  ``scope.py`` imports numpy and pyvisa (scope.py:5-6), and the upstream
README installs pyvisa, pyvisa-py and numpy (README.md:17), so the deployment puts the pinned clone on ``PYTHONPATH``
and installs those dependencies.  ``ip`` is the oscilloscope address the upstream constructor expects; the optional
``timeout_ms`` is passed through and the upstream default applies when it is absent (scope.py:14).
"""


def connect(ip, timeout_ms=None, **options):
    from scope import Scope

    if timeout_ms is None:
        return Scope(ip, **options)
    return Scope(ip, timeout_ms=int(timeout_ms), **options)

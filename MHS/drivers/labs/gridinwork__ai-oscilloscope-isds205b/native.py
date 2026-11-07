"""Hardware backend: opens one ISDS205B through the upstream ctypes wrapper.

Used only with backend="hardware" and allow_hardware=True (an operator decision) and a writable state_dir for the
e-stop latch.  This package is model-authored and unreviewed.  It is R1, and the loader requires a human
``reviewed_by`` signature for a model-written hardware package at R2 and R3 only, so this R1 backend is not refused by
the loader: an operator must still review the package and decide to open the device.  The acceptance gate runs the
fake backend and never imports this module or the upstream ``instrustar`` package; no hardware was attached.

The upstream wrapper loads ``instrustar/bin/vdso_x64.dll`` with ``ctypes.WinDLL`` (instrustar/device.py:37-38, 87-91),
so this hardware path is Windows x64 only even though the task card's install block says platform any.  The upstream
Scope() constructor takes no options; ``connect(timeout_s=5.0)`` initialises the DLL and waits for the device.
"""


def connect(timeout_s=5.0):
    from instrustar.device import Scope

    device = Scope()
    device.connect(timeout_s=timeout_s)
    return device

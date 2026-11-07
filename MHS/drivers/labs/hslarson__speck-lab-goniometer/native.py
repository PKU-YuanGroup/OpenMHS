"""Hardware backend: opens a Thorlabs compact spectrometer through the upstream pyCCT wrapper.

Used only with backend="hardware" and allow_hardware=True, an operator decision.  The acceptance gate runs the fake
backend and never imports this module or the upstream package, and no hardware run was made.  This package is
model-authored, unreviewed and R1; the loader refuses an unreviewed model-written hardware backend only at R2 and R3,
so this R1 package does not rely on that protection.

The clone is a source tree rather than an installed package.  ``PyCCT`` loads the .NET assemblies from its own
``net48`` directory and discovers devices through StartupHelperCompactSpectrometer
(src/components/pyCCT/pyCCT.py:23-37, 91-118).  Pass ``clone_root`` (the root of the speck-lab-goniometer clone) or
put ``<clone>/src`` on PYTHONPATH so that ``components.pyCCT.pyCCT`` imports.  ``dll_path`` is forwarded to
``PyCCT`` (its default is the ``net48`` directory next to pyCCT.py), and ``device_id`` optionally selects one of the
discovered connection keys instead of the first one.
"""

import sys
from pathlib import Path


def connect(*, clone_root=None, dll_path="./net48", device_id=None):
    """Open one discovered spectrometer and return its ``SpectrometerWrapper``."""
    if clone_root is not None:
        source = Path(clone_root) / "src"
        if str(source) not in sys.path:
            sys.path.insert(0, str(source))
    from components.pyCCT.pyCCT import PyCCT

    pycct = PyCCT(dll_path=dll_path)
    known = list(pycct.discover_devices())
    if not known:
        raise RuntimeError("PyCCT.discover_devices() found no spectrometer")
    chosen = device_id if device_id is not None else known[0]
    wrapper = pycct.connect_to_device(chosen)
    if wrapper is None:
        raise RuntimeError(f"PyCCT.connect_to_device({chosen!r}) returned None")
    return wrapper

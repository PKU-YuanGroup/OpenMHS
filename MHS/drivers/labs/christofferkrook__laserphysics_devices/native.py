"""Hardware backend: opens the upstream Ando class from the pinned clone.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed and is R1, so the loader's reviewed_by refusal for model-written R2/R3 packages does not apply here: the
hardware backend must still be used only after a human reviews the package.  The acceptance gate runs the fake
backend and never imports this module or the upstream clone.  No hardware run is claimed.

The upstream clone has no root package (``OSA/old_osa/Ando.py`` is loaded by file path).  ``source`` is the clone
directory; by default it is the clone the task card names, relative to the repository root.  ``address`` is the GPIB
address passed to ``Ando(gpib_address)`` (OSA/old_osa/Ando.py:13-17); the upstream wrapper imports pyvisa.
"""


def connect(address, source=None, **options):
    from importlib.util import module_from_spec, spec_from_file_location
    from pathlib import Path

    root = Path(source) if source is not None else (
        Path(__file__).resolve().parents[4] / "labs" / "christofferkrook" / "laserphysics_devices")
    path = root / "OSA" / "old_osa" / "Ando.py"
    spec = spec_from_file_location("_laserphysics_devices_ando", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load the upstream Ando class from {path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Ando(address)

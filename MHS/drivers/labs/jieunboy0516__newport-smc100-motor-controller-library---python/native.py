"""Hardware backend: opens a Newport SMC100 through the upstream smc100 class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  The clone is a two-file library, not
an installable package: the operator passes the path of ``smc100_base.py`` (or of the clone directory) as
``library_path``.  The upstream constructor opens a pyserial port at 57600 baud, 8N1 with a 10 s timeout
(smc100_base.py:76-95); when the open fails it only prints that it uses a dummy motor controller and does not replace
the serial object (smc100_base.py:89-95), so this factory lets the upstream exception surface instead of pretending a
connection exists.

This package is model-authored and unreviewed, and it is R1: the loader's review_required refusal for model-authored
R2/R3 packages does not cover it, and no SDK protection is claimed.  The gate never imports this module and nothing
here ran.
"""


def connect(port, library_path=None, **options):
    """Load the clone's smc100_base.py and return ``smc100(COM=port, **options)``."""
    from importlib.util import module_from_spec, spec_from_file_location
    from pathlib import Path

    if not library_path:
        raise RuntimeError("library_path must name the clone's smc100_base.py or the clone directory")
    path = Path(library_path)
    if path.is_dir():
        path = path / "smc100_base.py"
    spec = spec_from_file_location("smc100_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load the upstream module from {path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.smc100(COM=port, **options)

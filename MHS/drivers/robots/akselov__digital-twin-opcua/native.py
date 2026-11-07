"""Hardware backend: opens the KUKA KR C4 through the clone's KUKAVARPROXY client.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored and
unreviewed, and it is R2: the loader refuses its hardware backend until a human signs ``reviewed_by`` in
driver.lock.json (the loader does this at R2 and R3 only; an R0 or R1 package must not claim it).  The acceptance
gate runs the fake backend and never imports this module or the clone, and nothing here ran on a robot.

The clone is a set of thesis scripts, not an installable package: the entry class lives in
``xml/KUKAVARPROXY_communication.py``.  The file is loaded by path under a private module name because ``xml`` is
also a Python standard-library package; the clone's module creates its socket at import and the KUKA constructor
connects it to TCP port 7000 (xml/KUKAVARPROXY_communication.py:20-28).  ``TCP_IP`` is the controller address the
upstream KUKA constructor takes (for example the IP the object XML carries, xml/KUKA_KR16_2_object.xml:138).
``clone_root`` selects another checkout of gh.akselov/digital-twin-opcua; the default is this repository's clone.
"""

import importlib.util
from pathlib import Path


def connect(TCP_IP, *, clone_root=None, **options):
    """Open one KUKA KR C4 KVP connection and return the clone's ``KUKA`` object."""
    if not isinstance(TCP_IP, str) or not TCP_IP.strip():
        raise ValueError("TCP_IP is required: the address of the KUKA KR C4 controller running KukaVarProxy")
    root = Path(clone_root) if clone_root is not None else (
        Path(__file__).resolve().parents[4] / "robots" / "akselov" / "digital-twin-opcua"
    )
    source = root / "xml" / "KUKAVARPROXY_communication.py"
    if not source.is_file():
        raise FileNotFoundError(f"{source} is not a checkout of gh.akselov/digital-twin-opcua")
    spec = importlib.util.spec_from_file_location("_akselov_kukavarproxy_communication", source)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.KUKA(TCP_IP.strip())

"""Shared paths for the packaging tests (no imports of ``mhs`` here)."""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
SDK = HERE.parents[1]                 # MHS/sdk
SRC = SDK / "src"                     # MHS/sdk/src
PACKAGE = SRC / "mhs"                 # MHS/sdk/src/mhs
MHS_ROOT = SDK.parent                 # MHS
WORKSPACE = MHS_ROOT.parent           # repository root
SCHEMA_DIR = MHS_ROOT / "schema"
SYNC_TOOL = SDK / "tools" / "sync_data.py"
EXAMPLE_DEVICE = SCHEMA_DIR / "examples" / "device.conveyor-workcell.json"


def load_sync_tool():
    """Import ``MHS/sdk/tools/sync_data.py`` as a module."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_openmhs_sync_data", SYNC_TOOL)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

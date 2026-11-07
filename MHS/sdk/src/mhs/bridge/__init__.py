"""MHS bridge families (MHS-000 section 9.3).

A *bridge* is a reusable runtime that executes an adapter's declarative mapping
for one equipment family.  The families shipped here (the pilot helpers of the
OpenMHS 0.9 plan) are:

==============  ==========================================================
module          family
==============  ==========================================================
``base``        ``Bridge`` contract, ``AsyncRunner``, field/unit/limit/error maps
``bindings``    canonical MHS-006 §4/§7 ``mhs/bindings.json`` loader
``python``      ``python-object`` -- any importable (sync or async) Python object
``gymnasium``   ``gymnasium`` (and legacy ``gym``) environments
``mujoco``      MuJoCo models
``serial``      line-oriented serial instruments (pyserial)
``scpi``        SCPI instruments over stdlib sockets or pyvisa
``transcript``  record/replay of serial, SCPI and HTTP-like exchanges (fakes)
``replay``      recorded evidence/state bundles, read-only
==============  ==========================================================

Optional equipment libraries (gymnasium, mujoco, pyserial, pyvisa) are imported
lazily; ``available_bridges()`` reports which families can be opened in this
runtime.  Bridge modules are libraries: ``python -m mhs.bridge.<x>`` exits 2
with ``use: mhs serve <driver-dir|mhs-adapter.json>``.

The package imports its modules lazily (PEP 562 ``__getattr__``): ``from
mhs.bridge import PythonObjectBridge`` works as before, and ``python -m
mhs.bridge.<x>`` runs ``<x>`` without importing it twice (no runpy warning).
"""

from __future__ import annotations

import importlib
from typing import Any

#: Exported name -> (module, attribute); resolved on first access.
_EXPORTS: dict[str, tuple[str, str]] = {
    "AsyncRunner": ("mhs.bridge.base", "AsyncRunner"),
    "Bridge": ("mhs.bridge.base", "Bridge"),
    "BridgeContext": ("mhs.bridge.base", "BridgeContext"),
    "BridgeError": ("mhs.bridge.base", "BridgeError"),
    "ErrorMap": ("mhs.bridge.base", "ErrorMap"),
    "FieldMapping": ("mhs.bridge.base", "FieldMapping"),
    "MappingError": ("mhs.bridge.base", "MappingError"),
    "UnitError": ("mhs.bridge.base", "UnitError"),
    "convert_unit": ("mhs.bridge.base", "convert_unit"),
    "jsonable": ("mhs.bridge.base", "jsonable"),
    "make_mhs_error": ("mhs.bridge.base", "make_mhs_error"),
    "BindingDocument": ("mhs.bridge.bindings", "BindingDocument"),
    "load_bindings": ("mhs.bridge.bindings", "load_bindings"),
    "normalize_binding": ("mhs.bridge.bindings", "normalize_binding"),
    "validate_binding": ("mhs.bridge.bindings", "validate_binding"),
    "PythonObjectBridge": ("mhs.bridge.python", "PythonObjectBridge"),
    "ReplayBridge": ("mhs.bridge.replay", "ReplayBridge"),
    "ScpiBridge": ("mhs.bridge.scpi", "ScpiBridge"),
    "Transcript": ("mhs.bridge.transcript", "Transcript"),
    "TranscriptDivergence": ("mhs.bridge.transcript", "TranscriptDivergence"),
}

#: Optional families: ``None`` when the module cannot be imported here.
_OPTIONAL_EXPORTS: dict[str, tuple[str, str]] = {
    "GymnasiumBridge": ("mhs.bridge.gymnasium", "GymnasiumBridge"),
    "MujocoBridge": ("mhs.bridge.mujoco", "MujocoBridge"),
    "SerialBridge": ("mhs.bridge.serial", "SerialBridge"),
}

#: Bridge family -> (exported class name, optional third-party dependency)
_FAMILIES: dict[str, tuple[str, str | None]] = {
    "python-object": ("PythonObjectBridge", None),
    "gymnasium": ("GymnasiumBridge", "gymnasium"),
    "mujoco": ("MujocoBridge", "mujoco"),
    "serial": ("SerialBridge", "pyserial"),
    "scpi": ("ScpiBridge", None),
    "scpi-visa": ("ScpiBridge", None),   # the normative family name (adapter.schema.json)
    "replay": ("ReplayBridge", None),
}

__all__ = sorted([*_EXPORTS, *_OPTIONAL_EXPORTS, "BRIDGE_FAMILIES", "available_bridges"])


def _resolve(name: str) -> Any:
    if name in _EXPORTS:
        module, attribute = _EXPORTS[name]
        return getattr(importlib.import_module(module), attribute)
    module, attribute = _OPTIONAL_EXPORTS[name]
    try:
        return getattr(importlib.import_module(module), attribute)
    except Exception:  # pragma: no cover - defensive: the modules import no third-party code
        return None


def _families() -> dict[str, tuple[object, str | None]]:
    """Bridge family -> (class, optional third-party dependency)."""

    return {family: (_resolve(name), dependency) for family, (name, dependency) in _FAMILIES.items()}


def __getattr__(name: str) -> Any:
    if name in _EXPORTS or name in _OPTIONAL_EXPORTS:
        value = _resolve(name)
        globals()[name] = value
        return value
    if name == "BRIDGE_FAMILIES":
        value = _families()
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))


def available_bridges() -> dict[str, bool]:
    """Return which bridge families can be constructed in this interpreter.

    A ``False`` entry means the optional equipment library is absent; the bridge
    module still imports and its unit tests skip, but an endpoint built on that
    family cannot open equipment here.
    """

    status: dict[str, bool] = {}
    for family, (cls, dependency) in _families().items():
        if dependency is None or cls is None:
            status[family] = cls is not None
            continue
        available = getattr(cls, "available", None)
        if callable(available):
            try:
                status[family] = bool(available())
            except Exception:  # noqa: BLE001
                status[family] = False
        else:  # pragma: no cover - every optional bridge defines available()
            status[family] = False
    return status

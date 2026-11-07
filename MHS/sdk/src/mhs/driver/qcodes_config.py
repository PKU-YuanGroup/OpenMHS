"""Pure, bounded compilation of explicitly declared QCoDeS Parameter paths."""
from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from typing import Any

from .spec import DriverDefinitionError, Field
from .upstream import parse_ref, safe_relpath

_PATH = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*){0,7}\Z")
_KEYS = frozenset({"parameter", "get", "set", "timeout_ms", "source_ref", "factory_ref"})


def parameter_specs(bindings: Any, fields: Any) -> dict[str, dict[str, Any]]:
    """Return an owned finite declaration; no native objects or imports are consulted."""
    if not isinstance(bindings, Mapping) or not 1 <= len(bindings) <= 128:
        raise DriverDefinitionError("parameter_bindings must contain 1..128 explicit Parameter bindings")
    if not isinstance(fields, Mapping):
        raise DriverDefinitionError("parameters must be a mapping of Field declarations")
    out: dict[str, dict[str, Any]] = {}
    paths: set[str] = set()
    for name, raw in bindings.items():
        if not isinstance(name, str) or not isinstance(fields.get(name), Field):
            raise DriverDefinitionError(f"parameter_bindings[{name!r}] must name a declared Field")
        if not isinstance(raw, Mapping) or set(raw) - _KEYS:
            raise DriverDefinitionError(f"parameter_bindings[{name!r}] has unknown keys or is not a mapping")
        item = copy.deepcopy(dict(raw))
        path = item.get("parameter")
        if not isinstance(path, str) or len(path) > 200 or not _PATH.fullmatch(path):
            raise DriverDefinitionError(f"{name}: parameter must be a finite public dotted attribute path")
        if path in paths:
            raise DriverDefinitionError(f"{name}: duplicate Parameter selector {path!r}")
        paths.add(path)
        for op in ("get", "set"):
            if type(item.get(op)) is not bool:
                raise DriverDefinitionError(f"{name}: {op} must be an explicit boolean")
        if not item["get"]:
            raise DriverDefinitionError(f"{name}: this measurement profile requires get=True (no cache-only state)")
        if item["set"] != fields[name].writable:
            raise DriverDefinitionError(f"{name}: set must match Field.writable")
        timeout = item.get("timeout_ms")
        if type(timeout) is not int or not 1 <= timeout <= 60000:
            raise DriverDefinitionError(f"{name}: timeout_ms must be an integer in 1..60000")
        for key in ("source_ref", "factory_ref"):
            if key == "factory_ref" and key not in item:
                continue
            ref = parse_ref(item.get(key))
            if ref is None or safe_relpath(ref.path) != ref.path or ref.end - ref.line > 200:
                raise DriverDefinitionError(f"{name}: {key} must cite a bounded relative path:LINE[-END]")
        out[name] = item
    return out


def compile_parameters(bindings: Any, fields: Any, reads: Any, writes: Any):
    specs = parameter_specs(bindings, fields)
    if not isinstance(reads, Mapping) or not isinstance(writes, Mapping):
        raise DriverDefinitionError("reads and writes must be mappings")
    out_reads, out_writes = copy.deepcopy(dict(reads)), copy.deepcopy(dict(writes))
    for name, item in specs.items():
        if name in out_reads or name in out_writes:
            raise DriverDefinitionError(f"{name}: Parameter binding cannot overlap explicit reads or writes")
        out_reads[name] = {"native": item["parameter"] + ".get", "invoke": "call",
                           "timeout_ms": item["timeout_ms"]}
        if item["set"]:
            out_writes[name] = {"native": item["parameter"] + ".set", "invoke": "call",
                               "timeout_ms": item["timeout_ms"]}
    return out_reads, out_writes

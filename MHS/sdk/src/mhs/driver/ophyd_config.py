"""Bounded classic-Ophyd Signal compilation; no imports or native discovery."""
from __future__ import annotations
import copy
import re
from collections.abc import Mapping
from .spec import DriverDefinitionError, Field
from .upstream import parse_ref, safe_relpath

_PATH = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*){0,7}\Z")
_KEYS = {"signal", "get", "set", "get_kwargs", "timeout_ms", "source_ref", "profile"}


def signal_specs(bindings, fields):
    if not isinstance(bindings, Mapping) or not 1 <= len(bindings) <= 128:
        raise DriverDefinitionError("signal_bindings needs 1..128 explicit entries")
    if not isinstance(fields, Mapping):
        raise DriverDefinitionError("parameters must be a Field mapping")
    out, paths = {}, set()
    for name, raw in bindings.items():
        if not isinstance(name, str) or not isinstance(fields.get(name), Field):
            raise DriverDefinitionError(f"signal binding {name!r} must name an existing Field")
        if not isinstance(raw, Mapping) or set(raw) - _KEYS:
            raise DriverDefinitionError(f"signal binding {name!r} has unsupported keys")
        item = copy.deepcopy(dict(raw));path = item.get("signal")
        if not isinstance(path, str) or len(path) > 200 or not _PATH.fullmatch(path):
            raise DriverDefinitionError(f"{name}: signal must be a bounded public attribute path")
        if any(path == other or path.startswith(other + ".") or other.startswith(path + ".") for other in paths):
            raise DriverDefinitionError(f"{name}: duplicate or overlapping Signal selectors")
        paths.add(path)
        if type(item.get("get")) is not bool or type(item.get("set")) is not bool or not item["get"]:
            raise DriverDefinitionError(f"{name}: exact get=True and set boolean are required")
        if item["set"] != fields[name].writable:
            raise DriverDefinitionError(f"{name}: set must match Field.writable")
        if type(item.get("timeout_ms")) is not int or not 1 <= item["timeout_ms"] <= 60000:
            raise DriverDefinitionError(f"{name}: timeout_ms must be integer 1..60000")
        profile = item.get("profile")
        if type(profile) is not str or profile not in ("classic_epics_v1", "classic_epics_ro_v1", "classic_soft_v1"):
            raise DriverDefinitionError(f"{name}: an explicit classic_epics_v1, classic_epics_ro_v1 or classic_soft_v1 "
                                        "profile is required")
        # classic_epics_ro_v1 is the get-only EpicsSignalRO profile: no write is compiled for it.
        if profile == "classic_epics_ro_v1" and item["set"]:
            raise DriverDefinitionError(f"{name}: classic_epics_ro_v1 is get-only (EpicsSignalRO); set must be False")
        kwargs = item.get("get_kwargs")
        expected = {"use_monitor": False} if profile in ("classic_epics_v1", "classic_epics_ro_v1") else {}
        if not isinstance(kwargs, Mapping) or dict(kwargs) != expected or (kwargs and type(kwargs.get("use_monitor")) is not bool):
            raise DriverDefinitionError(f"{name}: get_kwargs must be {expected!r} for this profile")
        item["get_kwargs"] = dict(kwargs)
        ref = parse_ref(item.get("source_ref"))
        if ref is None or safe_relpath(ref.path) != ref.path or ref.end - ref.line > 200:
            raise DriverDefinitionError(f"{name}: source_ref needs bounded relative path:LINE[-END]")
        out[name] = item
    return out


def compile_signals(bindings, fields, reads, writes):
    specs = signal_specs(bindings, fields)
    if not isinstance(reads, Mapping) or not isinstance(writes, Mapping):
        raise DriverDefinitionError("reads/writes must be mappings")
    compiled_reads, compiled_writes = copy.deepcopy(dict(reads)), copy.deepcopy(dict(writes))
    for name, spec in specs.items():
        if name in reads or name in writes:
            raise DriverDefinitionError(f"{name}: Signal binding overlaps an explicit field map")
        compiled_reads[name] = {"native": spec["signal"] + ".get", "invoke": "call",
                                "timeout_ms": spec["timeout_ms"],
                                "args": {key: {"value": value} for key, value in spec["get_kwargs"].items()}}
        if spec["set"]:
            compiled_writes[name] = {"native": spec["signal"] + ".set", "invoke": "status",
                                     "timeout_ms": spec["timeout_ms"]}
    return compiled_reads, compiled_writes


# Unit labels describe native values; this API never converts their magnitude.
# Only top-level fields with no declared unit/native-unit conversion are eligible.
def compile_unit_metadata(parameters, actions, bindings, defaults, options, backend):
    from .. import units
    if not isinstance(bindings, Mapping) or len(bindings) > 128:
        raise DriverDefinitionError("unit_bindings must be a mapping with at most 128 entries")
    if not isinstance(defaults, Mapping) or not isinstance(options, Mapping):
        raise DriverDefinitionError("fake_unit_defaults and options must be mappings")
    params = copy.deepcopy(dict(parameters))
    acts = copy.deepcopy(dict(actions))
    values = copy.deepcopy(dict(options))
    targets = {"parameters." + name: field for name, field in params.items()}
    for capability_id, action in acts.items():
        for direction in ("input", "output"):
            for name, field in (getattr(action, direction) or {}).items():
                targets[f"actions.{capability_id}.{direction}.{name}"] = field
    option_names = set()
    for path, option in bindings.items():
        if path not in targets or not isinstance(option, str) or not _PATH.fullmatch(option) or "." in option:
            raise DriverDefinitionError("unit_bindings needs an exact top-level Field path and a public option name")
        option_names.add(option)
    if set(defaults) - option_names:
        raise DriverDefinitionError("fake_unit_defaults may only name declared unit options")
    for option in option_names:
        if option not in values and backend == "fake" and option in defaults:
            values[option] = copy.deepcopy(defaults[option])
        value = values.get(option)
        if not isinstance(value, str) or not units.is_known(value):
            raise DriverDefinitionError(f"supply explicit supported {option} before constructing this backend")
    for path, option in bindings.items():
        field = targets[path]
        if type(field) is not Field or field.type not in ("number", "integer"):
            raise DriverDefinitionError(f"{path}: unit metadata requires a plain numeric Field")
        if field.native_unit is not None:
            raise DriverDefinitionError(f"{path}: unit metadata does not implement native-unit conversion")
        if field.unit is not None and field.unit != values[option]:
            raise DriverDefinitionError(f"{path}: an explicit declared unit cannot be changed by instance metadata")
        for _, limit in field.limit_entries("value"):
            if not limit.is_operator_required and (field.unit is None or limit.unit not in (None, field.unit)):
                raise DriverDefinitionError(f"{path}: a sourced bound needs its fixed declared unit; use operator_required for unbound native units")
        field.unit = values[option]
    return params, acts, values


def model_contract(value):
    """Complete bounded structural model value, with no ignored safety keys.

    Every dataclass field and Field/Limit slot is included. Unknown object types
    are refused instead of invoking a caller serialization hook.
    """
    import dataclasses
    import math
    from ..catalog import Effective
    from .model import DriverModel, ParamModel, BindingModel, EstopModel, InterlockModel
    from .spec import Fact, Limit
    allowed = {DriverModel, ParamModel, BindingModel, EstopModel, InterlockModel, Effective}
    active = set()
    budget = [100000]
    def convert(item, depth=0):
        budget[0] -= 1
        if budget[0] < 0 or depth > 64:
            raise DriverDefinitionError("Ophyd model exceeds the bounded contract comparison")
        kind = type(item)
        if item is None or kind in (str, bool, int):
            return item
        if kind is float:
            if not math.isfinite(item):
                raise DriverDefinitionError("Ophyd model contains a nonfinite value")
            return item
        identity = id(item)
        if identity in active:
            raise DriverDefinitionError("Ophyd model contains a cyclic value")
        active.add(identity)
        try:
            if kind in (list, tuple):
                return {"type": kind.__name__, "items": [convert(v, depth + 1) for v in item]}
            if kind is dict:
                if any(type(key) is not str for key in item):
                    raise DriverDefinitionError("Ophyd model mapping keys must be strings")
                return {key: convert(val, depth + 1) for key, val in item.items()}
            if kind in allowed:
                return {"type": kind.__module__ + "." + kind.__qualname__, "fields": {
                    field.name: convert(getattr(item, field.name), depth + 1) for field in dataclasses.fields(item)}}
            if kind in (Field, Limit, Fact):
                return {"type": kind.__module__ + "." + kind.__qualname__, "slots": {
                    name: convert(getattr(item, name), depth + 1) for name in kind.__slots__}}
            raise DriverDefinitionError(f"unsupported Ophyd model value {kind.__module__}.{kind.__qualname__}")
        finally:
            active.remove(identity)
    return convert(value)

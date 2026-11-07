"""Test inputs for the conformance suite: fixtures, class examples, envelope-aware synthesis.

The suite needs, for the capability it probes, a valid input, a second valid
input that differs from the first, and inputs that are inside the schema but
outside the effective limits.  They come, in this order (CONF-01):

1. a **fixture file** supplied by the driver author (:class:`Fixtures`);
2. the catalogue class **examples**, projected onto the fields the binding
   declares and kept only when they validate and respect the limits;
3. **synthesis** from the input schema that honours the effective limits
   element-wise.

The effective limits of a binding are resolved exactly as the runtime does:
:func:`mhs._server.limits_plan.compile_binding` (class ∩ binding ∩ envelope,
patterns included, through :mod:`mhs.limits`) over the published manifest,
intersected with the limits the endpoint itself publishes for the binding in
``devices.get`` (``x-mhs-effective-limits``, which include the operator
overlay ``site-limits.json``, plan 3.5).  An endpoint that publishes a wider
limit than its manifest declares is noted; the declared one still applies.

Strings constrained by ``pattern`` or ``format`` are never invented: a
required one without a fixture or example raises :class:`Unsynthesizable`,
and the calling test reports ``skip`` with the reason (it does not fail the
endpoint for a suite limitation).  The one exception is the SAFE-014 probe of
an allowed set on a ``pattern`` string: a same-shape mutation of an allowed
value is sent only when the pattern and the field schema accept it; when none
does, the path is a :class:`Gap` and SAFE-014 cannot pass.

Fixture file format (JSON)::

    {
      "probe": "cap.thermal.setpoint.v1",              # optional: capability to probe
      "capabilities": {
        "cap.thermal.setpoint.v1": {
          "valid": {"target_temperature": 37},
          "alternate": {"target_temperature": 38},
          "out_of_envelope": [{"target_temperature": 81}]
        }
      },
      "devices": {"<device_id>": {"<capability_id>": {...}}}   # optional per-device overrides
    }

A flat ``{capability_id: {...}}`` mapping is accepted too.
"""

from __future__ import annotations

import copy
import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

from mhs import canonical

__all__ = [
    "Binding",
    "Fixtures",
    "Gap",
    "LeafBound",
    "Probe",
    "ProbePlan",
    "Unsynthesizable",
    "alternate_input",
    "base_from_fixture",
    "bindings_for",
    "envelope_probe_plan",
    "envelope_probes",
    "fixture_sides",
    "limit_path_of",
    "load_fixtures",
    "only_empty_input",
    "published_limits",
    "served_input",
    "valid_input",
    "violated_sides",
]

_MAX_DEPTH = 8
#: Hard cap on the probed elements of one binding (SAFE-014).  Every probe of
#: an element is mandatory: both sides of a bound and the allowed set, at every
#: limited path, at the first and the last element of every array on the path
#: (every element of a per-element bound).  Elements beyond the cap are
#: reported (:attr:`ProbePlan.unprobed`) and SAFE-014 cannot pass.
_MAX_PATH_PROBES = 256


class Unsynthesizable(Exception):
    """No valid input can be built without a fixture; ``str(exc)`` is the reason."""


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


class Fixtures:
    """Driver-supplied inputs keyed by capability id (and optionally device id)."""

    def __init__(self, document: Mapping[str, Any] | None = None):
        document = dict(document or {})
        self.document = document
        capabilities = document.get("capabilities")
        if not isinstance(capabilities, Mapping):
            capabilities = {key: value for key, value in document.items()
                            if isinstance(value, Mapping) and key not in ("devices",)}
        self.capabilities: dict[str, dict[str, Any]] = {str(k): dict(v) for k, v in capabilities.items()}
        devices = document.get("devices")
        self.devices: dict[str, dict[str, dict[str, Any]]] = {}
        if isinstance(devices, Mapping):
            for device_id, entries in devices.items():
                if isinstance(entries, Mapping):
                    self.devices[str(device_id)] = {str(k): dict(v) for k, v in entries.items()
                                                    if isinstance(v, Mapping)}
        probe = document.get("probe")
        self.probe: str | None = str(probe) if isinstance(probe, str) else None

    def __bool__(self) -> bool:
        return bool(self.capabilities or self.devices or self.probe)

    def entry(self, device_id: str | None, capability_id: str) -> dict[str, Any]:
        if device_id and capability_id in self.devices.get(str(device_id), {}):
            return self.devices[str(device_id)][capability_id]
        return self.capabilities.get(capability_id, {})

    @property
    def digest(self) -> str | None:
        return canonical.digest(self.document) if self.document else None


def load_fixtures(source: Any) -> Fixtures:
    """Build :class:`Fixtures` from ``None``, a mapping, a JSON file path or a ``Fixtures``."""

    if source is None:
        return Fixtures()
    if isinstance(source, Fixtures):
        return source
    if isinstance(source, Mapping):
        return Fixtures(source)
    if isinstance(source, (str, os.PathLike)):
        document = json.loads(Path(source).read_text(encoding="utf-8"))
        if not isinstance(document, Mapping):
            raise ValueError(f"fixture file {source!r} does not contain a JSON object")
        return Fixtures(document)
    raise TypeError(f"unsupported fixtures source {type(source).__name__}")


# ---------------------------------------------------------------------------
# schema helpers
# ---------------------------------------------------------------------------


def _types(schema: Mapping[str, Any]) -> list[str]:
    declared = schema.get("type")
    if isinstance(declared, str):
        return [declared]
    if isinstance(declared, list):
        return [item for item in declared if isinstance(item, str)]
    return []


def _primary_type(schema: Mapping[str, Any]) -> str | None:
    types = [item for item in _types(schema) if item != "null"]
    if types:
        return types[0]
    if "properties" in schema or "required" in schema:
        return "object"
    if "items" in schema or "prefixItems" in schema:
        return "array"
    if "enum" in schema or "const" in schema:
        return None
    if _types(schema) == ["null"]:
        return "null"
    return None


def _local(root: Mapping[str, Any], ref: str) -> Any:
    if not isinstance(ref, str) or not ref.startswith("#"):
        return None
    try:
        return canonical.json_pointer_get(root, ref[1:]) if ref != "#" else root
    except Exception:  # noqa: BLE001 - an unresolvable $ref is simply not followed
        return None


def _resolve(schema: Any, root: Mapping[str, Any], depth: int = 0) -> dict[str, Any]:
    """Flatten local ``$ref`` and ``allOf`` into one schema (first win for conflicting keywords)."""

    if not isinstance(schema, Mapping) or depth > _MAX_DEPTH:
        return {}
    out: dict[str, Any] = {}
    ref = schema.get("$ref")
    if isinstance(ref, str):
        out.update(_resolve(_local(root, ref), root, depth + 1))
    for key, value in schema.items():
        if key in ("$ref", "allOf"):
            continue
        if key == "properties" and isinstance(value, Mapping) and isinstance(out.get("properties"), Mapping):
            merged = dict(out["properties"])
            merged.update(value)
            out["properties"] = merged
        elif key == "required" and isinstance(value, list) and isinstance(out.get("required"), list):
            out["required"] = list(dict.fromkeys(list(out["required"]) + list(value)))
        else:
            out[key] = value
    for option in schema.get("allOf") or []:
        part = _resolve(option, root, depth + 1)
        for key, value in part.items():
            if key == "properties" and isinstance(value, Mapping):
                merged = dict(out.get("properties") or {})
                for name, sub in value.items():
                    merged.setdefault(name, sub)
                out["properties"] = merged
            elif key == "required" and isinstance(value, list):
                out["required"] = list(dict.fromkeys(list(out.get("required") or []) + list(value)))
            else:
                out.setdefault(key, value)
    return out


def _branches(schema: Any, root: Mapping[str, Any], depth: int = 0) -> list[dict[str, Any]]:
    """``schema`` resolved, then every ``anyOf`` / ``oneOf`` option it is composed of (recursively).

    These are the alternatives a payload may satisfy: a field any of them
    declares can reach the endpoint (RESIDUAL-B, 07b r3 blocker).
    """

    resolved = _resolve(schema, root)
    out = [resolved]
    if depth >= _MAX_DEPTH:
        return out
    for keyword in ("anyOf", "oneOf"):
        options = resolved.get(keyword)
        if isinstance(options, list):
            for option in options:
                if isinstance(option, Mapping):
                    out.extend(_branches(option, root, depth + 1))
    return out


def _child(schema: Mapping[str, Any], token: Any, root: Mapping[str, Any]) -> dict[str, Any]:
    resolved = _resolve(schema, root)
    if isinstance(token, str):
        # The property as every branch declares it (the node's own first,
        # then its anyOf / oneOf options; first keyword wins).
        found = [branch["properties"][token] for branch in _branches(resolved, root)
                 if isinstance(branch.get("properties"), Mapping) and token in branch["properties"]]
        if len(found) <= 1:
            return _resolve(found[0] if found else {}, root)
        return _resolve({"allOf": [item for item in found if isinstance(item, Mapping)]}, root)
    prefix = resolved.get("prefixItems")
    if isinstance(prefix, list) and isinstance(token, int) and token < len(prefix):
        return _resolve(prefix[token], root)
    items = resolved.get("items")
    return _resolve(items if isinstance(items, Mapping) else {}, root)


def schema_at(root: Mapping[str, Any], tokens: Sequence[Any]) -> dict[str, Any]:
    """The (resolved) subschema at concrete path ``tokens`` of ``root``."""

    node: dict[str, Any] = _resolve(root, root)
    for token in tokens:
        node = _child(node, token, root)
    return node


def _schema_valid(payload: Any, schema: Mapping[str, Any]) -> bool:
    try:
        from mhs.schema import validate as schema_validate
    except Exception:  # noqa: BLE001 - validator missing: accept (the endpoint will judge)
        return True
    try:
        return not schema_validate(payload, dict(schema))
    except Exception:  # noqa: BLE001 - a schema the validator cannot read is not a reason to fail
        return True


# ---------------------------------------------------------------------------
# limits
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LeafBound:
    """One effective numeric/enumerated bound at a limit path.

    ``array`` is true when the path names an array whose elements carry the
    bound; ``min``/``max`` are scalars or per-element lists.
    """

    path: str
    tokens: tuple[Any, ...]
    array: bool = False
    min: Any = None
    max: Any = None
    allowed: tuple[Any, ...] | None = None
    unit: str | None = None
    #: source label of each bound kind (``class``, ``binding``, ``envelope``,
    #: ``endpoint`` for a bound only the endpoint's published limits state...)
    origins: tuple[tuple[str, str], ...] = ()
    #: fixed length of the array the path names (``None``: not fixed, or not an array)
    length: int | None = None

    def origin(self, kind: str) -> str | None:
        return dict(self.origins).get(kind)

    def at(self, kind: str, index: int | None) -> Any:
        value = self.min if kind == "min" else self.max
        if isinstance(value, (list, tuple)):
            if index is None or index >= len(value):
                return None
            return value[index]
        return value


def _bound_value(bound: Any) -> Any:
    if bound is None:
        return None
    if isinstance(bound, tuple):
        return [item.value if item is not None else None for item in bound]
    return getattr(bound, "value", bound)


def _bound_label(bound: Any) -> str | None:
    items = bound if isinstance(bound, tuple) else (bound,)
    for item in items:
        origin = getattr(item, "origin", None)
        if origin is not None:
            return str(getattr(origin, "label", None) or "")
    return None


def _from_effective(effective: Any) -> list[LeafBound]:
    out: list[LeafBound] = []
    for path, rule in sorted((getattr(effective, "rules", None) or {}).items()):
        if not rule.has_bound:
            continue
        origins = []
        for kind in ("min", "max"):
            label = _bound_label(getattr(rule, kind))
            if label is not None:
                origins.append((kind, label))
        if rule.allowed is not None and rule.allowed_origin is not None:
            origins.append(("allowed", str(rule.allowed_origin.label)))
        out.append(LeafBound(
            path=path, tokens=tuple(rule.tokens), array=bool(rule.field.array),
            min=_bound_value(rule.min), max=_bound_value(rule.max),
            allowed=tuple(rule.allowed) if rule.allowed is not None else None, unit=rule.unit,
            origins=tuple(origins), length=rule.field.length if rule.field.array else None,
        ))
    return out


def _numbers(value: Any) -> list[Any]:
    items = value if isinstance(value, (list, tuple)) else [value]
    return [item if isinstance(item, (int, float)) and not isinstance(item, bool) else None for item in items]


def _wider(declared: LeafBound, published: LeafBound | None) -> list[str]:
    """How the endpoint's published rule is wider than (or drops) the declared one."""

    if published is None:
        return ["dropped"]
    out: list[str] = []
    for kind, looser in (("max", lambda new, old: new > old), ("min", lambda new, old: new < old)):
        old = _numbers(getattr(declared, kind))
        if all(item is None for item in old):
            continue
        new = _numbers(getattr(published, kind))
        if len(new) == 1 and len(old) > 1:
            new = new * len(old)
        if len(old) == 1 and len(new) > 1:
            old = old * len(new)
        if any(o is not None and (n is None or looser(n, o)) for o, n in zip(old, new)):
            out.append(kind)
    if declared.allowed is not None and (published.allowed is None
                                         or any(item not in declared.allowed for item in published.allowed)):
        out.append("allowed")
    return out


def _same_bounds(left: LeafBound, right: LeafBound) -> bool:
    return (_numbers(left.min), _numbers(left.max), left.allowed) == (_numbers(right.min), _numbers(right.max),
                                                                      right.allowed)


def _runtime_plan(manifest: Mapping[str, Any], capability: Mapping[str, Any]) -> Any:
    """The runtime's limit plan of one binding (:func:`mhs._server.limits_plan.compile_binding`).

    The server compiles its plans from ``Device``/``Capability`` objects; this
    hands it the same members read from the published manifest, so the suite
    resolves class, binding and envelope limits (and the schema the paths
    resolve in) with the runtime's own code.  The operator overlay is not in
    the manifest; it comes from the endpoint's published limits.
    """

    from types import SimpleNamespace

    from mhs._server import limits_plan

    safety = manifest.get("safety") if isinstance(manifest.get("safety"), Mapping) else {}
    resources = {
        item.get("resource_id"): SimpleNamespace(kind=item.get("kind"), state_schema=item.get("state_schema"))
        for item in manifest.get("resources") or [] if isinstance(item, Mapping)
    }
    device = SimpleNamespace(
        device_id=str(manifest.get("device_id") or ""), mode=manifest.get("mode"),
        safety=SimpleNamespace(risk_class=str(safety.get("risk_class") or "R0"), envelope=safety.get("envelope")),
        _by_resource=resources, capabilities=(),
    )
    verb = capability.get("verb") if capability.get("verb") in ("read", "write", "invoke") else None
    binding = SimpleNamespace(
        capability_id=str(capability.get("capability_id")), resource=capability.get("resource"),
        verb=verb or "invoke", declared_verb=verb,
        input_schema=capability.get("input_schema"), output_schema=capability.get("output_schema"),
        limits=capability.get("limits"), requires_permit=bool(capability.get("requires_permit")),
    )
    return limits_plan.compile_binding(device, binding, overlay=None, key="mhs-conformance")


def published_limits(published: Any, capability: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """The binding's ``x-mhs-effective-limits`` in a ``devices.get`` manifest (``None`` when absent)."""

    if not isinstance(published, Mapping):
        return None
    for entry in published.get("capabilities") or []:
        if (isinstance(entry, Mapping) and entry.get("capability_id") == capability.get("capability_id")
                and entry.get("resource") == capability.get("resource")):
            effective = entry.get("x-mhs-effective-limits")
            return effective if isinstance(effective, Mapping) else None
    return None


def _endpoint_bounds(schema: Mapping[str, Any], effective: Mapping[str, Any],
                     declared: Sequence[LeafBound]) -> tuple[list[LeafBound], list[str]]:
    """Bounds the endpoint publishes beyond the declared ones, and notes on its published limits."""

    from mhs import limits as _limits

    notes: list[str] = []
    if isinstance(effective.get("error"), Mapping):
        error = effective["error"]
        notes.append(f"the endpoint reports its limits cannot be enforced as declared ({error.get('rule')}: "
                     f"{str(error.get('message') or '')[:200]})")
        return [], notes
    rules = effective.get("limits")
    if not isinstance(rules, Mapping) or not rules:
        rules = {}
    try:
        compiled = _limits.compile_limits(schema, [_limits.LimitSource("endpoint", rules, partial=True)])
    except Exception as exc:  # noqa: BLE001 - unreadable published limits: the declared ones still apply
        notes.append(f"the published x-mhs-effective-limits cannot be read ({type(exc).__name__}: {exc})")
        return [], notes
    endpoint = {bound.path: bound for bound in _from_effective(compiled)}
    by_path = {bound.path: bound for bound in declared}
    extra = [bound for path, bound in sorted(endpoint.items())
             if path not in by_path or not _same_bounds(by_path[path], bound)]
    for path, bound in sorted(by_path.items()):
        wider = _wider(bound, endpoint.get(path))
        if wider:
            notes.append(f"the endpoint publishes {path} wider than its manifest declares ({', '.join(wider)}); "
                         "the declared limit is probed")
    return extra, notes


def _legacy_bounds(schema: Mapping[str, Any], sources: Iterable[tuple[str, Mapping[str, Any]]]) -> list[LeafBound]:
    """Server-style bounds for manifests the strict limit compiler refuses (legacy keys).

    ``sources`` are ``(label, rules)`` pairs; the label of the source that set
    each bound kind is kept in :attr:`LeafBound.origins`.
    """

    from mhs.limits import LimitConfigError, parse_path

    merged: dict[str, dict[str, Any]] = {}
    origins: dict[str, dict[str, str]] = {}
    for label, source in sources:
        for key, rule in (source or {}).items():
            if not isinstance(rule, Mapping):
                continue
            current = merged.setdefault(str(key), {})
            labels = origins.setdefault(str(key), {})
            for kind, pick in (("min", max), ("max", min)):
                value = rule.get(kind)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    narrowed = pick(current[kind], value) if kind in current else value
                    if kind not in current or narrowed != current[kind]:
                        labels[kind] = label
                    current[kind] = narrowed
            allowed = rule.get("allowed")
            if isinstance(allowed, list):
                current["allowed"] = [item for item in allowed if "allowed" not in current
                                      or item in current["allowed"]]
                labels["allowed"] = label
    out: list[LeafBound] = []
    for key, rule in sorted(merged.items()):
        try:
            tokens = parse_path(key)
        except LimitConfigError:
            tokens = (key,)
        leaf = schema_at(schema, [0 if not isinstance(token, str) else token for token in tokens])
        array = _primary_type(leaf) == "array"
        allowed = rule.get("allowed")
        out.append(LeafBound(key, tokens, array, rule.get("min"), rule.get("max"),
                             tuple(allowed) if isinstance(allowed, list) else None,
                             origins=tuple(sorted(origins.get(key, {}).items()))))
    return out


def _matches(rule_tokens: Sequence[Any], concrete: Sequence[Any]) -> bool:
    if len(rule_tokens) != len(concrete):
        return False
    for expected, actual in zip(rule_tokens, concrete):
        if isinstance(expected, str):
            if expected != actual:
                return False
        elif isinstance(expected, int):
            if expected != actual:
                return False
        elif not isinstance(actual, int):  # WILDCARD
            return False
    return True


def bounds_at(bounds: Sequence[LeafBound], concrete: Sequence[Any]) -> tuple[Any, Any, tuple[Any, ...] | None]:
    """``(min, max, allowed)`` that apply to the value at ``concrete`` (intersected)."""

    low = high = None
    allowed: tuple[Any, ...] | None = None
    for bound in bounds:
        index: int | None = None
        if _matches(bound.tokens, concrete):
            if bound.array:
                continue  # the array itself; its elements carry the bound
        elif bound.array and concrete and isinstance(concrete[-1], int) and _matches(bound.tokens, concrete[:-1]):
            index = concrete[-1]
        else:
            continue
        lo, hi = bound.at("min", index), bound.at("max", index)
        if isinstance(lo, (int, float)) and not isinstance(lo, bool):
            low = lo if low is None else max(low, lo)
        if isinstance(hi, (int, float)) and not isinstance(hi, bool):
            high = hi if high is None else min(high, hi)
        if bound.allowed is not None:
            allowed = bound.allowed if allowed is None else tuple(item for item in allowed if item in bound.allowed)
    return low, high, allowed


def _leaves(value: Any, prefix: tuple[Any, ...] = (), depth: int = 0) -> Iterator[tuple[tuple[Any, ...], Any]]:
    if depth > _MAX_DEPTH:
        return
    if isinstance(value, Mapping):
        for key in value:
            yield from _leaves(value[key], prefix + (str(key),), depth + 1)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _leaves(item, prefix + (index,), depth + 1)
    else:
        yield prefix, value


def within_bounds(payload: Any, bounds: Sequence[LeafBound]) -> bool:
    for path, value in _leaves(payload):
        if value is None:
            continue  # absent/nullable leaves are the schema's business
        low, high, allowed = bounds_at(bounds, path)
        if allowed is not None and value not in allowed:
            return False
        if low is None and high is None:
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        if low is not None and value < low:
            return False
        if high is not None and value > high:
            return False
    return True


# ---------------------------------------------------------------------------
# bindings
# ---------------------------------------------------------------------------


@dataclass
class Binding:
    """One capability binding of one device, as the suite uses it."""

    manifest: dict[str, Any]
    capability: dict[str, Any]
    verb: str
    schema: dict[str, Any]
    bounds: list[LeafBound] = field(default_factory=list)
    class_entry: dict[str, Any] | None = None
    extension: bool = False
    deprecated: bool = False
    requires_permit: bool = False
    limits_source: str = "none"
    #: True when the endpoint published effective limits for this binding (``devices.get``).
    published: bool = False
    #: Why the runtime cannot enforce the declared limits (it refuses the binding's commands).
    limits_error: str | None = None
    #: Discrepancies between the declared and the published limits.
    limit_notes: list[str] = field(default_factory=list)
    #: The verb the binding itself declares (manifest ``verb``, or the endpoint's device summary).  For a
    #: catalogued class the runtime uses the catalogue verb (:attr:`verb`); for an extension, this one.
    declared_verb: str | None = None
    #: The schema the runtime resolves the limit paths in (the class input for a catalogued class); the
    #: leaf of a limited field the binding admits without declaring it is built from it (SAFE-014).
    limit_schema: dict[str, Any] = field(default_factory=dict)

    @property
    def capability_id(self) -> str:
        return str(self.capability.get("capability_id"))

    @property
    def device_id(self) -> str:
        return str(self.manifest.get("device_id"))

    @property
    def resource(self) -> str | None:
        resource = self.capability.get("resource")
        return str(resource) if isinstance(resource, str) else None

    @property
    def input_properties(self) -> list[str]:
        return sorted((self.schema.get("properties") or {}).keys())

    @property
    def required_inputs(self) -> list[str]:
        return [str(item) for item in self.schema.get("required") or []]

    def valid(self, payload: Any) -> bool:
        return isinstance(payload, Mapping) and _schema_valid(payload, self.schema) and within_bounds(payload, self.bounds)


def _catalog():
    try:
        from mhs import catalog

        return catalog
    except Exception:  # noqa: BLE001 - catalogue missing: extension semantics only
        return None


def _permit_patterns(manifest: Mapping[str, Any]) -> list[str]:
    return [str(item) for item in ((manifest.get("safety") or {}).get("requires_permit") or [])]


def _pattern_matches(pattern: str, capability_id: str) -> bool:
    import fnmatch

    if pattern.endswith(".*"):
        return capability_id.startswith(pattern[:-1])
    return fnmatch.fnmatchcase(capability_id, pattern)


def bindings_for(manifest: Mapping[str, Any], published: Mapping[str, Any] | None = None) -> list[Binding]:
    """Resolve every capability binding of ``manifest`` (verbs and limits exactly like the runtime).

    ``published`` is the endpoint's ``devices.get`` result for the device; its
    ``x-mhs-effective-limits`` (which include the operator overlay) are
    intersected with the declared limits.
    """

    manifest = dict(manifest)
    catalog = _catalog()
    envelope = ((manifest.get("safety") or {}).get("envelope") or {})
    permit_patterns = _permit_patterns(manifest)
    out: list[Binding] = []
    for capability in manifest.get("capabilities") or []:
        if not isinstance(capability, Mapping):
            continue
        capability = dict(capability)
        capability_id = str(capability.get("capability_id"))
        entry = None
        extension = True
        if catalog is not None and not catalog.is_extension(capability_id):
            entry = catalog.get(capability_id)
            extension = entry is None
        binding_schema = capability.get("input_schema") if isinstance(capability.get("input_schema"), Mapping) else {}
        schema = dict(binding_schema)
        if entry is not None and catalog.is_skeleton(binding_schema):
            schema = copy.deepcopy(dict(entry.get("input_schema") or {}))
        verb = str((entry or {}).get("verb") or capability.get("verb") or "invoke")
        if verb not in ("read", "write", "invoke"):
            verb = "invoke"
        source = "none"
        bounds: list[LeafBound] = []
        limits_error: str | None = None
        notes: list[str] = []
        plan = None
        try:
            plan = _runtime_plan(manifest, capability)
        except Exception as exc:  # noqa: BLE001 - no runtime resolver: legacy server-style bounds
            source = f"legacy ({type(exc).__name__}: {exc})"
        if plan is not None and plan.error is None and plan.limits is not None:
            bounds = _from_effective(plan.limits)
            source = "runtime"
        else:
            if plan is not None:
                limits_error = f"{getattr(plan.error, 'rule', 'limit-invalid')}: {plan.error}"
                source = f"invalid ({limits_error})"
            sources: list[tuple[str, Mapping[str, Any]]] = [("binding", capability.get("limits") or {})]
            if entry is not None:
                sources.append(("class", entry.get("limits") or {}))
            for pattern, rules in envelope.items():
                if _pattern_matches(str(pattern), capability_id) and isinstance(rules, Mapping):
                    sources.append(("envelope", rules))
            bounds = _legacy_bounds(schema, sources)
        effective = published_limits(published, capability)
        if effective is not None:
            limit_schema = plan.limit_schema if plan is not None and plan.limit_schema else schema
            extra, notes = _endpoint_bounds(limit_schema, effective, bounds)
            bounds = bounds + extra
            source += " + published"
        requires_permit = bool(capability.get("requires_permit")) or bool((entry or {}).get("requires_permit")) or any(
            _pattern_matches(pattern, capability_id) for pattern in permit_patterns)
        declared = capability.get("verb")
        out.append(Binding(
            manifest=manifest, capability=capability, verb=verb, schema=schema, bounds=bounds,
            class_entry=dict(entry) if entry is not None else None, extension=extension,
            deprecated=str((entry or {}).get("status")) == "deprecated",
            requires_permit=requires_permit, limits_source=source, published=effective is not None,
            limits_error=limits_error, limit_notes=notes,
            declared_verb=str(declared) if declared in ("read", "write", "invoke") else None,
            limit_schema=dict(plan.limit_schema) if plan is not None and isinstance(plan.limit_schema, Mapping)
            and plan.limit_schema else dict(schema),
        ))
    return out


# ---------------------------------------------------------------------------
# synthesis
# ---------------------------------------------------------------------------


def _numeric(schema: Mapping[str, Any], low: Any, high: Any, *, integer: bool, path: str) -> Any:
    lo = schema.get("minimum")
    hi = schema.get("maximum")
    ex_lo = schema.get("exclusiveMinimum")
    ex_hi = schema.get("exclusiveMaximum")
    candidates_lo = [value for value in (lo, low) if isinstance(value, (int, float)) and not isinstance(value, bool)]
    candidates_hi = [value for value in (hi, high) if isinstance(value, (int, float)) and not isinstance(value, bool)]
    floor = max(candidates_lo) if candidates_lo else None
    ceiling = min(candidates_hi) if candidates_hi else None
    step = 1 if integer else 1e-6
    if isinstance(ex_lo, (int, float)) and not isinstance(ex_lo, bool):
        floor = max(floor, ex_lo + step) if floor is not None else ex_lo + step
    if isinstance(ex_hi, (int, float)) and not isinstance(ex_hi, bool):
        ceiling = min(ceiling, ex_hi - step) if ceiling is not None else ex_hi - step
    if integer:
        floor = math.ceil(floor) if floor is not None else None
        ceiling = math.floor(ceiling) if ceiling is not None else None
    if floor is not None and ceiling is not None and floor > ceiling:
        raise Unsynthesizable(f"{path or 'input'} has an empty valid range ({floor} > {ceiling})")
    preferred = 1 if integer else 1.0
    if (floor is None or floor <= preferred) and (ceiling is None or ceiling >= preferred):
        value: Any = preferred
    elif floor is not None:
        value = floor
    else:
        value = ceiling
    multiple = schema.get("multipleOf")
    if isinstance(multiple, (int, float)) and not isinstance(multiple, bool) and multiple > 0:
        base = floor if floor is not None else value
        value = math.ceil(base / multiple) * multiple
        if ceiling is not None and value > ceiling:
            raise Unsynthesizable(f"{path or 'input'}: no multiple of {multiple} inside its range")
        if integer:
            value = int(value)
    return int(value) if integer else float(value)


def synthesize(schema: Mapping[str, Any], bounds: Sequence[LeafBound] = (), *, root: Mapping[str, Any] | None = None,
               tokens: tuple[Any, ...] = (), depth: int = 0) -> Any:
    """A schema-valid value for ``schema`` that respects ``bounds``; raises :class:`Unsynthesizable`."""

    from mhs.limits import format_path

    root = root if root is not None else schema
    path = format_path(tokens)
    if depth > _MAX_DEPTH:
        raise Unsynthesizable(f"{path or 'input'} nests too deeply to synthesize")
    resolved = _resolve(schema, root)
    low, high, allowed = bounds_at(bounds, tokens)
    for combinator in ("oneOf", "anyOf"):
        options = resolved.get(combinator)
        if isinstance(options, list) and options:
            reasons = []
            for option in options:
                merged = dict(resolved)
                merged.pop(combinator, None)
                merged.update(_resolve(option, root))
                try:
                    return synthesize(merged, bounds, root=root, tokens=tokens, depth=depth + 1)
                except Unsynthesizable as exc:
                    reasons.append(str(exc))
            raise Unsynthesizable("; ".join(reasons[:2]))
    if "const" in resolved:
        return copy.deepcopy(resolved["const"])
    enum = resolved.get("enum")
    if isinstance(enum, list) and enum:
        for item in enum:
            if allowed is None or item in allowed:
                return copy.deepcopy(item)
        raise Unsynthesizable(f"{path or 'input'}: no enum value is inside the allowed set")
    if allowed:
        return copy.deepcopy(allowed[0])
    if "default" in resolved:
        default = copy.deepcopy(resolved["default"])
        if _schema_valid(default, resolved) and within_bounds(_wrap(default, tokens), bounds):
            return default
    kind = _primary_type(resolved)
    if kind == "object":
        properties = resolved.get("properties") or {}
        required = [str(item) for item in resolved.get("required") or []]
        result: dict[str, Any] = {}
        for name in required:
            result[name] = synthesize(properties.get(name) or {}, bounds, root=root, tokens=tokens + (name,),
                                      depth=depth + 1)
        minimum = resolved.get("minProperties")
        if isinstance(minimum, int) and len(result) < minimum:
            for name in sorted(properties):
                if name in result:
                    continue
                try:
                    result[name] = synthesize(properties[name], bounds, root=root, tokens=tokens + (name,),
                                              depth=depth + 1)
                except Unsynthesizable:
                    continue
                if len(result) >= minimum:
                    break
        return result
    if kind == "array":
        prefix = resolved.get("prefixItems") if isinstance(resolved.get("prefixItems"), list) else []
        minimum = resolved.get("minItems")
        count = max(int(minimum) if isinstance(minimum, int) else 1, len(prefix) if resolved.get("items") is False else 0, 1)
        maximum = resolved.get("maxItems")
        if isinstance(maximum, int):
            count = min(count, maximum)
        values = []
        for index in range(count):
            item_schema = prefix[index] if index < len(prefix) else resolved.get("items")
            values.append(synthesize(item_schema if isinstance(item_schema, Mapping) else {}, bounds, root=root,
                                     tokens=tokens + (index,), depth=depth + 1))
        return values
    if kind == "boolean":
        return False
    if kind in ("integer", "number"):
        return _numeric(resolved, low, high, integer=kind == "integer", path=path)
    if kind == "string":
        if resolved.get("pattern") or resolved.get("format"):
            what = "pattern" if resolved.get("pattern") else f"format {resolved.get('format')!r}"
            raise Unsynthesizable(f"{path or 'input'} is a {what}-constrained string; supply a fixture")
        minimum = resolved.get("minLength") if isinstance(resolved.get("minLength"), int) else 0
        maximum = resolved.get("maxLength") if isinstance(resolved.get("maxLength"), int) else None
        text = "mhs"
        if len(text) < minimum:
            text = text + "x" * (minimum - len(text))
        if maximum is not None:
            text = text[:maximum]
        return text
    if kind == "null":
        return None
    return None


def _wrap(value: Any, tokens: Sequence[Any]) -> Any:
    """Embed ``value`` at ``tokens`` so :func:`within_bounds` can address it."""

    for token in reversed(tuple(tokens)):
        if isinstance(token, str):
            value = {token: value}
        else:
            value = [None] * int(token) + [value]
    return value


def _project(example: Mapping[str, Any], schema: Mapping[str, Any]) -> dict[str, Any]:
    properties = schema.get("properties")
    if not isinstance(properties, Mapping) or not properties:
        return copy.deepcopy(dict(example))
    return {key: copy.deepcopy(value) for key, value in example.items() if key in properties}


def _examples(binding: Binding) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for example in (binding.class_entry or {}).get("examples") or []:
        if isinstance(example, Mapping):
            projected = _project(example, binding.schema)
            if binding.valid(projected) and projected not in out:
                out.append(projected)
    return out


def valid_input(binding: Binding, fixtures: Fixtures | None = None) -> tuple[dict[str, Any], str]:
    """``(payload, source)`` for ``binding``: fixture, then class example, then synthesis."""

    fixture = (fixtures or Fixtures()).entry(binding.device_id, binding.capability_id)
    if isinstance(fixture.get("valid"), Mapping):
        return copy.deepcopy(dict(fixture["valid"])), "fixture"
    examples = _examples(binding)
    if examples:
        return examples[0], "class example"
    payload = synthesize(binding.schema, binding.bounds)
    if not isinstance(payload, dict):
        payload = {}
    if not binding.valid(payload):
        raise Unsynthesizable(f"synthesized input for {binding.capability_id} does not validate; supply a fixture")
    return payload, "synthesized"


def served_input(binding: Binding, fixtures: Fixtures | None = None) -> tuple[dict[str, Any], str]:
    """Like :func:`valid_input`, but the input must also validate against the schema the endpoint publishes.

    A compatibility-mode endpoint serves the binding's own ``input_schema``;
    a skeleton one (no properties) can be narrower than the class schema the
    suite synthesizes from, so a class example with optional fields would be
    refused.  Used for the read command of OP-001, whose inputs are optional.
    """

    served = binding.capability.get("input_schema")
    served = dict(served) if isinstance(served, Mapping) and served else None
    candidates: list[tuple[dict[str, Any], str]] = []
    try:
        candidates.append(valid_input(binding, fixtures))
    except Unsynthesizable:
        pass
    if served is not None:
        try:
            payload = synthesize(served, binding.bounds)
        except Unsynthesizable:
            payload = None
        if isinstance(payload, dict):
            candidates.append((payload, "synthesized"))
    for payload, source in candidates:
        if binding.valid(payload) and (served is None or _schema_valid(payload, served)):
            return payload, source
    raise Unsynthesizable(f"no input for {binding.capability_id} validates against its published input_schema")


def _alternates_for_leaf(binding: Binding, tokens: tuple[Any, ...], value: Any, *, strings: bool) -> list[Any]:
    leaf = schema_at(binding.schema, tokens)
    low, high, allowed = bounds_at(binding.bounds, tokens)
    enum = leaf.get("enum") if isinstance(leaf.get("enum"), list) else None
    choices = [item for item in (enum or list(allowed or [])) if item != value and (allowed is None or item in allowed)]
    if choices:
        return choices[:2]
    if isinstance(value, bool):
        return [not value]
    if isinstance(value, (int, float)):
        integer = _primary_type(leaf) == "integer" or (isinstance(value, int) and _primary_type(leaf) != "number")
        lo = max([item for item in (leaf.get("minimum"), low) if isinstance(item, (int, float)) and not isinstance(item, bool)],
                 default=None)
        hi = min([item for item in (leaf.get("maximum"), high) if isinstance(item, (int, float)) and not isinstance(item, bool)],
                 default=None)
        step = 1
        out: list[Any] = []
        for candidate in (value + step, value - step):
            if (lo is None or candidate >= lo) and (hi is None or candidate <= hi):
                out.append(int(candidate) if integer else float(candidate))
        if not out and not integer:
            for edge in (hi, lo):
                if edge is not None and edge != value:
                    out.append(float((value + edge) / 2.0))
        return out
    if strings and isinstance(value, str) and not (leaf.get("pattern") or leaf.get("format")):
        maximum = leaf.get("maxLength") if isinstance(leaf.get("maxLength"), int) else None
        candidate = value + "-alt"
        if maximum is not None:
            candidate = (value[: max(0, maximum - 4)] + "-alt")[:maximum]
        return [candidate] if candidate != value else []
    return []


def _set(payload: Any, tokens: Sequence[Any], value: Any) -> Any:
    copied = copy.deepcopy(payload)
    if not tokens:
        return value
    cursor = copied
    for token in tokens[:-1]:
        cursor = cursor[token]
    cursor[tokens[-1]] = value
    return copied


def alternate_input(binding: Binding, payload: Mapping[str, Any], fixtures: Fixtures | None = None) -> dict[str, Any] | None:
    """A second valid input that differs from ``payload``, or ``None`` when none can be built."""

    fixture = (fixtures or Fixtures()).entry(binding.device_id, binding.capability_id)
    candidate = fixture.get("alternate")
    if isinstance(candidate, Mapping) and dict(candidate) != dict(payload):
        return copy.deepcopy(dict(candidate))
    for example in _examples(binding):
        if example != dict(payload):
            return example
    required = binding.required_inputs
    leaves = sorted(_leaves(dict(payload)),
                    key=lambda item: (0 if item[0] and item[0][0] in required else 1, [str(t) for t in item[0]]))
    for strings in (False, True):
        for tokens, value in leaves:
            for alternate in _alternates_for_leaf(binding, tokens, value, strings=strings):
                changed = _set(dict(payload), tokens, alternate)
                if changed != dict(payload) and binding.valid(changed):
                    return changed
        if strings:
            break
        properties = binding.schema.get("properties") or {}
        for name in sorted(properties):
            if name in payload:
                continue
            try:
                value = synthesize(properties[name], binding.bounds, root=binding.schema, tokens=(name,))
            except Unsynthesizable:
                continue
            changed = dict(copy.deepcopy(dict(payload)))
            changed[name] = value
            if binding.valid(changed):
                return changed
    return None


#: A field name no binding declares: PROTO-027 sends it as the undeclared field, and SAFE-031 presents a
#: permit of an input-free binding with it (:func:`only_empty_input`).
UNDECLARED_FIELD = "__mhs_invalid_field__"
#: One value of every JSON type but an object: a schema that admits any of them has a second valid input
#: (:func:`only_empty_input`; integrator-v3 edit after the Claude Sonnet review of p3-safe031, F4).
_NON_OBJECTS: tuple[Any, ...] = ("", 0, 1.5, True, None, [], [{}])


def only_empty_input(binding: Binding) -> str | None:
    """Why the empty object is the only input ``binding`` admits, or None when that is not shown.

    SAFE-031 binds a permit to the digest of ``{capability_id, resource, input}``.  When the
    binding's input schema admits nothing but ``{}`` (a declared re-enable, CORE-086, or any action
    without inputs), no second valid input exists to present the permit with: another input is
    refused by the structure check (CORE-060 step 7) before the permit check (step 10).  This is
    shown, never assumed, for every schema the suite or the endpoint applies to the input (the one
    the suite synthesizes from, :attr:`Binding.schema`, the binding's declared ``input_schema`` and,
    for a catalogued class, the class input schema, each when it differs; the endpoint serves
    binding ∩ class):

    * an object schema (``type: object``, exactly: a schema without a type, or with a list of
      types, also admits a string, a number, null or a list) without a top-level ``$ref`` that
      declares no ``properties`` and no ``patternProperties`` and closes the object with
      ``additionalProperties: false`` or ``maxProperties: 0``;
    * the SDK's own validator (:func:`mhs.schema.validate`, the one that checks command inputs)
      accepts ``{}`` and refuses ``{UNDECLARED_FIELD: ...}`` and a value of every other JSON type,
      so a keyword the validator ignores never counts.

    The empty object has no leaf, so no limit applies to it.  Anything else (a schema the validator
    cannot evaluate, a top-level ``$ref``, a declared property, an open object) returns None: the
    suite then keeps asking for a fixture with a distinct second input, as before.
    """

    try:
        from mhs.schema import validate as schema_validate
    except Exception:  # noqa: BLE001 - no validator: nothing is shown
        return None
    schemas: list[Any] = [binding.schema]
    for other in (binding.capability.get("input_schema"), (binding.class_entry or {}).get("input_schema")):
        if isinstance(other, Mapping) and other and all(dict(other) != dict(seen) for seen in schemas):
            schemas.append(other)
    keywords: set[str] = set()
    for schema in schemas:
        if not isinstance(schema, Mapping) or "$ref" in schema:
            return None
        if schema.get("type") != "object":
            # Without type "object" (no type, or a list of types) the schema also admits a string, a number,
            # null or a list: each is a second valid input (integrator-v3 edit; Sonnet review of p3-safe031, F4).
            return None
        if schema.get("properties") or schema.get("patternProperties"):
            return None
        closed_by_additional = schema.get("additionalProperties") is False
        maximum = schema.get("maxProperties")
        closed_by_maximum = isinstance(maximum, int) and not isinstance(maximum, bool) and maximum == 0
        if not (closed_by_additional or closed_by_maximum):
            return None
        try:
            if schema_validate({}, dict(schema)):
                return None
            if not schema_validate({UNDECLARED_FIELD: {"not": "allowed"}}, dict(schema)):
                return None
            if any(not schema_validate(value, dict(schema)) for value in _NON_OBJECTS):
                return None
        except Exception:  # noqa: BLE001 - a schema the validator cannot evaluate shows nothing
            return None
        keywords.add("additionalProperties: false" if closed_by_additional else "maxProperties: 0")
    return (f"its input schema admits only the empty object (no declared property, {' and '.join(sorted(keywords))}"
            "): every other input is refused by the structure check (CORE-060 step 7) before the permit check "
            "(step 10), so no second valid input exists to present the permit with")


# ---------------------------------------------------------------------------
# envelope probes (SAFE-014)
# ---------------------------------------------------------------------------


@dataclass
class Probe:
    """One shape-correct out-of-limit input for SAFE-014 (inside the schema range when the schema allows it)."""

    capability_id: str
    device_id: str
    path: str
    kind: str
    bound: Any
    value: Any
    payload: dict[str, Any]
    in_schema: bool
    #: the limit path the probed value belongs to (``joint_positions`` for ``joint_positions[2]``)
    limit_path: str | None = None


def _concrete(tokens: Sequence[Any], array: bool, index: int = 0) -> tuple[Any, ...]:
    out = tuple(0 if not isinstance(token, (str, int)) else token for token in tokens)
    return out + (index,) if array else out


def _ensure(payload: dict[str, Any], schema: Mapping[str, Any], bounds: Sequence[LeafBound],
            tokens: Sequence[Any]) -> dict[str, Any] | None:
    """Make sure ``payload`` has a value at ``tokens`` (synthesising containers); None when impossible.

    An array is grown with copies of its last element where the item schema
    is shared (no ``prefixItems`` entry, no ``uniqueItems``) and the copy is
    within the limits at its new index, so an element the suite could not
    synthesize (a ``pattern`` string from a fixture) still yields a tail.
    """

    result = copy.deepcopy(payload)
    cursor: Any = result
    for depth, token in enumerate(tokens):
        sub = tuple(tokens[: depth + 1])
        if isinstance(token, str):
            if not isinstance(cursor, dict):
                return None
            if token not in cursor:
                try:
                    cursor[token] = synthesize(schema_at(schema, sub), bounds, root=schema, tokens=sub)
                except Unsynthesizable:
                    return None
            cursor = cursor[token]
        else:
            if not isinstance(cursor, list):
                return None
            container = schema_at(schema, sub[:-1])
            prefix = container.get("prefixItems") if isinstance(container.get("prefixItems"), list) else []
            while len(cursor) <= int(token):
                if cursor and len(cursor) >= len(prefix) and container.get("uniqueItems") is not True:
                    candidate = copy.deepcopy(cursor[-1])
                    if within_bounds(_wrap(candidate, sub[:-1] + (len(cursor),)), bounds):
                        cursor.append(candidate)
                        continue
                try:
                    cursor.append(synthesize(schema_at(schema, sub[:-1] + (len(cursor),)), bounds, root=schema,
                                             tokens=sub[:-1] + (len(cursor),)))
                except Unsynthesizable:
                    return None
            cursor = cursor[int(token)]
    return result


def _value_at(payload: Any, tokens: Sequence[Any]) -> Any:
    cursor = payload
    for token in tokens:
        if isinstance(token, str) and isinstance(cursor, Mapping) and token in cursor:
            cursor = cursor[token]
        elif isinstance(token, int) and isinstance(cursor, list) and token < len(cursor):
            cursor = cursor[token]
        else:
            return None
    return cursor


def _per_element(bound: LeafBound) -> bool:
    """True when ``bound`` gives every array element its own ``min``/``max`` (a vector bound, plan 3.5)."""

    return bound.array and any(isinstance(value, (list, tuple)) for value in (bound.min, bound.max))


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _fixed_length(node: Mapping[str, Any]) -> int | None:
    """The fixed length of an array schema (``prefixItems`` with ``items: false``, or ``minItems == maxItems``)."""

    prefix = node.get("prefixItems")
    if isinstance(prefix, list) and node.get("items") is False:
        return len(prefix)
    low, high = _int(node.get("minItems")), _int(node.get("maxItems"))
    return low if low is not None and low == high else None


def _last_index(node: Mapping[str, Any], present: Any) -> int:
    """The last element probed in an array: its fixed length, else at least the second element the schema allows.

    An endpoint that checks only the first element (DRV-02, FIT-ROS-01) is
    caught only by a probe at a later element, so a variable-length array is
    grown to two elements (the rest synthesized inside the limits) when its
    ``maxItems`` allows it.
    """

    fixed = _fixed_length(node)
    if fixed is not None:
        return max(fixed, 1) - 1
    count = max(len(present) if isinstance(present, list) else 0, _int(node.get("minItems")) or 0, 2)
    maximum = _int(node.get("maxItems"))
    if maximum is not None:
        count = min(count, maximum)
    return max(count, 1) - 1


def _ends(last: int) -> list[int]:
    return [0, last] if last > 0 else [0]


def _element_paths(binding: Binding, bound: LeafBound, base: Mapping[str, Any], *,
                   schema: Mapping[str, Any] | None = None) -> list[tuple[tuple[Any, ...], int | None]]:
    """``(concrete path, element index)`` of every element of ``bound`` that SAFE-014 probes.

    Each wildcard of the limit path (``points[*].z``) expands to the first and
    the last element of its array; an array the path names (``joint_positions``)
    contributes every element under a per-element (vector) bound and the first
    and the last one under a scalar bound, and nested arrays below it their
    first and last elements.  The index is the one a per-element bound uses.
    ``schema`` is the schema the array lengths are read from (default: the
    binding's input schema).
    """

    schema = binding.schema if schema is None else schema
    prefixes: list[tuple[Any, ...]] = [()]
    for token in bound.tokens:
        grown: list[tuple[Any, ...]] = []
        for prefix in prefixes:
            if isinstance(token, (str, int)) and not isinstance(token, bool):
                grown.append(prefix + (token,))
                continue
            node = schema_at(schema, prefix)
            grown.extend(prefix + (index,) for index in _ends(_last_index(node, _value_at(base, prefix))))
        prefixes = grown
    if not bound.array:
        return [(prefix, None) for prefix in prefixes]
    out: list[tuple[tuple[Any, ...], int | None]] = []
    for prefix in prefixes:
        lengths = [len(value) for value in (bound.min, bound.max) if isinstance(value, (list, tuple))]
        if _per_element(bound):
            indices = list(range(max(lengths + [int(bound.length or 0)])))
        elif bound.length:
            indices = _ends(int(bound.length) - 1)
        else:
            indices = _ends(_last_index(schema_at(schema, prefix), _value_at(base, prefix)))
        for index in indices:
            concrete = [prefix + (index,)]
            for _depth in range(_MAX_DEPTH):  # an array of arrays: the bound applies to every leaf
                node = schema_at(schema, concrete[0])
                if _primary_type(node) != "array":
                    break
                concrete = [path + (inner,) for path in concrete
                            for inner in _ends(_last_index(node, _value_at(base, path)))]
            out.extend((path, index) for path in concrete)
    return out


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _outside(limit: Any, kind: str, leaf: Mapping[str, Any], *, integer: bool) -> Any:
    """A value just outside ``limit``, inside the schema range when one exists (and on its ``multipleOf`` grid)."""

    sign = 1 if kind == "max" else -1
    multiple = leaf.get("multipleOf")
    if _number(multiple) and multiple > 0:
        steps = math.floor(limit / multiple) if sign > 0 else math.ceil(limit / multiple)
        value: Any = limit
        for offset in range(1, 4):
            value = round((steps + sign * offset) * multiple, 10)
            if sign * (value - limit) > 0:
                break
        return int(round(value)) if integer else float(value)
    value = limit + sign
    if not integer:
        for edge_key in (("maximum", "exclusiveMaximum") if sign > 0 else ("minimum", "exclusiveMinimum")):
            edge = leaf.get(edge_key)
            exclusive = edge_key.startswith("exclusive")
            if _number(edge) and sign * (edge - limit) > 0 and (sign * (value - edge) > 0
                                                                or (exclusive and value == edge)):
                value = (limit + edge) / 2.0
    return int(value) if integer else float(value)


_NOT_ALLOWED = "mhs-conformance-not-allowed"
#: Character classes for same-shape mutations of an allowed string.
_CHARACTER_CLASSES = ("0123456789", "abcdefghijklmnopqrstuvwxyz", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def _string_candidates(allowed: Sequence[Any]) -> Iterator[str]:
    """Strings outside ``allowed`` to try, most generic first, then same-shape mutations of allowed values."""

    yield _NOT_ALLOWED
    for item in [value for value in allowed if isinstance(value, str)][:4]:
        for position in reversed(range(max(len(item) - 32, 0), len(item))):
            for alphabet in _CHARACTER_CLASSES:
                if item[position] in alphabet:
                    for replacement in alphabet:
                        if replacement != item[position]:
                            yield item[:position] + replacement + item[position + 1:]
        yield item + item[-1:]
        if len(item) > 1:
            yield item[:-1]
        yield item[::-1]
    yield from ("x", "z", "0", "X")


def _pattern_accepts(pattern: Any, value: str) -> bool:
    import re

    try:
        return re.search(str(pattern), value) is not None
    except re.error:
        return False


def _allowed_numbers(leaf: Mapping[str, Any], numbers: Sequence[Any], *, integer: bool) -> list[Any]:
    """Numbers outside a numeric allowed set: above it, below it and in a gap between two members.

    A single probe above the set let an endpoint that checks the set as a
    range, or only its upper side, pass (RESIDUAL-B, 07b r3).  The gap value
    is the first ``enum`` member strictly between the allowed extremes that is
    not allowed, else the next value on the ``multipleOf`` grid (or the next
    integer) after a member, else the midpoint of two members.  Only values the
    leaf schema accepts without its ``enum`` / ``const`` (the runtime strips
    those for a limited field, plan 3.5) are kept, so an enforcing endpoint
    answers with its limit check; when none is, the value above the set.
    """

    members = sorted({item for item in numbers if _number(item)})
    multiple = leaf.get("multipleOf")
    grid = _number(multiple) and multiple > 0
    step = multiple if grid else 1
    candidates: list[Any] = [members[-1] + step, members[0] - step]
    enum = [item for item in leaf.get("enum") or [] if _number(item)] if isinstance(leaf.get("enum"), list) else []
    inside = next((item for item in enum if members[0] < item < members[-1] and item not in members), None)
    if inside is None:
        for low, high in zip(members, members[1:]):
            value = low + step if (integer or grid) else (low + high) / 2.0
            if low < value < high and value not in members:
                inside = value
                break
    if inside is not None:
        candidates.append(inside)
    stripped = {key: value for key, value in leaf.items() if key not in ("enum", "const")}
    out: list[Any] = []
    for value in candidates:
        value = int(round(value)) if integer else float(round(value, 10))
        if value in members or value in out:
            continue
        if _schema_valid(value, stripped):
            out.append(value)
    if not out:
        top = members[-1] + step
        out.append(int(round(top)) if integer else float(round(top, 10)))
    return out


def _not_allowed(leaf: Mapping[str, Any], allowed: Sequence[Any], kind_type: str | None) -> tuple[list[Any], str | None]:
    """``(values, None)`` outside ``allowed`` for ``leaf``, or ``([], reason)`` when none can be built.

    ``values`` is empty without a reason when the allowed set admits every
    value of the leaf's type (nothing to enforce).  Never an invented string
    the schema forbids: on a ``pattern`` string a candidate (a same-shape
    mutation of an allowed value) is used only when the pattern and the leaf
    schema accept it; a ``format`` string is never probed (formats are not
    validated, so an invented value proves nothing).  A numeric set gets the
    values of :func:`_allowed_numbers`.
    """

    def outside(value: Any) -> bool:
        return not any(value == item and type(value) is type(item) for item in allowed)

    if kind_type in ("integer", "number") or (kind_type is None and allowed and all(_number(item) for item in allowed)):
        numbers = [item for item in allowed if _number(item)]
        if not numbers:
            return [], "an allowed set without numbers on a numeric field"
        integer = kind_type == "integer" or (kind_type is None and all(isinstance(item, int) for item in numbers))
        return _allowed_numbers(leaf, numbers, integer=integer), None
    if kind_type == "boolean":
        return [value for value in (True, False) if outside(value)][:1], None
    if kind_type == "string" or (kind_type is None and allowed and all(isinstance(item, str) for item in allowed)):
        enum = leaf.get("enum")
        if isinstance(enum, list):
            values = [item for item in enum if outside(item)]
            return [values[0] if values else _NOT_ALLOWED], None
        if leaf.get("format"):
            return [], (f"an allowed set on a format {leaf.get('format')!r} string (never invented); "
                        "supply an out_of_envelope fixture")
        pattern = leaf.get("pattern")
        for candidate in _string_candidates(allowed):
            if outside(candidate) and (pattern is None or _pattern_accepts(pattern, candidate)) \
                    and _schema_valid(candidate, leaf):
                return [candidate], None
        if pattern is None:
            return [_NOT_ALLOWED], None  # outside the schema too; the limit is checked first (plan 3.5)
        return [], ("no value outside the allowed set matches its pattern; supply an out_of_envelope fixture")
    return [], f"an allowed set on a {kind_type or 'untyped'} field"


@dataclass(frozen=True)
class Gap:
    """A side of a limited path's element SAFE-014 could not probe, and why; it keeps the test from passing.

    ``path`` is the concrete element (``points[2].z``) and ``kind`` the side
    (``max``, ``min`` or ``allowed``; None for every side of the element).  A
    fixture refusal covers a gap only when it names that element and its
    refused value is on that side (RESIDUAL-B, 07b r3 major).
    """

    limit_path: str
    path: str
    reason: str
    kind: str | None = None


@dataclass
class ProbePlan:
    """The SAFE-014 probes of one binding and the limited paths it cannot cover."""

    probes: list[Probe]
    #: concrete paths (``f19``, ``joint_positions[7]``) beyond :data:`_MAX_PATH_PROBES`
    unprobed: list[str] = field(default_factory=list)
    #: sides of limited elements without a buildable out-of-limit value (no base input, a pattern
    #: string, a field the binding refuses but still limits...); SAFE-014 cannot pass with them
    gaps: list[Gap] = field(default_factory=list)
    #: class-default limits on fields no valid input of the binding can carry: nothing can be sent
    not_applicable: list[str] = field(default_factory=list)


#: The ``type`` names :mod:`mhs.schema` knows (any other name is a schema error there).
_TYPE_NAMES = frozenset(("object", "array", "string", "number", "integer", "boolean", "null"))
#: How deep :func:`_refused` follows ``$ref`` / combinators / path tokens before it gives up ("not refused").
_MAX_REFUSAL_DEPTH = 4 * _MAX_DEPTH


def _validator_types(schema: Mapping[str, Any]) -> list[str] | None:
    """The ``type`` names of ``schema`` (empty: no ``type``), or None when :mod:`mhs.schema` cannot read them."""

    declared = schema.get("type")
    if declared is None:
        return []
    names = [declared] if isinstance(declared, str) else list(declared) if isinstance(declared, (list, tuple)) else None
    if names is None or any(not isinstance(name, str) or name not in _TYPE_NAMES for name in names):
        return None
    return names


def _refused(schema: Any, tokens: Sequence[Any], root: Mapping[str, Any], *, numeric: bool = False,
             depth: int = 0) -> bool:
    """True only when no instance :mod:`mhs.schema` accepts for ``schema`` carries concrete path ``tokens``.

    With ``numeric``, the value at the path must also be able to be a number.
    Only keywords the validator applies are read, the way it applies them:
    ``additionalProperties: false`` next to the node's own ``properties`` and
    ``patternProperties`` (``re.search``); a ``type`` without ``object`` (a
    property token), without ``array`` (an index) or, at the leaf, without
    ``number`` / ``integer``; ``maxItems``; ``prefixItems`` with ``items:
    false``; the draft-07 ``items: [...]`` with ``additionalItems: false``;
    a local ``$ref``; one ``allOf`` member, or every ``anyOf`` / ``oneOf``
    option, that refuses.  Every subschema a matched property must satisfy
    (its ``properties`` entry and each matching pattern) is followed.
    Keywords that only add constraints (``not``, ``if`` / ``then`` /
    ``else``, ``dependentSchemas``, ``propertyNames``, ``enum`` / ``const``,
    ``unevaluatedProperties``, which the validator ignores) are never a
    reason, and a subschema the validator cannot read (boolean, an unknown
    type name, a bad pattern, an unresolvable ``$ref``) is never refused.
    This keeps "refused" sound; :func:`_reachable` still confirms it by
    validation (RESIDUAL-B verifier blocker: ``unevaluatedProperties`` and a
    string-typed pattern in one ``anyOf`` option were taken as refusals).
    """

    import re

    if not isinstance(schema, Mapping) or depth > _MAX_REFUSAL_DEPTH:
        return False
    tokens = tuple(tokens)

    def deeper(child: Any, rest: tuple[Any, ...]) -> bool:
        return isinstance(child, Mapping) and _refused(child, rest, root, numeric=numeric, depth=depth + 1)

    ref = schema.get("$ref")
    if isinstance(ref, str) and deeper(_local(root, ref), tokens):
        return True
    members = schema.get("allOf")
    if isinstance(members, list) and any(deeper(member, tokens) for member in members):
        return True
    for keyword in ("anyOf", "oneOf"):
        options = schema.get(keyword)
        if isinstance(options, list) and options and all(deeper(option, tokens) for option in options):
            return True
    types = _validator_types(schema)
    if types is None:
        return False
    if not tokens:
        return numeric and bool(types) and not {"number", "integer"} & set(types)
    token, rest = tokens[0], tokens[1:]
    children: list[Any] = []
    if isinstance(token, str):
        if types and "object" not in types:
            return True
        properties, patterns = schema.get("properties"), schema.get("patternProperties")
        if (properties is not None and not isinstance(properties, Mapping)) or (
                patterns is not None and not isinstance(patterns, Mapping)):
            return False
        matched = bool(properties) and token in properties
        if matched:
            children.append(properties[token])
        for pattern, child in (patterns or {}).items():
            try:
                hit = re.search(str(pattern), token) is not None
            except re.error:
                return False  # the validator raises a schema error: unknown
            if hit:
                matched = True
                children.append(child)
        if not matched:
            extra = schema.get("additionalProperties", True)
            if extra is False:
                return True
            children.append(extra)
    elif isinstance(token, int) and not isinstance(token, bool):
        if types and "array" not in types:
            return True
        maximum = _int(schema.get("maxItems"))
        if maximum is not None and token >= maximum:
            return True
        prefix = schema.get("prefixItems")
        if prefix is not None and not isinstance(prefix, list):
            return False
        prefix = prefix or []
        items = schema.get("items")
        if token < len(prefix):
            children.append(prefix[token])
        elif isinstance(items, list):  # draft-07 tuple form, after prefixItems (as the validator reads it)
            offset = token - len(prefix)
            if offset < len(items):
                children.append(items[offset])
            elif schema.get("additionalItems", True) is False:
                return True
            else:
                children.append(schema.get("additionalItems"))
        elif items is False:
            return True
        else:
            children.append(items)
    else:
        return False
    return any(deeper(child, rest) for child in children)


def _reach(root: Mapping[str, Any], tokens: Sequence[Any], *, numeric: bool = False) -> tuple[str, dict[str, Any]]:
    """Whether a payload carrying concrete path ``tokens`` can reach the endpoint through ``root``.

    ``("refused", {})``: :func:`_refused` -- no input the validator accepts
    carries it (a number there, with ``numeric``), also where a branch
    declares it; ``("declared", leaf)``: the schema (or any ``anyOf`` /
    ``oneOf`` branch) declares every field on the path (``leaf`` is the
    declared value schema); ``("admitted", {})``: anything else -- the schema
    accepts the field without declaring it, or cannot be shown to refuse it.
    Before RESIDUAL-B only the top-level ``properties`` counted, so a limit
    on a field declared in a branch, or admitted, was "not applicable" and
    never probed.
    """

    if _refused(root, tokens, root, numeric=numeric):
        return "refused", {}
    node = _resolve(root, root)
    for token in tokens:
        if isinstance(token, str):
            if any(isinstance(branch.get("properties"), Mapping) and token in branch["properties"]
                   for branch in _branches(node, root)):
                node = _child(node, token, root)
                continue
        elif _primary_type(node) == "array":
            node = _child(node, token, root)
            continue
        break
    else:
        return "declared", node
    return "admitted", {}


def _class_only(bound: LeafBound) -> bool:
    labels = {label for _kind, label in bound.origins}
    return bool(labels) and labels <= {"class"}


def _numeric_bound(bound: LeafBound) -> bool:
    return (_number(bound.at("min", 0)) or _number(bound.at("max", 0)) or _number(bound.min)
            or _number(bound.max))


def _inside_values(bound: LeafBound, index: int | None) -> list[Any]:
    """Values inside the limits of ``bound`` at element ``index``.

    The members of its allowed set that its numeric bounds admit, else
    numbers inside the numeric bounds: their ends, integers next to them, the
    midpoint and 0.
    """

    low, high = bound.at("min", index), bound.at("max", index)
    low = low if _number(low) and math.isfinite(low) else None
    high = high if _number(high) and math.isfinite(high) else None

    def inside(value: Any) -> bool:
        if not _number(value):
            return low is None and high is None
        return (low is None or value >= low) and (high is None or value <= high)

    if bound.allowed is not None:
        return [value for value in bound.allowed if inside(value)]
    candidates: list[Any] = [0]
    if low is not None:
        candidates += [low, math.ceil(low)]
    if high is not None:
        candidates += [high, math.floor(high)]
    if low is not None and high is not None:
        candidates += [(low + high) / 2, math.floor((low + high) / 2)]
    return list(dict.fromkeys(value for value in candidates if inside(value)))


def _carriers(binding: Binding, bound: LeafBound, concrete: Sequence[Any], index: int | None,
              base: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Inputs that carry concrete path ``concrete`` with a value inside its limits, built from ``base``.

    The leaf is synthesized from the limit schema (the class input) and from
    the binding's schema, and also set to each of :func:`_inside_values`;
    the rest of ``base`` is kept.
    """

    concrete = tuple(concrete)
    out: list[dict[str, Any]] = []
    for schema in (binding.limit_schema or binding.schema, binding.schema):
        payload = _ensure(dict(base), schema, binding.bounds, concrete)
        if payload is not None and payload not in out:
            out.append(payload)
    for payload in list(out):
        for value in _inside_values(bound, index):
            candidate = _set(payload, concrete, value)
            if candidate not in out:
                out.append(candidate)
    return out


def _carrier(binding: Binding, bound: LeafBound, concrete: Sequence[Any], index: int | None,
             base: Mapping[str, Any]) -> dict[str, Any] | None:
    """The first of :func:`_carriers` that is valid for the binding's input schema, or None.

    Under a numeric bound only an input carrying a number there counts: the
    probes put a number there.
    """

    numeric = _numeric_bound(bound)
    for candidate in _carriers(binding, bound, concrete, index, base):
        if numeric and not _number(_value_at(candidate, concrete)):
            continue
        if _schema_valid(candidate, binding.schema):
            return candidate
    return None


def _reachable(binding: Binding, bound: LeafBound, concrete: Sequence[Any],
               base: Mapping[str, Any] | None = None, index: int | None = None) -> str:
    """:func:`_reach` of ``concrete`` for ``bound``, a refusal confirmed by validation.

    "refused" needs both: :func:`_refused` (the schema, as the validator
    reads it, rejects every input carrying the field -- with a number there
    for a numeric bound) and, given a valid ``base``, no input built from it
    that carries the field inside its limits (:func:`_carriers`) validating
    against the binding's schema.  One that validates makes the field
    ``admitted``: it reaches the endpoint, so its limit is probed
    (RESIDUAL-B verifier blocker).
    """

    status, _leaf = _reach(binding.schema, concrete, numeric=_numeric_bound(bound))
    if status == "refused" and base is not None and _carrier(binding, bound, concrete, index, base) is not None:
        return "admitted"
    return status


def _probe_schema(binding: Binding, reach: str) -> Mapping[str, Any]:
    """The schema a probe is built from: the binding's, or the limit schema for a field the binding only admits."""

    return binding.schema if reach == "declared" else (binding.limit_schema or binding.schema)


def _sides(bound: LeafBound, index: int | None) -> list[str]:
    """The sides of ``bound`` at element ``index`` that SAFE-014 probes."""

    out = [kind for kind in ("max", "min") if _number(bound.at(kind, index))]
    if bound.allowed is not None:
        out.append("allowed")
    return out


#: Gap reason for a field no valid input of the binding can carry (:func:`_reachable`).
_REFUSED = "the binding's input schema rejects every input that carries it"
#: Gap reason for a field the binding admits when no valid input carrying it could be built.
_UNBUILDABLE = "the binding admits the field, but no valid input carrying it inside its limits could be built"
#: Former name of :data:`_REFUSED`.
_UNDECLARED = _REFUSED


def _probes_at(binding: Binding, bound: LeafBound, concrete: tuple[Any, ...], index: int | None,
               base: Mapping[str, Any], reach: str | None = None) -> tuple[list[Probe], list[tuple[str | None, str]]]:
    """The out-of-limit probes of ``bound`` at one element (``max``, ``min``, then ``allowed``).

    The second item lists the sides that could not be probed, with why:
    ``(kind, reason)``, ``kind`` None for every side of the element.  A field
    the binding admits without declaring it is built from the limit schema
    (the class input), the binding's schema or a plain number inside the
    limit (:func:`_carriers`), and the probe is sent only from an input
    carrying it inside its limits that is valid for the binding.  ``reach``
    is :func:`_reachable` of the element when the caller has it.
    """

    from mhs.limits import format_path

    reach = reach or _reachable(binding, bound, concrete, base, index)
    if reach == "refused":
        return [], [(None, _REFUSED)]
    schema = _probe_schema(binding, reach)
    leaf = schema_at(schema, concrete)
    if reach == "declared":
        payload = _ensure(dict(base), schema, binding.bounds, concrete)
        if payload is None:
            return [], [(None, "its container cannot be synthesized inside the limits")]
    else:
        if not _carriers(binding, bound, concrete, index, base):
            return [], [(None, "its container cannot be synthesized inside the limits")]
        payload = _carrier(binding, bound, concrete, index, base)
        if payload is None:
            return [], [(None, _UNBUILDABLE)]
    kind_type = _primary_type(leaf)
    integer = kind_type == "integer"
    path = format_path(concrete)
    out: list[Probe] = []
    missing: list[tuple[str | None, str]] = []
    for kind in ("max", "min"):
        limit = bound.at(kind, index)
        if not _number(limit):
            continue
        value = _outside(limit, kind, leaf, integer=integer)
        candidate = _set(payload, concrete, value)
        out.append(Probe(binding.capability_id, binding.device_id, path, kind, limit,
                         value, candidate, _schema_valid(candidate, binding.schema), bound.path))
    if bound.allowed is not None:
        values, reason = _not_allowed(leaf, bound.allowed, kind_type)
        if reason is not None:
            missing.append(("allowed", reason))
        for value in values:
            candidate = _set(payload, concrete, value)
            out.append(Probe(binding.capability_id, binding.device_id, path, "allowed",
                             list(bound.allowed), value, candidate,
                             _schema_valid(candidate, binding.schema), bound.path))
    return out, missing


def envelope_probe_plan(binding: Binding, base: Mapping[str, Any] | None, *,
                        base_error: str | None = None) -> ProbePlan:
    """Shape-correct inputs just outside each effective bound of ``binding`` (SAFE-014).

    Every limited path is probed: numeric ``min``/``max`` bounds (both sides;
    class defaults, binding limits, the envelope and the endpoint's published
    limits alike) and ``allowed`` sets (a numeric set above, below and between
    its members), at every nested leaf, at the first and the last element of
    every array on the path (``points[*].z``, a scalar bound on
    ``joint_positions``) and at every element of a per-element (vector) bound.
    A field is probed wherever a payload can carry it to the endpoint: the
    binding declares it (in ``properties`` or in any ``anyOf`` / ``oneOf``
    branch) or admits it (no ``additionalProperties: false``; its leaf is then
    built from the limit schema).  The rest of ``base`` stays valid, so the
    only defect of a probe is the one value outside its limit;
    :attr:`Probe.in_schema` says whether the schema alone would also have
    refused it.

    Every probe of an element is sent; elements are taken breadth-first (the
    first element of every limited path, then the next ones) up to
    :data:`_MAX_PATH_PROBES`, and the rest are listed in
    :attr:`ProbePlan.unprobed`.  Each side of an element without a buildable
    out-of-limit value is a :class:`Gap`; so is every side of every element
    when there is no ``base`` (``base_error`` says why).  Only a class-default
    limit on an element no valid input can carry is
    :attr:`ProbePlan.not_applicable` (nothing can be sent for it): the schema,
    read with the validator's own keywords, rejects every input carrying it,
    and -- given a ``base`` -- no input built from ``base`` that carries it
    inside its limits validates (:func:`_reachable`).  The path is listed
    when every element is, else each such element.  A binding or envelope
    limit there is a gap on every side.
    """

    from mhs.limits import format_path

    plan = ProbePlan([])

    def gap(bound: LeafBound, concrete: tuple[Any, ...], index: int | None, reason: str,
            kind: str | None = None) -> None:
        for side in ([kind] if kind else _sides(bound, index)):
            item = Gap(bound.path, format_path(concrete), reason, side)
            if item not in plan.gaps:
                plan.gaps.append(item)

    def not_applicable(path: str) -> None:
        if path not in plan.not_applicable:
            plan.not_applicable.append(path)

    #: (element rank within its path, path order, probes)
    slots: list[tuple[int, int, list[Probe]]] = []
    for order, bound in enumerate(binding.bounds):
        reach = _reachable(binding, bound, _concrete(bound.tokens, bound.array), base, 0 if bound.array else None)
        schema = _probe_schema(binding, reach)
        elements = [(concrete, index, _reachable(binding, bound, concrete, base, index))
                    for concrete, index in _element_paths(binding, bound, base or {}, schema=schema)]
        refused = [concrete for concrete, _index, element_reach in elements if element_reach == "refused"]
        if refused and _class_only(bound):
            if len(refused) == len(elements):
                not_applicable(bound.path)
            else:
                for concrete in refused:
                    not_applicable(format_path(concrete))
        for rank, (concrete, index, element_reach) in enumerate(elements):
            if element_reach == "refused":
                if not _class_only(bound):
                    gap(bound, concrete, index, _REFUSED)
                continue
            if base is None:
                gap(bound, concrete, index, f"no valid base input ({base_error or 'none'})")
                continue
            probes, missing = _probes_at(binding, bound, concrete, index, base, element_reach)
            for kind, reason in missing:
                gap(bound, concrete, index, reason, kind)
            if probes:
                slots.append((rank, order, probes))
    slots.sort(key=lambda slot: (slot[0], slot[1]))
    kept = slots[:_MAX_PATH_PROBES]
    for level in range(max((len(probes) for _rank, _order, probes in kept), default=0)):
        plan.probes.extend(probes[level] for _rank, _order, probes in kept if level < len(probes))
    plan.unprobed = [probes[0].path for _rank, _order, probes in slots[_MAX_PATH_PROBES:]]
    return plan


def violated_sides(binding: Binding, path: Any, value: Any) -> list[str]:
    """The sides (``max``, ``min``, ``allowed``) of the effective limits at concrete ``path`` that ``value`` is outside.

    ``path`` is a concrete path string (``points[0].z``) or its tokens.  A
    fixture refusal covers exactly these sides of exactly this element.
    """

    from mhs.limits import LimitConfigError, parse_path

    if isinstance(path, str):
        try:
            tokens = tuple(parse_path(path))
        except LimitConfigError:
            return []
    else:
        tokens = tuple(path)
    if value is None:
        return []
    low, high, allowed = bounds_at(binding.bounds, tokens)
    out: list[str] = []
    if _number(value):
        if high is not None and value > high:
            out.append("max")
        if low is not None and value < low:
            out.append("min")
    if allowed is not None and value not in allowed:
        out.append("allowed")
    return out


def fixture_sides(binding: Binding, payload: Any, path: str) -> list[str]:
    """:func:`violated_sides` of the value ``payload`` carries at concrete ``path`` (empty when it carries none)."""

    from mhs.limits import LimitConfigError, parse_path

    try:
        tokens = tuple(parse_path(str(path)))
    except LimitConfigError:
        return []
    return violated_sides(binding, tokens, _value_at(payload, tokens))


def base_from_fixture(binding: Binding, payloads: Iterable[Any]) -> dict[str, Any] | None:
    """A valid base input derived from ``out_of_envelope`` fixture inputs, or None.

    Each value outside its effective limit is put back inside it (the value
    the suite would synthesize there, else the nearest bound or the first
    allowed value); the first input that then validates against the binding
    is the base.  SAFE-014 uses it when it cannot build a valid input itself
    (a required ``pattern`` string without a ``valid`` fixture), so the normal
    element and side probes still run from the fields only the driver author
    can supply (RESIDUAL-B, 07b r3 major).
    """

    for payload in payloads:
        if not isinstance(payload, Mapping):
            continue
        candidate: Any = copy.deepcopy(dict(payload))
        for tokens, value in list(_leaves(candidate)):
            if not violated_sides(binding, tokens, value):
                continue
            replacement = _inside(binding, tokens, value)
            if replacement is None:
                candidate = None
                break
            candidate = _set(candidate, tokens, replacement)
        if isinstance(candidate, dict) and binding.valid(candidate):
            return candidate
    return None


def _inside(binding: Binding, tokens: tuple[Any, ...], value: Any) -> Any:
    """A value inside the effective limits at ``tokens`` to replace ``value`` (None when none is known)."""

    try:
        synthesized = synthesize(schema_at(binding.schema, tokens), binding.bounds, root=binding.schema,
                                 tokens=tuple(tokens))
    except Unsynthesizable:
        synthesized = None
    if synthesized is not None and not violated_sides(binding, tokens, synthesized):
        return synthesized
    low, high, allowed = bounds_at(binding.bounds, tokens)
    if allowed:
        return copy.deepcopy(allowed[0])
    if _number(value):
        if high is not None and value > high:
            return high
        if low is not None and value < low:
            return low
    return None


def envelope_probes(binding: Binding, base: Mapping[str, Any]) -> list[Probe]:
    """The probes of :func:`envelope_probe_plan` (elements beyond the budget are dropped)."""

    return envelope_probe_plan(binding, base).probes


def limit_path_of(binding: Binding, path: str) -> str | None:
    """The limit path of ``binding`` whose rule covers concrete ``path`` (``joint_positions[2]`` -> ``joint_positions``)."""

    from mhs.limits import LimitConfigError, parse_path

    try:
        concrete = parse_path(str(path))
    except LimitConfigError:
        return None
    for bound in binding.bounds:
        if bound.path == path:
            return bound.path
    for bound in binding.bounds:
        for length in range(len(concrete), len(bound.tokens) - 1, -1):
            head = concrete[:length]
            if _matches(bound.tokens, head) or (bound.array and head and isinstance(head[-1], int)
                                                and _matches(bound.tokens, head[:-1])):
                return bound.path
    return None

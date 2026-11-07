"""Per-binding limit plans of the endpoint runtime (plan 3.5 / 3.6, WP-04 step 4c).

The server enforces limits with the one engine, :mod:`mhs.limits`.  For each
binding it compiles a :class:`BindingPlan`:

* the **sources** intersected for the binding, exactly as
  :func:`mhs.catalog.compile_manifest_limits` composes them: the class limits
  (partial, provenance ``class_default``), the binding's ``limits``, the device
  envelope (the exact capability id, then every matching ``cap.<class>.*``
  pattern) and the operator overlay ``site-limits.json``
  (``MHSServer(site_limits=...)``; narrow-only, provenance ``operator``);
* the **schema** the paths resolve in: the binding ∩ class schema of a
  catalogued class (:meth:`mhs.catalog.Catalog.resolve_binding`; for
  ``cap.device.configure.v1`` the writable state properties), the inline
  schema of an extension, or the binding's own schema for an uncatalogued id
  (compatibility mode only);
* the **two-pass** validation schemas: the served input schema without the
  bound keywords of limited fields (structure first), and the full schema
  (the remaining schema bounds, evaluated after the limits);
* the numeric leaves no limit covers and the ``operator_required`` bounds no
  overlay filled (``MHS.SAFETY.LIMITS_UNSET``), and the cumulative budgets.

Nothing here talks to a bridge or holds a server lock; the server caches one
plan per binding and recompiles it when what it was compiled from changes.
"""

from __future__ import annotations

import copy
import json
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .. import canonical
from .. import catalog as _catalog
from .. import limits as _limits

__all__ = [
    "BindingPlan",
    "CONFIGURE_CLASS",
    "SERVED",
    "TEST_PROFILE_PREFIX",
    "check_device_targets",
    "compile_binding",
    "cumulative_amounts",
    "device_bindings",
    "fingerprint",
    "load_site_limits",
    "located_error",
    "overlay_device_ids",
    "present_paths",
    "violation_details",
    "violation_message",
]

CONFIGURE_CLASS = _catalog.CONFIGURE_CLASS
#: A ``safety.envelope`` key: a capability id, a ``.*`` pattern, or ``cap.*`` / ``x-cap.*``.
_ENVELOPE_KEY = re.compile(r"^(?:cap|x-cap)\.(?:\*|[a-z0-9_.-]+\.(?:\*|v[0-9]+))$")
_RISKS = ("R0", "R1", "R2", "R3")
#: Envelope keys of the reserved test-profile namespace may name a capability
#: the device binds only under its test profile (the reference conveyor's
#: ``x-cap.mhs-test.delay.v1``): an unbound one is a warning, not a refusal.
TEST_PROFILE_PREFIX = "x-cap.mhs-test."
#: Violations listed in one ENVELOPE_VIOLATION (the first one is the headline).
MAX_VIOLATIONS = 16


@dataclass(frozen=True)
class _Probe:
    """Where a limit path addresses values: its tokens and the schema chain (for defaults)."""

    path: str
    tokens: tuple[Any, ...]
    chain: tuple[Mapping[str, Any], ...]


@dataclass
class BindingPlan:
    """How the runtime checks the inputs of one binding (see the module docstring)."""

    device_id: str
    capability_id: str
    resource: str
    #: :func:`fingerprint` of what the plan was compiled from.
    key: str
    limits: _limits.EffectiveLimits | None = None
    #: The load-time defect, when the binding's limits cannot be enforced as written.
    error: _limits.LimitConfigError | None = None
    #: The schema the limit paths resolve in.
    limit_schema: Mapping[str, Any] = field(default_factory=dict)
    #: Pass 1: the served input schema without the bound keywords of limited fields.
    first_pass_schema: Mapping[str, Any] | None = None
    #: The served input schema (pass 2 when :attr:`two_pass`).  For
    #: ``cap.device.configure.v1`` it is the binding's writable state
    #: properties in every mode (the patch is the input).
    served_schema: Mapping[str, Any] | None = None
    #: True when some rule has a bound: the full schema is then validated again
    #: after the limits (pass 2); otherwise pass 1 already was the full schema.
    two_pass: bool = False
    #: The resolved class contract (None for an uncatalogued id).
    effective: Any = None
    #: Numeric leaves no rule bounds (and no operator_required declares).
    unlimited: tuple[str, ...] = ()
    #: operator_required bounds no overlay filled.
    unset: tuple[str, ...] = ()
    #: Highest of the device risk class and the class floor.
    risk: str = "R0"
    #: The verb the LIMITS_UNSET rule reads (the class verb when catalogued).
    verb: str = "invoke"
    #: True when :attr:`verb` is the catalogue's (a ``cap.*`` class); an
    #: extension's or uncatalogued id's declared verb is not trusted.
    catalogued: bool = False
    #: :func:`device_bindings` of the device when the plan was compiled: a
    #: binding added or removed re-runs the device-level rules.
    bindings: tuple[Any, ...] = ()
    probes: dict[str, _Probe] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        """The effective limits as ``devices.get`` publishes them (``x-mhs-effective-limits``)."""
        if self.error is not None or self.limits is None:
            return {"error": {"rule": getattr(self.error, "rule", "limit-invalid"),
                              "path": getattr(self.error, "path", None), "message": str(self.error)[:500]}}
        out: dict[str, Any] = {"limits": self.limits.to_json()}
        cumulative = []
        for item in self.limits.cumulative:
            entry: dict[str, Any] = {"path": item.path, "per": item.per, "max": item.max.value}
            if item.unit:
                entry["unit"] = item.unit
            if item.max.origin.source:
                entry["source"] = item.max.origin.source
            cumulative.append(entry)
        if cumulative:
            out["cumulative"] = cumulative
        if self.unset:
            out["operator_required"] = list(self.unset)
        if self.unlimited:
            out["unlimited"] = list(self.unlimited)
        if self.limits.narrowed:
            out["narrowed"] = list(self.limits.narrowed)
        return out


def _jsonable(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, sort_keys=True, default=repr, allow_nan=True))
    except (TypeError, ValueError):
        return repr(value)


def fingerprint(device: Any, capability: Any, overlay_digest: str | None) -> str:
    """A digest of everything a binding's plan is compiled from.

    The runtime recompiles a plan when it changes, so a limit narrowed (or
    broken) after start-up is enforced (or refused) on the next command.
    """
    resource = getattr(device, "_by_resource", {}).get(capability.resource)
    material = {
        "device": [id(device), device.device_id, device.mode, str(device.safety.risk_class)],
        "capability": [capability.capability_id, capability.resource, capability.verb,
                       getattr(capability, "declared_verb", None)],
        "input_schema": capability.input_schema,
        "limits": capability.limits,
        "envelope": device.safety.envelope,
        "state_schema": getattr(resource, "state_schema", None),
        "resource_kind": getattr(resource, "kind", None),
        "overlay": overlay_digest,
    }
    try:
        return canonical.digest(material)
    except Exception:  # noqa: BLE001 - a non-JSON manifest still gets a stable key
        return "repr:" + canonical.digest_text(json.dumps(_jsonable(material), sort_keys=True))


def device_bindings(device: Any) -> tuple[Any, ...]:
    """What the device-level rules (:func:`check_device_targets`) read besides each binding's plan.

    The device object and its ``(capability_id, resource)`` bindings; the
    envelope and the overlay are part of every binding's :func:`fingerprint`.
    """
    return (id(device), tuple((str(capability.capability_id), str(capability.resource))
                              for capability in device.capabilities))


def _resolve(device: Any, capability: Any, catalog: Any) -> Any:
    resource = getattr(device, "_by_resource", {}).get(capability.resource)
    try:
        cat = catalog or _catalog.default_catalog()
        return cat.resolve_binding(
            capability.capability_id,
            capability.input_schema,
            capability.output_schema,
            getattr(resource, "kind", None),
            device.mode,
            state_schema=getattr(resource, "state_schema", None),
            binding_limits=capability.limits,
            binding_verb=getattr(capability, "declared_verb", None),
            binding_requires_permit=bool(capability.requires_permit),
        )
    except Exception:  # noqa: BLE001 - uncatalogued / unresolvable: the binding schema is used
        return None


def _risk_max(*risks: Any) -> str:
    best = 0
    for risk in risks:
        if risk in _RISKS:
            best = max(best, _RISKS.index(risk))
    return _RISKS[best]


#: ``served_schema`` default of :func:`compile_binding`: the binding's current input schema.
SERVED = object()


def located_error(device_id: str, capability_id: str | None, error: _limits.LimitConfigError
                  ) -> _limits.LimitConfigError:
    """``error`` with the device (and capability) in its message; ``rule``/``path``/``source`` kept."""
    where = f"device {device_id}" + (f" {capability_id}" if capability_id else "")
    located = _limits.LimitConfigError(f"{where}: {error}", rule=error.rule, path=error.path,
                                       member=error.member)
    located.source = error.source
    located.capability_id = capability_id  # type: ignore[attr-defined]
    return located


def compile_binding(device: Any, capability: Any, *, overlay: Mapping[str, Any] | None,
                    overlay_digest: str | None = None, effective: Any = None,
                    served_schema: Any = SERVED, key: str | None = None,
                    catalog: Any = None) -> BindingPlan:
    """Compile the plan of one binding; a limit defect is stored in :attr:`BindingPlan.error`.

    ``effective`` is the binding's resolved contract when the caller has it;
    otherwise it is resolved here (an uncatalogued ``cap.*`` id resolves to
    None and its own schema is used).  ``served_schema`` is the input schema
    the binding is validated against (default: ``capability.input_schema``;
    strict mode passes the resolved one it is about to serve).
    """
    did = str(device.device_id)
    cid = str(capability.capability_id)
    key = key or fingerprint(device, capability, overlay_digest)
    plan = BindingPlan(did, cid, str(capability.resource), key)
    if effective is None:
        effective = _resolve(device, capability, catalog)
    plan.effective = effective
    if effective is not None and isinstance(effective.input_schema, Mapping):
        schema: Mapping[str, Any] = effective.input_schema
    elif isinstance(capability.input_schema, Mapping):
        schema = capability.input_schema
    else:
        schema = {"type": "object", "properties": {}}
    plan.limit_schema = schema
    catalogued = effective is not None and not getattr(effective, "extension", False)
    plan.risk = _risk_max(str(device.safety.risk_class), effective.risk_floor if catalogued else "R0")
    plan.verb = str(effective.verb if catalogued else capability.verb or "invoke")
    plan.catalogued = catalogued
    sources: list[_limits.LimitSource] = []
    if catalogued and effective.class_limits:
        sources.append(_limits.LimitSource("class", effective.class_limits, partial=True,
                                           default_source="class_default"))
    sources.append(_limits.LimitSource("binding", capability.limits))
    sources.extend(_limits.envelope_sources(device.safety.envelope, cid))
    narrow = _limits.overlay_sources(overlay, did, cid, parameter_paths=cid == CONFIGURE_CLASS,
                                     partial_parameters=True)
    try:
        compiled = _limits.compile_limits(schema, sources, narrow)
    except _limits.LimitConfigError as exc:
        plan.error = exc
        return plan
    except Exception as exc:  # noqa: BLE001 - any defect of the declaration fails closed
        plan.error = _limits.LimitConfigError(f"limits cannot be compiled: {type(exc).__name__}: {exc}")
        return plan
    plan.limits = compiled
    served = capability.input_schema if served_schema is SERVED else served_schema
    if cid == CONFIGURE_CLASS and effective is not None and isinstance(effective.input_schema, Mapping):
        # The configure input is a patch of the writable state properties, in
        # every mode: a compatibility binding's own (or missing) input schema
        # never lets an unknown key through (WP-04 4c verifier p11).
        served = effective.input_schema
    plan.served_schema = served if isinstance(served, Mapping) and served else None
    plan.two_pass = any(rule.has_bound for rule in compiled.rules.values())
    if isinstance(served, Mapping) and served:
        plan.first_pass_schema = _limits.strip_bound_keywords(compiled, served) if plan.two_pass else served
    plan.unset = tuple(compiled.unset)
    try:
        plan.unlimited = tuple(_limits.unlimited_numeric_leaves(compiled))
    except Exception:  # noqa: BLE001 - a schema the walker cannot read: nothing to report
        plan.unlimited = ()
    plan.probes = _probes(schema, compiled, [*plan.unlimited, *(item.path for item in compiled.cumulative)])
    return plan


def _probes(schema: Mapping[str, Any], compiled: _limits.EffectiveLimits, paths: Iterable[str]) -> dict[str, _Probe]:
    out: dict[str, _Probe] = {}
    for path in compiled.unset:
        rule = compiled.rules.get(path)
        if rule is not None:
            out[path] = _Probe(path, tuple(rule.tokens), tuple(rule.field.chain))
    wanted = [path for path in dict.fromkeys(paths) if path not in out]
    if not wanted:
        return out
    try:
        probe = _limits.compile_limits(schema, [_limits.LimitSource(
            "probe", {path: _limits.OPERATOR_REQUIRED for path in wanted}, partial=True)])
    except _limits.LimitConfigError:
        return out
    for path in wanted:
        rule = probe.rules.get(path)
        if rule is not None:
            out[path] = _Probe(path, tuple(rule.tokens), tuple(rule.field.chain))
    return out


def _values(payload: Any, probe: _Probe) -> list[Any]:
    """Every value ``payload`` holds at the probe's path (schema defaults of omitted fields included)."""
    out: list[Any] = []
    tokens, chain = probe.tokens, probe.chain

    def walk(value: Any, index: int, depth: int) -> None:
        if depth > 64:
            return
        if index == len(tokens):
            out.append(value)
            return
        if value is None:
            return
        token = tokens[index]
        if isinstance(token, str):
            if not isinstance(value, Mapping):
                return
            if token in value:
                child = value[token]
            elif index < len(chain) and isinstance(chain[index], Mapping) and "default" in chain[index]:
                child = copy.deepcopy(chain[index]["default"])
            else:
                return
            walk(child, index + 1, depth + 1)
            return
        if not isinstance(value, (list, tuple)):
            return
        if token is _limits.WILDCARD:
            for item in value:
                walk(item, index + 1, depth + 1)
        elif isinstance(token, int) and token < len(value):
            walk(value[token], index + 1, depth + 1)

    walk(payload, 0, 0)
    return out


def present_paths(plan: BindingPlan, payload: Any, paths: Sequence[str]) -> list[str]:
    """The ``paths`` for which ``payload`` carries a value (an empty array or object carries none)."""
    found: list[str] = []
    for path in paths:
        probe = plan.probes.get(path)
        if probe is None:
            continue
        for value in _values(payload, probe):
            if value is None or (isinstance(value, (list, tuple, Mapping)) and not value):
                continue
            found.append(path)
            break
    return found


def cumulative_amounts(plan: BindingPlan, payload: Any) -> list[tuple[_limits.CumulativeRule, float]]:
    """``(budget, amount)`` for every cumulative budget the payload draws on.

    The amount is the sum of the magnitudes of the addressed numeric values: a
    negative value never refunds a budget (travel, time, dose and volume are
    consumed whatever the sign).  Absent fields draw nothing.
    """
    if plan.limits is None:
        return []
    out: list[tuple[_limits.CumulativeRule, float]] = []
    for rule in plan.limits.cumulative:
        probe = plan.probes.get(rule.path)
        if probe is None:
            continue
        values = [value for value in _values(payload, probe)
                  if isinstance(value, (int, float)) and not isinstance(value, bool)]
        if not values:
            continue
        amount = 0.0
        for value in values:
            try:
                magnitude = abs(float(value))
            except (OverflowError, ValueError):
                magnitude = math.inf
            amount += magnitude if math.isfinite(magnitude) else math.inf
        out.append((rule, amount))
    return out


def check_device_targets(device: Any, plans: Mapping[str, BindingPlan], overlay: Mapping[str, Any] | None,
                         *, refuse_unbound: bool = True) -> None:
    """Device-level load-time rules of :func:`mhs.catalog.compile_manifest_limits`.

    Raises :class:`mhs.limits.LimitConfigError` when an envelope key is no
    capability id or pattern (``envelope-key-invalid``); with
    ``refuse_unbound``, when an envelope key matches no bound capability
    (``envelope-unbound``: a typo of the id would drop its limits; keys of the
    reserved ``x-cap.mhs-test.`` namespace are exempt -- strict mode reports
    every unbound key as a finding of its own, so it passes False); when an
    envelope pattern names a path that resolves in none of the bindings it
    matches; or when the overlay names a capability the device does not bind
    or a parameter that is not writable through ``cap.device.configure.v1``.
    """
    envelope = device.safety.envelope if isinstance(device.safety.envelope, Mapping) else {}
    if device.safety.envelope is not None and not isinstance(device.safety.envelope, Mapping):
        raise _limits.LimitConfigError("safety.envelope must map capability ids or patterns to limit maps",
                                       rule="envelope-key-invalid", source="envelope")
    for pattern in envelope:
        # A key that is no capability id or pattern (a field name one level too
        # high, "cap.motion*") would never match a binding: the limit would be
        # silently dropped (device.schema.json capabilityPattern; "cap.*" too).
        if not isinstance(pattern, str) or not _ENVELOPE_KEY.match(pattern):
            raise _limits.LimitConfigError(
                f"safety.envelope key {pattern!r} is not a capability id or pattern "
                "(cap.<class>.vN, x-cap.<owner>.<name>.vN, cap.<class>.* or cap.*)",
                rule="envelope-key-invalid", path=str(pattern), source="envelope")
    bound = {plan.capability_id for plan in plans.values()}
    if refuse_unbound:
        for pattern in envelope:
            if pattern.startswith(TEST_PROFILE_PREFIX):
                continue
            if not any(_limits.pattern_matches(pattern, capability_id) for capability_id in bound):
                raise _limits.LimitConfigError(
                    f"safety.envelope names {pattern!r}, which matches no bound capability "
                    "(a misspelt capability id would silently drop its limits)",
                    rule="envelope-unbound", path=pattern, source="envelope")
    for pattern, rules in envelope.items():
        if not (isinstance(pattern, str) and pattern.endswith(".*")) or not isinstance(rules, Mapping):
            continue
        matching = [plan for plan in plans.values()
                    if _limits.pattern_matches(pattern, plan.capability_id) and plan.limits is not None]
        if not matching:
            continue
        label = f"envelope:{pattern}"
        for path in rules:
            if all((label, path) in plan.limits.skipped for plan in matching):
                raise _limits.LimitConfigError(
                    f"envelope path {path!r} resolves in no capability matching {pattern}",
                    rule="limit-path-resolves", path=path, source=label)
    devices = overlay.get("devices") if isinstance(overlay, Mapping) else None
    entry = devices.get(device.device_id) if isinstance(devices, Mapping) else None
    if not isinstance(entry, Mapping):
        return
    configure = [plan for plan in plans.values() if plan.capability_id == CONFIGURE_CLASS and plan.limits is not None]
    for name in entry:
        if name.startswith(("cap.", "x-cap.")):
            if name not in bound:
                raise _limits.LimitConfigError(f"overlay names {name}, which {device.device_id} does not bind",
                                               rule="overlay-binding-known", path=name, source="overlay")
        elif not any(("overlay", name) not in plan.limits.skipped for plan in configure):
            raise _limits.LimitConfigError(
                f"overlay parameter {name!r} is not a writable parameter of {device.device_id} "
                "(a parameter needs a cap.device.configure.v1 binding)",
                rule="limit-path-resolves", path=name, source="overlay")


def load_site_limits(value: Any) -> tuple[dict[str, Any] | None, str | None]:
    """The operator overlay (``site-limits.json``) and its digest; ``(None, None)`` without one.

    ``value`` is a document or a path to one.  The document must validate
    against ``site-limits.schema.json`` (every rule carries a bound, a stated
    source is ``operator``, nothing is ``operator_required``); otherwise
    :class:`mhs.limits.LimitConfigError` is raised (``site-limits-invalid``),
    so a broken overlay never silently leaves the device unnarrowed.
    """
    if value is None:
        return None, None
    if isinstance(value, (str, os.PathLike)):
        path = Path(value)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise _limits.LimitConfigError(f"cannot read site_limits {path}: {exc}",
                                           rule="site-limits-invalid", source="overlay") from exc
    elif isinstance(value, Mapping):
        document = copy.deepcopy(dict(value))
    else:
        raise TypeError("site_limits must be a site-limits.json document (a mapping) or a path to one")
    if not isinstance(document, dict):
        raise _limits.LimitConfigError("site_limits must be a JSON object", rule="site-limits-invalid",
                                       source="overlay")
    from ..schema import SchemaStore

    try:
        problems = SchemaStore().validate(document, "site-limits.schema.json")
    except Exception as exc:  # noqa: BLE001 - no schema to check against: fail closed
        raise _limits.LimitConfigError(f"site_limits cannot be validated ({type(exc).__name__}: {exc})",
                                       rule="site-limits-invalid", source="overlay") from exc
    if problems:
        raise _limits.LimitConfigError("site_limits is not a valid site-limits.json document: "
                                       + "; ".join(problems[:5]), rule="site-limits-invalid", source="overlay")
    try:
        digest = canonical.digest(document)
    except Exception as exc:  # noqa: BLE001
        raise _limits.LimitConfigError(f"site_limits is not canonical JSON ({exc})", rule="site-limits-invalid",
                                       source="overlay") from exc
    return document, digest


def overlay_device_ids(overlay: Mapping[str, Any] | None) -> list[str]:
    devices = overlay.get("devices") if isinstance(overlay, Mapping) else None
    return sorted(str(key) for key in devices) if isinstance(devices, Mapping) else []


def violation_details(violations: Sequence[_limits.Violation]) -> dict[str, Any]:
    """``MHS.SAFETY.ENVELOPE_VIOLATION`` details: the first violation, plus every one in ``violations``."""
    first = violations[0].to_details()
    out = dict(first)
    out["field"] = first.get("limit_path") or first.get("path")
    out["violations"] = [item.to_details() for item in violations[:MAX_VIOLATIONS]]
    if len(violations) > MAX_VIOLATIONS:
        out["violations_truncated"] = len(violations) - MAX_VIOLATIONS
    return out


def violation_message(violations: Sequence[_limits.Violation]) -> str:
    more = f" (and {len(violations) - 1} more)" if len(violations) > 1 else ""
    return f"{violations[0].message()}{more}"

"""Strict mode of the endpoint runtime (plan 3.6, WP-04 step 4b).

``MHSServer(strict=...)`` and ``Device(strict=...)`` take ``None`` (the 0.9
default), ``False`` or ``True``.  ``None`` and ``False`` are *compatibility
mode*: every finding below is reported as an :class:`MHSStrictWarning` and the
device keeps its current behaviour, except that a declared risk class below
the class floor is raised to the floor.  ``True`` is *strict mode*: findings
marked ``refuse`` make construction fail with :class:`MHSStrictError`, and the
runtime rules of :mod:`mhs.server` that are strict-only apply (catalogue verb
and schemas, class permit flags, output validation, token-bound principals,
approval verifier for hardware R2+, operator-only hardware reset, arming).

:func:`resolve_device` is the single static check of one device.  It resolves
every binding with :func:`mhs.catalog.resolve_binding` (the same resolver the
conformance suite and the registry use) and adds the device-level rules:

* ``unknown-capability`` -- a ``cap.*`` id that is neither catalogued nor an
  extension id (``x-cap.*``, ``cap.x.*``); ``capability-id-invalid`` for an id
  that is not a capability id at all;
* ``schema-drift`` / ``verb-differs`` -- the binding drifts from its class
  (``MHS.INTERNAL.SCHEMA_DRIFT``); a verb is drift only when the binding
  declares one (an undeclared verb is taken from the class in strict mode);
* ``kind-mismatch`` (``MHS.CAPABILITY.KIND_MISMATCH``) and ``class-mode``;
* ``risk-floor`` -- the device's ``risk_class`` is below the highest class
  floor of its bindings (SAFE-007);
* ``achieved-by-unbound``, ``required-for-empty``, ``required-for-unbound``,
  ``interlock-invalid``;
* ``limits-invalid`` (any :class:`mhs.limits.LimitConfigError`: a limit path
  that does not resolve, an unknown rule member, a widening, ...) and
  ``envelope-unbound`` (an envelope entry for no bound capability);
* ``SAFE-045`` -- a hardware or hybrid device at R2 or above needs an
  independent hardware e-stop (``safety.estop.kind`` ``hardware`` or ``both``
  with a ``physical_ref``) or a non-empty ``safe_state.achieved_by``;
* ``fidelity-*`` -- the fidelity contract of a simulated or hybrid device is
  missing or incomplete (05-fidelity §2.1, FID-001/008/010), or a hardware
  device carries one;
* ``constraints-invalid`` -- ``constraints.max_duration_ms`` is not a positive
  integer, ``constraints.long_running`` is not a boolean, or a
  ``long_running`` binding has no execution bound (no ``max_duration_ms`` of
  its own or of its class; plan 3.7); ``resource-undeclared``,
  ``capability-duplicate``.

``class-requires-permit`` is not a refusal: strict mode enforces the class's
``requires_permit`` flag at runtime, compatibility mode only warns.
"""

from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .. import catalog as _catalog
from .. import limits as _limits

__all__ = [
    "DeviceResolution",
    "Finding",
    "MHSStrictError",
    "MHSStrictWarning",
    "PRINCIPAL_KINDS",
    "apply_compat",
    "apply_strict",
    "normalise_token_principal",
    "replace_non_finite",
    "resolve_device",
    "resolve_flag",
    "untrusted_principal",
    "wire_principal",
]

RISK_ORDER = ("R0", "R1", "R2", "R3")
_CAPABILITY_ID_RE = re.compile(r"^(?:cap|x-cap)\.[a-z0-9_.-]+\.v[0-9]+$")

#: Principal kinds an ``auth_tokens`` entry may carry.  ``operator`` is a
#: human with operator authority (the only kind that may reset a hardware
#: e-stop in strict mode); on the wire it is ``kind: "human"`` with
#: ``x-meta.role: "operator"`` because ``defs.schema.json`` has no operator kind.
PRINCIPAL_KINDS = ("human", "agent", "service", "operator")
_WIRE_KINDS = ("human", "agent", "service")
#: Kinds a caller must not grant itself: without a token they are recorded as
#: ``claimed_principal`` and treated as ``agent`` in strict mode.
PRIVILEGED_KINDS = ("human", "operator")
#: ``principal.x-meta`` members only the endpoint writes: whether a bearer
#: token authenticated the principal, its operator role and the identity a
#: caller claimed.  A caller's own values are dropped (never trusted).
RESERVED_X_META = ("authenticated", "role", "claimed_principal")
#: The members of ``defs.schema.json#/$defs/principal``.
_PRINCIPAL_MEMBERS = ("id", "kind", "display_name", "contact", "x-meta")

_MANIFEST = "MHS.ADAPTER.MANIFEST_INVALID"
_FIDELITY = "MHS.FIDELITY.CONTRACT_REQUIRED"
_DRIFT = "MHS.INTERNAL.SCHEMA_DRIFT"


class MHSStrictWarning(RuntimeWarning):
    """A finding that strict mode refuses (or enforces), reported in compatibility mode.

    One warning is emitted per finding when an :class:`mhs.server.MHSServer`
    is built in compatibility mode (``strict=None`` or ``False``), and once
    per capability for a runtime finding (an output that does not match its
    output schema).  Subclass of :class:`RuntimeWarning`.
    """


class MHSStrictError(ValueError):
    """Strict mode refused a device; ``findings`` lists every reason (:class:`Finding`)."""

    def __init__(self, findings: Iterable["Finding"]):
        self.findings: tuple[Finding, ...] = tuple(findings)
        count = len(self.findings)
        lines = "\n  ".join(item.text() for item in self.findings)
        super().__init__(f"strict mode refuses {count} finding{'s' if count != 1 else ''}:\n  {lines}")

    @property
    def codes(self) -> list[str]:
        return sorted({item.code for item in self.findings})

    @property
    def rules(self) -> list[str]:
        return sorted({item.rule for item in self.findings})


@dataclass(frozen=True)
class Finding:
    """One strict-mode finding about a device."""

    rule: str
    code: str
    device_id: str
    message: str
    capability_id: str | None = None
    path: str | None = None
    #: True: strict mode refuses the device.  False: strict mode enforces the
    #: rule at runtime (compatibility mode only warns).
    refuse: bool = True

    def text(self) -> str:
        where = self.device_id
        if self.capability_id:
            where += f" {self.capability_id}"
        if self.path and self.path not in ("verb",):
            where += f" ({self.path})"
        return f"{where}: {self.message} [{self.rule}, {self.code}]"

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"rule": self.rule, "code": self.code, "device_id": self.device_id,
                               "message": self.message, "refuse": self.refuse}
        if self.capability_id:
            out["capability_id"] = self.capability_id
        if self.path:
            out["path"] = self.path
        return out


@dataclass
class DeviceResolution:
    """What :func:`resolve_device` found out about one device."""

    device_id: str
    findings: list[Finding]
    #: (capability id, resource) -> resolved contract (catalogued classes and
    #: extensions); a binding is identified by the pair (plan 3.6 step 3)
    effective: dict[tuple[str, str], Any] = field(default_factory=dict)
    #: highest risk floor of the device's catalogued bindings
    risk_floor: str = "R0"
    declared_risk: str = "R0"

    @property
    def refused(self) -> list[Finding]:
        return [item for item in self.findings if item.refuse]


def resolve_flag(*values: Any) -> bool:
    """True when any of the given ``strict`` flags is ``True`` (strict wins)."""
    return any(value is True for value in values)


def _risk_index(risk: Any) -> int:
    return RISK_ORDER.index(risk) if risk in RISK_ORDER else 0


def _pattern_matches(pattern: str, capability_id: str) -> bool:
    """The interlock/permit pattern rule of :mod:`mhs.server` (exact, ``.*`` or ``*`` suffix)."""
    if pattern == capability_id:
        return True
    if pattern.endswith("*"):
        return capability_id.startswith(pattern[:-1])
    return False


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def resolve_device(device: Any, *, catalog: "_catalog.Catalog | None" = None) -> DeviceResolution:
    """Resolve every binding of ``device`` against the catalogue and check the device rules.

    Never raises for a manifest defect: every defect is a :class:`Finding`.
    ``device`` is an :class:`mhs.server.Device`.
    """
    did = str(device.device_id)
    findings: list[Finding] = []

    def add(rule: str, code: str, message: str, **extra: Any) -> None:
        findings.append(Finding(rule, code, did, message, **extra))

    safety = device.safety
    declared_risk = str(getattr(safety, "risk_class", "R0") or "R0")
    if declared_risk not in RISK_ORDER:
        add("risk-class-invalid", _MANIFEST, f"risk_class {declared_risk!r} is not one of {list(RISK_ORDER)}")
    try:
        cat = catalog or _catalog.default_catalog()
    except _catalog.CatalogError as exc:
        add("catalogue-unavailable", _MANIFEST, f"the capability catalogue cannot be loaded ({exc})")
        return DeviceResolution(did, findings, {}, "R0", declared_risk)

    resources = {resource.resource_id: resource for resource in device.resources}
    bound = [capability.capability_id for capability in device.capabilities]
    effective: dict[tuple[str, str], Any] = {}
    floors: dict[tuple[str, str], str] = {}
    seen: set[tuple[str, str]] = set()
    for capability in device.capabilities:
        cid = capability.capability_id
        if not isinstance(cid, str) or not _CAPABILITY_ID_RE.match(cid):
            add("capability-id-invalid", "MHS.CAPABILITY.UNKNOWN",
                f"{cid!r} is not a capability id (cap.<domain>.<name>.vN or x-cap.<owner>.<name>.vN)")
            continue
        # A binding is (capability_id, resource): one class on two resources
        # (two pipettes, two grippers) is two bindings; the same pair twice
        # could never both be served.
        key = (cid, str(capability.resource))
        if key in seen:
            add("capability-duplicate", _MANIFEST,
                f"the capability is bound to resource {capability.resource!r} more than once; "
                "only one of the bindings could be served", capability_id=cid)
        seen.add(key)
        resource = resources.get(capability.resource)
        if resource is None:
            add("resource-undeclared", _MANIFEST,
                f"binds resource {capability.resource!r}, which the device does not declare "
                f"(resources: {sorted(resources)})", capability_id=cid)
        constraints = capability.constraints if isinstance(capability.constraints, Mapping) else {}
        if "max_duration_ms" in constraints:
            value = constraints.get("max_duration_ms")
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                add("constraints-invalid", _MANIFEST,
                    f"constraints.max_duration_ms must be a positive integer, got {value!r}",
                    capability_id=cid, path="constraints.max_duration_ms")
        if "long_running" in constraints and not isinstance(constraints.get("long_running"), bool):
            add("constraints-invalid", _MANIFEST,
                f"constraints.long_running must be a boolean, got {constraints.get('long_running')!r}",
                capability_id=cid, path="constraints.long_running")
        try:
            resolved = cat.resolve_binding(
                cid,
                capability.input_schema,
                capability.output_schema,
                resource.kind if resource is not None else None,
                device.mode,
                state_schema=resource.state_schema if resource is not None else None,
                binding_limits=capability.limits,
                binding_verb=getattr(capability, "declared_verb", None),
                binding_requires_permit=bool(capability.requires_permit),
            )
        except _catalog.UnknownCapabilityError:
            add("unknown-capability", "MHS.CAPABILITY.UNKNOWN",
                "not in the capability catalogue and not an extension id "
                "(use a catalogued class or x-cap.<owner>.<name>.vN with inline schemas)",
                capability_id=cid)
            continue
        except Exception as exc:  # noqa: BLE001 - CatalogError or a malformed binding: a finding
            add("binding-unresolvable", _MANIFEST, f"{type(exc).__name__}: {exc}", capability_id=cid)
            continue
        effective[key] = resolved
        class_constraints = getattr(resolved, "constraints", None) or {}
        long_running = (constraints.get("long_running") is True if "long_running" in constraints
                        else class_constraints.get("long_running") is True)
        class_bound = class_constraints.get("max_duration_ms")
        if (long_running and "max_duration_ms" not in constraints
                and not (isinstance(class_bound, int) and not isinstance(class_bound, bool) and class_bound > 0)):
            # Plan 3.7: max_duration_ms bounds the execution of long-running
            # work; without one the endpoint falls back to its longest
            # command deadline.
            add("constraints-invalid", _MANIFEST,
                "constraints.long_running needs an execution bound: declare constraints.max_duration_ms "
                "(the class declares none); without it the endpoint bounds the operation by its "
                "maximum command deadline", capability_id=cid, path="constraints.long_running")
        if resolved.extension:
            continue
        floors[key] = resolved.risk_floor
        for drift in resolved.drift:
            if drift.kind == "verb-differs":
                add("verb-differs", _DRIFT, drift.message, capability_id=cid, path="verb")
            else:
                add("schema-drift", _DRIFT, f"{drift.kind}: {drift.message}", capability_id=cid,
                    path=drift.path)
        if not resolved.kind_ok:
            kinds = (cat.get(cid) or {}).get("resource_kinds") or []
            add("kind-mismatch", "MHS.CAPABILITY.KIND_MISMATCH",
                f"resource {capability.resource!r} has kind "
                f"{getattr(resource, 'kind', None)!r}, which the class does not bind "
                f"(resource_kinds: {kinds})", capability_id=cid)
        if not resolved.mode_ok:
            modes = (cat.get(cid) or {}).get("modes") or []
            add("class-mode", _MANIFEST, f"the class is not defined for mode {device.mode!r} (modes: {modes})",
                capability_id=cid)
        if (resolved.requires_permit and not capability.requires_permit
                and not safety.permits_required_for(cid)):
            add("class-requires-permit", "MHS.SAFETY.PERMIT_INVALID",
                "the class requires a permit for every call; strict mode enforces it",
                capability_id=cid, refuse=False)

    floor = _catalog.risk_at_least(*floors.values())
    if _risk_index(floor) > _risk_index(declared_risk):
        raising = sorted({cid for (cid, _resource), value in floors.items() if value == floor})
        add("risk-floor", _MANIFEST,
            f"risk_class {declared_risk} is below the class floor {floor} of {', '.join(raising)} "
            "(SAFE-007: a device's risk is at least the highest risk of its capability classes)")
    effective_risk = RISK_ORDER[max(_risk_index(floor), _risk_index(declared_risk))]

    safe_state = safety.safe_state if isinstance(safety.safe_state, Mapping) else {}
    achieved_by = safe_state.get("achieved_by") or []
    achieved_by = list(achieved_by) if isinstance(achieved_by, (list, tuple)) else []
    for item in achieved_by:
        if str(item) not in bound:
            add("achieved-by-unbound", _MANIFEST,
                f"safe_state.achieved_by names {str(item)!r}, which is not bound on the device; "
                "its e-stop would report MHS.SAFETY.SAFE_STATE_UNREACHED", path="safety.safe_state.achieved_by")

    for index, entry in enumerate(safety.interlocks or []):
        path = f"safety.interlocks[{index}]"
        if not isinstance(entry, Mapping) or not isinstance(entry.get("id"), str) or not entry.get("id"):
            add("interlock-invalid", _MANIFEST, "an interlock needs a string id", path=path)
            continue
        if "required_for" not in entry:
            continue  # a purely informative interlock (device.schema.json)
        required_for = entry.get("required_for")
        if not isinstance(required_for, (list, tuple)) or not required_for:
            add("required-for-empty", _MANIFEST,
                f"interlock {entry['id']!r} has an empty required_for, so it gates nothing; "
                "name the capabilities it gates or omit the member for an informative interlock",
                path=f"{path}.required_for")
            continue
        for pattern in required_for:
            if not isinstance(pattern, str) or not any(_pattern_matches(pattern, cid) for cid in bound):
                add("required-for-unbound", _MANIFEST,
                    f"interlock {entry['id']!r} required_for {pattern!r} matches no bound capability",
                    path=f"{path}.required_for")

    if device.mode in ("hardware", "hybrid") and _risk_index(effective_risk) >= 2:
        estop = safety.estop if isinstance(safety.estop, Mapping) else {}
        physical = estop.get("physical_ref")
        hardware_stop = estop.get("kind") in ("hardware", "both") and isinstance(physical, str) and bool(physical.strip())
        if not hardware_stop and not achieved_by:
            add("SAFE-045", _MANIFEST,
                f"a {device.mode} device at {effective_risk} needs an independent hardware e-stop "
                "(safety.estop.kind 'hardware' or 'both' with physical_ref) or a non-empty "
                "safe_state.achieved_by; a software-only latch is not enough", path="safety.estop")

    findings.extend(_fidelity_findings(device, did))
    findings.extend(_limit_findings(device, did, effective, cat))
    return DeviceResolution(did, findings, effective, floor, declared_risk)


def _fidelity_findings(device: Any, did: str) -> list[Finding]:
    """05-fidelity §2.1: the contract of a simulated or hybrid device (FID-001/008/010)."""
    out: list[Finding] = []

    def add(rule: str, message: str, path: str, code: str = _FIDELITY) -> None:
        out.append(Finding(rule, code, did, message, path=path))

    fidelity = device.fidelity
    if device.mode == "hardware":
        if fidelity:
            add("fidelity-forbidden", "a hardware device must not carry a fidelity contract (FID-001)",
                "fidelity", _MANIFEST)
        return out
    if device.mode not in ("simulated", "hybrid"):
        return out
    if not isinstance(fidelity, Mapping) or not fidelity:
        add("fidelity-required", f"a {device.mode} device needs a fidelity contract (FID-001)", "fidelity")
        return out
    engine = fidelity.get("engine")
    if not isinstance(engine, str) or not engine.strip():
        add("fidelity-incomplete", "fidelity.engine must name the engine or model", "fidelity.engine")
    level = fidelity.get("fidelity_level")
    if level not in ("F0", "F1", "F2", "F3"):
        add("fidelity-incomplete", f"fidelity.fidelity_level must be F0..F3, got {level!r}",
            "fidelity.fidelity_level")
    determinism = fidelity.get("determinism")
    kind = determinism.get("kind") if isinstance(determinism, Mapping) else None
    if kind not in ("exact", "seeded", "statistical", "none"):
        add("fidelity-incomplete", "fidelity.determinism must be an object whose kind is exact, seeded, "
            f"statistical or none (FID-010), got {determinism!r}", "fidelity.determinism")
    elif kind == "seeded" and determinism.get("seed_control") not in ("parameter", "reset_required", "none"):
        add("fidelity-incomplete", "seeded determinism must declare seed_control (FID-008)",
            "fidelity.determinism.seed_control")
    for name in ("timestep_ms", "realtime_factor"):
        value = fidelity.get(name)
        if not _is_number(value) or value < 0:
            add("fidelity-incomplete", f"fidelity.{name} must be a number >= 0, got {value!r}", f"fidelity.{name}")
    if fidelity.get("reset") not in ("full", "partial", "none"):
        add("fidelity-incomplete", f"fidelity.reset must be full, partial or none, got {fidelity.get('reset')!r}",
            "fidelity.reset")
    if not isinstance(fidelity.get("snapshot_restore"), bool):
        add("fidelity-incomplete", "fidelity.snapshot_restore must be a boolean", "fidelity.snapshot_restore")
    gaps = fidelity.get("gaps")
    if gaps is not None and (not isinstance(gaps, list) or not all(isinstance(item, str) for item in gaps)):
        add("fidelity-incomplete", "fidelity.gaps must be an array of strings", "fidelity.gaps")
    if level == "F3":
        validation = fidelity.get("validation")
        if not isinstance(validation, Mapping) or not validation:
            add("fidelity-validation", "an F3 claim needs a fidelity.validation record (§7)",
                "fidelity.validation", "MHS.FIDELITY.VALIDATION_MISSING")
    return out


def _limit_findings(device: Any, did: str, effective: Mapping[tuple[str, str], Any], cat: Any) -> list[Finding]:
    """Compile the device's limits (class, binding, envelope) with :mod:`mhs.limits`."""
    resources = [
        {"resource_id": resource.resource_id, "kind": resource.kind,
         "state_schema": resource.state_schema or {"type": "object"}}
        for resource in device.resources
    ]
    declared = {resource.resource_id for resource in device.resources}
    capabilities = []
    for capability in device.capabilities:
        if (capability.capability_id, str(capability.resource)) not in effective or capability.resource not in declared:
            continue  # already a finding of its own
        capabilities.append({
            "capability_id": capability.capability_id,
            "resource": capability.resource,
            "input_schema": capability.input_schema,
            "output_schema": capability.output_schema,
            "limits": capability.limits,
            "requires_permit": bool(capability.requires_permit),
        })
    envelope = device.safety.envelope if isinstance(device.safety.envelope, Mapping) else {}
    manifest = {"device_id": did, "mode": device.mode, "resources": resources,
                "capabilities": capabilities, "safety": {"envelope": dict(envelope)}}
    try:
        compiled = _catalog.compile_manifest_limits(manifest, None, catalog=cat)
    except _limits.LimitConfigError as exc:
        return [Finding("limits-invalid", _MANIFEST, did, f"{exc} ({exc.rule})", path=exc.path)]
    except Exception as exc:  # noqa: BLE001 - any defect of the declaration is a finding
        return [Finding("limits-invalid", _MANIFEST, did, f"limits cannot be compiled: {exc}")]
    return [
        Finding("envelope-unbound", _MANIFEST, did,
                f"safety.envelope names {pattern!r}, which matches no bound capability",
                path=f"safety.envelope.{pattern}")
        for pattern in compiled.unused_envelope
    ]


def apply_strict(device: Any, resolution: DeviceResolution) -> None:
    """Make the device serve its resolved contract (strict mode).

    The verb of a catalogued class comes from the class; the published and
    enforced schemas are binding ∩ class (a skeleton binding inherits the
    class schema); the class's ``requires_permit`` applies.  Idempotent.
    """
    for capability in device.capabilities:
        resolved = resolution.effective.get((capability.capability_id, str(capability.resource)))
        if resolved is None:
            continue
        if not resolved.extension:
            capability.verb = resolved.verb
        capability.input_schema = copy.deepcopy(resolved.input_schema)
        capability.output_schema = copy.deepcopy(resolved.output_schema)
        capability.requires_permit = bool(capability.requires_permit or resolved.requires_permit)
        capability.publish_verb = True


def apply_compat(device: Any, resolution: DeviceResolution) -> str | None:
    """Compatibility mode: raise a risk class below the class floor; return the new class or None."""
    if _risk_index(resolution.risk_floor) > _risk_index(device.safety.risk_class):
        device.safety.risk_class = resolution.risk_floor
        return resolution.risk_floor
    return None


# ---------------------------------------------------------------------------
# principals
# ---------------------------------------------------------------------------


def normalise_token_principal(principal: Any, *, index: int) -> tuple[dict[str, Any], list[str]]:
    """The principal an ``auth_tokens`` entry stands for, and what had to be fixed.

    A principal is ``{"id": <non-empty string>, "kind": one of PRINCIPAL_KINDS}``
    plus optional ``display_name``/``contact``.  Problems are returned (strict
    mode refuses them; compatibility mode warns and uses ``agent`` /
    ``token-<index>``).
    """
    problems: list[str] = []
    source = dict(principal) if isinstance(principal, Mapping) else {}
    if not isinstance(principal, Mapping):
        problems.append(f"auth_tokens principal #{index} is not an object")
    pid = source.get("id")
    if not isinstance(pid, str) or not pid.strip():
        problems.append(f"auth_tokens principal #{index} has no string id")
        pid = f"token-{index}"
    kind = source.get("kind")
    if kind not in PRINCIPAL_KINDS:
        problems.append(f"auth_tokens principal {pid!r} has kind {kind!r}; expected one of {list(PRINCIPAL_KINDS)}")
        kind = "agent"
    out: dict[str, Any] = {"id": str(pid)[:200], "kind": kind}
    for key in ("display_name", "contact"):
        if isinstance(source.get(key), str):
            out[key] = source[key][:200]
    return out, problems


def wire_principal(principal: Mapping[str, Any], *, x_meta: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """``principal`` as ``defs.schema.json#/$defs/principal`` allows it on receipts.

    ``kind: "operator"`` becomes ``kind: "human"`` with ``x-meta.role:
    "operator"``; ``x_meta`` entries are merged into ``x-meta``.  Other
    members are kept as given (compatibility).
    """
    out = dict(principal)
    meta = dict(out.get("x-meta")) if isinstance(out.get("x-meta"), Mapping) else {}
    if out.get("kind") == "operator":
        out["kind"] = "human"
        meta["role"] = "operator"
    meta.update(dict(x_meta or {}))
    if meta:
        out["x-meta"] = meta
    return out


def untrusted_principal(principal: Mapping[str, Any], *, strict: bool) -> dict[str, Any]:
    """A self-declared principal (no bearer token) as the endpoint may record it.

    The :data:`RESERVED_X_META` members of the caller's ``x-meta`` are dropped
    (and an ``x-meta`` that is not an object), so only the endpoint can state
    ``authenticated``, a ``role`` or a ``claimed_principal``.  Strict mode also
    keeps only the members of ``defs.schema.json#/$defs/principal`` (strings,
    at most 200 characters); compatibility mode keeps the others as given,
    except top-level members named like the reserved ones (a lookalike
    ``authenticated`` beside ``x-meta`` would mislead a careless reader).
    """
    out = {key: value for key, value in principal.items()
           if (key in _PRINCIPAL_MEMBERS if strict else key not in RESERVED_X_META)}
    meta = out.pop("x-meta", None)
    if isinstance(meta, Mapping):
        out["x-meta"] = {key: value for key, value in meta.items() if key not in RESERVED_X_META}
    if strict:
        out["id"] = str(out.get("id"))[:200]
        for key in ("display_name", "contact"):
            if key in out and not isinstance(out[key], str):
                del out[key]
            elif key in out:
                out[key] = out[key][:200]
    return out


def claimed_summary(principal: Mapping[str, Any]) -> dict[str, Any]:
    """The self-declared identity kept for attribution (id and kind, bounded)."""
    out: dict[str, Any] = {"id": str(principal.get("id"))[:200]}
    if isinstance(principal.get("kind"), str):
        out["kind"] = str(principal["kind"])[:32]
    return out


# ---------------------------------------------------------------------------
# outputs
# ---------------------------------------------------------------------------


def replace_non_finite(value: Any, path: str = "", found: list[str] | None = None,
                       _depth: int = 0) -> tuple[Any, list[str]]:
    """``value`` with every NaN / infinity replaced by ``None``, and their JSON Pointers.

    A receipt is canonical JSON (RFC 8259 has no NaN); a bridge that returns
    one would otherwise lose its receipt.  Subtrees deeper than 64 levels are
    kept as they are.
    """
    found = [] if found is None else found
    if isinstance(value, float) and not math.isfinite(value):
        found.append(path or "/")
        return None, found
    if _depth > 64:
        return value, found
    if isinstance(value, Mapping):
        return {key: replace_non_finite(item, f"{path}/{_escape(key)}", found, _depth + 1)[0]
                for key, item in value.items()}, found
    if isinstance(value, list):
        return [replace_non_finite(item, f"{path}/{index}", found, _depth + 1)[0]
                for index, item in enumerate(value)], found
    return value, found


def _escape(key: Any) -> str:
    return str(key).replace("~", "~0").replace("/", "~1")

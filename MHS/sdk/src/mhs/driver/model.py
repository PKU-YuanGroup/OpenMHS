"""The resolved model of one Driver: its parameters, bindings and safety, checked against the catalogue.

:func:`model_for_class` reads the decorated methods and class attributes of a
:class:`mhs.driver.Driver` subclass; the family drivers build the same
:class:`DriverModel` from their configuration (:mod:`mhs.driver.families`).
:func:`finish` resolves every binding with :func:`mhs.catalog.resolve_binding`
(the resolver the runtime, the conformance suite and the registry share): an
unknown class, a method parameter that is not a class field, a required class
field the method does not take, any schema drift, a resource kind the class
does not bind and a missing execution bound are definition problems, raised
together as one :class:`~mhs.driver.spec.DriverDefinitionError`.

Package composition: besides its main resource (``resource_id`` of kind
``device_kind``) a driver may declare ``extra_resources``, further typed
resources of the same device that carry no parameters, only bindings.  An
action names one with ``Action(resource=...)`` / ``@action(..., resource=...)``
and is resolved against that resource's kind.  The device keeps one backend
object, one bridge, one e-stop latch and one lifecycle; each capability id is
still bound once.

The model is pure data plus the runtime tables the driver needs (which method
serves which capability, the single output field a scalar return is wrapped
into, unit conversions).  It never imports the server.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .. import catalog as _catalog
from .. import limits as _limits
from .. import units as _units
from .decorators import (
    ROLE_ATTR,
    ActionRole,
    EstopRole,
    InterlockRole,
    ParamRole,
    ResetRole,
    Signature,
    signature_of,
)
from .spec import Action, DriverDefinitionError, Fact, Field, Limit
from .source_selector import parse_pybind_selector, parse_selector

__all__ = [
    "BindingModel",
    "DriverModel",
    "EMPTY_STATE_SCHEMA",
    "MAX_EXTRA_RESOURCES",
    "ResourceModel",
    "EstopModel",
    "InterlockModel",
    "ParamModel",
    "binding_from_action",
    "check_class_attributes",
    "finish",
    "model_for_class",
]

CONFIGURE = _catalog.CONFIGURE_CLASS
MOTION_ESTOP = "cap.motion.estop.v1"
#: Capability classes that stop motion; the runtime exempts them from the latch (never locked here either).
STOP_CLASSES = frozenset({"cap.motion.stop.v1", MOTION_ESTOP})
#: Output members the runtime supplies: the server adds ``revision``; the driver stamps ``sampled_at``.
SERVER_OUTPUTS = frozenset({"revision"})
STAMPED_OUTPUTS = frozenset({"sampled_at"})
RISKS = ("R0", "R1", "R2", "R3")
DRIVER_MODES = ("hardware", "simulated")
#: The backend names a driver may declare and be loaded with (the ``mhs serve --backend`` set).  Only
#: ``hardware`` reaches a device; every other name is served as mode ``simulated``.
BACKENDS = ("hardware", "fake", "sim")
FAKE_BACKENDS = ("fake", "sim")
#: Relative module of the hardware entry point (templates: ``".native:connect"``); never a fake backend.
HARDWARE_MODULE = ".native"
_SHORT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*(/[A-Za-z0-9][A-Za-z0-9_.-]*)*$")
_DEVICE_ID = re.compile(r"^mhs://[^\s/]+(/[^\s]+)+$")
_KIND = re.compile(r"^[a-z][a-z0-9_.]*$")
_RESOURCE_ID = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_TAG = re.compile(r"^[a-z0-9][a-z0-9 -]{0,79}$")
_NATIVE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_.]*$")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
#: Package composition is bounded: at most this many resources besides the main one.
MAX_EXTRA_RESOURCES = 7
#: The state schema of a resource without parameters (an extra resource, or a main resource with none).
EMPTY_STATE_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}


@dataclass
class ParamModel:
    """One named parameter of the resource (a ``state_schema`` property)."""

    name: str
    field: Field
    getter: str | None = None
    setter: str | None = None
    getter_signature: Signature | None = None
    setter_signature: Signature | None = None
    risk: str | None = None
    #: config-only families: written through the inner bridge
    writable: bool = False

    @property
    def is_writable(self) -> bool:
        return self.setter is not None or self.writable

    def schema(self) -> dict[str, Any]:
        out = self.field.to_schema(what=self.name)
        if not self.is_writable:
            out["readOnly"] = True
        return out


@dataclass
class BindingModel:
    """One capability binding of the device (manifest ``capabilities[]`` entry plus runtime data)."""

    capability_id: str
    name: str
    attr: str | None = None
    signature: Signature | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    limits: dict[str, Any] = field(default_factory=dict)
    #: limit paths a simulator family derived from its backend (an action space, a ctrlrange), not driver Limits
    derived_limits: tuple[str, ...] = ()
    operator_reasons: dict[str, str] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    title: str | None = None
    exclusive: bool | None = None
    requires_permit: bool = False
    verb: str | None = None
    determinism: str | None = None
    native: str | None = None
    schema_digest: str | None = None
    examples: list[dict[str, Any]] = field(default_factory=list)
    safe_state: bool = False
    risk: str | None = None
    #: the device's explicit re-enable after a safety reset (``safety.estop.reenable``, CORE-086)
    reenable: bool = False
    #: top-level input fields converted before the native call: name -> (unit, native unit, delta)
    native_units: dict[str, tuple[str, str, bool]] = field(default_factory=dict)
    #: filled by :func:`finish`
    effective: Any = None
    principal_output: str | None = None
    stamps_sampled_at: bool = False
    takes_lock: bool = True
    simulation_timing: dict[str, Any] | None = None
    #: the declared resource (``Action(resource=...)``); ``None`` is the driver's main resource
    resource: str | None = None

    @property
    def extension(self) -> bool:
        return _catalog.is_extension(self.capability_id)

    def manifest(self, resource_id: str) -> dict[str, Any]:
        out: dict[str, Any] = {"capability_id": self.capability_id, "resource": resource_id}
        if self.title:
            out["title"] = self.title
        if self.verb is not None and self.extension:
            out["verb"] = self.verb
        if self.input_schema is not None:
            out["input_schema"] = copy.deepcopy(self.input_schema)
        if self.output_schema is not None:
            out["output_schema"] = copy.deepcopy(self.output_schema)
        if self.constraints:
            out["constraints"] = copy.deepcopy(self.constraints)
        if self.limits:
            out["limits"] = copy.deepcopy(self.limits)
        if self.determinism:
            out["determinism"] = self.determinism
        if self.exclusive:
            out["exclusive"] = True
        if self.requires_permit:
            out["requires_permit"] = True
        if self.native:
            out["native"] = self.native
        if self.capability_id != CONFIGURE:
            out["x-mhs-name"] = self.name
        if self.schema_digest:
            out["x-mhs-schema-digest"] = self.schema_digest
        if self.simulation_timing is not None:
            out["x-vendor"] = {"openmhs_simulation_timing": copy.deepcopy(self.simulation_timing)}
        return out


@dataclass
class EstopModel:
    attr: str | None
    native: str | None
    latency_ms: int | None = None
    wants_reason: bool = False


@dataclass
class InterlockModel:
    attr: str | None
    id: str
    description: str | None = None
    blocks: tuple[str, ...] | None = None
    source: str = "hardware"
    reset_exempt: bool = False

    def manifest(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.id}
        if self.description:
            out["description"] = self.description
        if self.blocks is not None:
            out["required_for"] = list(self.blocks)
        out["source"] = self.source
        if self.reset_exempt:
            out["reset_exempt"] = True
        return out


@dataclass
class ResourceModel:
    """One further typed resource of a composed driver (``extra_resources``): bindings only, no parameters."""

    resource_id: str
    kind: str
    title: str | None = None

    def manifest(self) -> dict[str, Any]:
        out: dict[str, Any] = {"resource_id": self.resource_id, "kind": self.kind,
                               "state_schema": copy.deepcopy(EMPTY_STATE_SCHEMA)}
        if self.title:
            out["title"] = self.title
        return out


@dataclass
class DriverModel:
    """Everything needed to build a manifest, a Device and a reference file for one driver."""

    driver: str
    device_id: str
    device_kind: str
    resource_id: str
    mode: str
    declared_risk: str
    params: list[ParamModel] = field(default_factory=list)
    bindings: list[BindingModel] = field(default_factory=list)
    estop: EstopModel | None = None
    interlocks: list[InterlockModel] = field(default_factory=list)
    reset_attr: str | None = None
    safe_state: str | None = None
    estop_physical_ref: str | None = None
    estop_latency_ms: int | None = None
    #: why the native stop cannot be undone without a new endpoint (``safety.estop.terminal``, CORE-087)
    estop_terminal: str | None = None
    #: the sensed confirmation of a simulated device's request stop (``safety.estop.confirmation``, SAFE-049)
    estop_confirmation: dict[str, Any] | None = None
    watchdog_ms: int | None = None
    fidelity: dict[str, Any] | None = None
    display_name: str | None = None
    vendor: str | None = None
    model: str | None = None
    tags: tuple[str, ...] = ()
    operating_notes: tuple[str, ...] = ()
    facts: tuple[Fact, ...] = ()
    native_symbol: str | None = None
    upstream: dict[str, str] | None = None
    resource_title: str | None = None
    models: tuple[str, ...] = ()
    #: further typed resources of a composed package (``extra_resources``), in declaration order
    extra_resources: list[ResourceModel] = field(default_factory=list)
    #: E3: the bridges the operator must run (RosDriver ``operator_bridges``, validated), ``({args, ref,
    #: description?}, ...)``; listed in the reference file, never started by the package
    operator_bridges: tuple[dict[str, str], ...] = ()
    #: filled by :func:`finish`
    risk_floor: str = "R0"
    risk: str = "R0"
    problems: list[str] = field(default_factory=list)

    # -- lookups -----------------------------------------------------------
    def binding(self, capability_id: str) -> BindingModel | None:
        for item in self.bindings:
            if item.capability_id == capability_id:
                return item
        return None

    def param(self, name: str) -> ParamModel | None:
        for item in self.params:
            if item.name == name:
                return item
        return None

    def extra_resource(self, resource_id: Any) -> ResourceModel | None:
        """The declared extra resource ``resource_id`` (``None`` for the main resource or an unknown id)."""
        for item in self.extra_resources:
            if item.resource_id == resource_id:
                return item
        return None

    def resource_of(self, binding: BindingModel) -> str:
        """The resource a binding is served on: its declared resource, or the main resource."""
        return binding.resource or self.resource_id

    def resource_kind(self, resource_id: Any) -> str | None:
        """The kind of the main or an extra resource (``None``: the driver declares no such resource)."""
        if resource_id == self.resource_id:
            return self.device_kind
        extra = self.extra_resource(resource_id)
        return extra.kind if extra is not None else None

    @property
    def writable(self) -> list[ParamModel]:
        return [item for item in self.params if item.is_writable]

    @property
    def achieved_by(self) -> list[str]:
        return [item.capability_id for item in self.bindings if item.safe_state]

    @property
    def reenable(self) -> str | None:
        """The capability declared ``reenable=True`` (``safety.estop.reenable``), or ``None``."""
        return next((item.capability_id for item in self.bindings if item.reenable), None)

    @property
    def operator_reasons(self) -> dict[tuple[str, str], str]:
        """``(capability id, limit path) -> reason`` of every ``Limit.operator_required``."""
        out: dict[tuple[str, str], str] = {}
        for binding in self.bindings:
            for path, reason in binding.operator_reasons.items():
                out[(binding.capability_id, path)] = reason
        return out

    # -- manifest pieces ---------------------------------------------------
    def state_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {item.name: item.schema() for item in self.params},
                "additionalProperties": False}

    def resource_manifest(self) -> dict[str, Any]:
        out: dict[str, Any] = {"resource_id": self.resource_id, "kind": self.device_kind,
                               "state_schema": self.state_schema()}
        if self.resource_title:
            out["title"] = self.resource_title
        return out

    def resources_manifest(self) -> list[dict[str, Any]]:
        """The main resource followed by every extra resource (a one-element list without extras)."""
        return [self.resource_manifest()] + [item.manifest() for item in self.extra_resources]

    def estop_manifest(self) -> dict[str, Any]:
        out: dict[str, Any] = {"kind": "both" if self.estop_physical_ref else "software", "latching": True}
        out["native"] = self.estop.native if self.estop is not None else None
        latency = self.estop_latency_ms
        if self.estop is not None and self.estop.latency_ms is not None:
            latency = self.estop.latency_ms
        if latency is not None:
            out["latency_ms"] = latency
        if self.estop_physical_ref:
            out["physical_ref"] = self.estop_physical_ref
        # Only declared recovery contracts are published: a manifest without them is unchanged.
        if self.reenable is not None:
            out["reenable"] = self.reenable
        if self.estop_terminal is not None:
            out["terminal"] = self.estop_terminal
        if self.estop_confirmation is not None:
            out["confirmation"] = copy.deepcopy(self.estop_confirmation)
        return out

    def safety_manifest(self) -> dict[str, Any]:
        return {
            "risk_class": self.risk,
            "interlocks": [item.manifest() for item in self.interlocks],
            "estop": self.estop_manifest(),
            "safe_state": {"description": self.safe_state or "no declared safe state",
                           "achieved_by": self.achieved_by},
        }


# ---------------------------------------------------------------------------
# class attributes
# ---------------------------------------------------------------------------


def _attr(cls: type, name: str, default: Any = None) -> Any:
    return getattr(cls, name, default)


def check_class_attributes(cls: type, problems: list[str], *, native_symbol: Any, safe_state: Any,
                           require_mode: Sequence[str] = DRIVER_MODES) -> dict[str, Any]:
    """Validate the declarative class attributes shared by every driver; return them normalised."""
    out: dict[str, Any] = {}
    device_id = _attr(cls, "device_id")
    if not isinstance(device_id, str) or not device_id:
        problems.append("device_id must be set (a short name such as 'bath', or an mhs:// device id)")
        device_id = "unnamed"
    elif device_id.startswith("mhs://"):
        if not _DEVICE_ID.match(device_id):
            problems.append(f"device_id {device_id!r} is not an mhs://host/path device id")
    elif not _SHORT_ID.match(device_id):
        problems.append(f"device_id {device_id!r} must be letters, digits, '_', '.', '-' and '/' (no spaces)")
    out["device_id"] = device_id
    kind = _attr(cls, "device_kind")
    if not isinstance(kind, str) or not _KIND.match(kind):
        problems.append(f"device_kind must be a resource kind such as 'thermal.zone' (python3 -m mhs.driver "
                        f"catalog show <cap id> lists the kinds of a class), got {kind!r}")
        kind = "device"
    out["device_kind"] = kind
    resource_id = _attr(cls, "resource_id", "main")
    if not isinstance(resource_id, str) or not _RESOURCE_ID.match(resource_id):
        problems.append(f"resource_id must match [a-z0-9][a-z0-9_.-]*, got {resource_id!r}")
        resource_id = "main"
    out["resource_id"] = resource_id
    out["extra_resources"] = _extra_resources(_attr(cls, "extra_resources"), resource_id, problems)
    mode = _attr(cls, "mode", "hardware")
    if mode not in require_mode:
        problems.append(f"mode must be one of {list(require_mode)}, got {mode!r}")
        mode = "hardware"
    out["mode"] = mode
    risk = _attr(cls, "risk", "R0")
    if risk not in RISKS:
        problems.append(f"risk must be one of {list(RISKS)}, got {risk!r}")
        risk = "R0"
    out["risk"] = risk
    tags = _attr(cls, "tags", ()) or ()
    if isinstance(tags, str) or not all(isinstance(tag, str) and _TAG.match(tag) for tag in tags):
        problems.append(f"tags must be short lowercase keywords ([a-z0-9][a-z0-9 -]*), got {tags!r}")
        tags = ()
    out["tags"] = tuple(dict.fromkeys(tags))
    facts = _attr(cls, "facts", ()) or ()
    if isinstance(facts, (str, Fact)) or not all(isinstance(item, Fact) for item in facts):
        problems.append("facts must be a list of Fact(text, source=..., ref=...) objects")
        facts = ()
    out["facts"] = tuple(facts)
    if safe_state is not None and (not isinstance(safe_state, str) or not safe_state.strip() or len(safe_state) > 500):
        problems.append(f"safe_state must describe the safe state in one sentence (at most 500 characters), "
                        f"got {safe_state!r}")
        safe_state = None
    out["safe_state"] = safe_state
    if (native_symbol is not None and parse_selector(native_symbol) is None
            and parse_pybind_selector(native_symbol) is None):
        problems.append(f"native must be 'package.module:Class', 'pyfile:path.py#Class', 'pyfile:path.py#*' or "
                        f"'pybind:path.cpp#scope.Class', got {native_symbol!r}")
        native_symbol = None
    out["native_symbol"] = native_symbol
    for name, limit in (("estop_physical_ref", 500), ("estop_terminal", 500), ("display_name", 200),
                        ("vendor", 200), ("model", 200)):
        value = _attr(cls, name)
        if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > limit):
            problems.append(f"{name} must be a non-empty string of at most {limit} characters, got {value!r}")
            value = None
        out[name] = value
    for name in ("watchdog_ms", "estop_latency_ms"):
        value = _attr(cls, name)
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < (1 if name == "watchdog_ms" else 0)):
            problems.append(f"{name} must be a {'positive' if name == 'watchdog_ms' else 'non-negative'} integer, "
                            f"got {value!r}")
            value = None
        out[name] = value
    backends = _attr(cls, "backends", {}) or {}
    if not isinstance(backends, Mapping):
        problems.append("backends must map backend names (hardware, fake, ...) to 'module:attr' entry points")
        backends = {}
    for key, value in backends.items():
        if key not in BACKENDS:
            problems.append(f"backend name {key!r} is not one of {list(BACKENDS)}: only 'hardware' drives the "
                            "device, 'fake' and 'sim' are served as mode simulated")
        if not (isinstance(value, str) and value) and not callable(value):
            problems.append(f"backends[{key!r}] must be a 'module:attr' string (relative '.fake:Fake' allowed) "
                            "or a callable")
    if mode == "simulated" and "hardware" in backends:
        problems.append("a simulated driver has no hardware backend; remove backends['hardware']")
    hardware_entry = backends.get("hardware")
    for key in FAKE_BACKENDS:
        value = backends.get(key)
        if value is None:
            continue
        if hardware_entry is not None and (value is hardware_entry or value == hardware_entry):
            problems.append(f"backends[{key!r}] is the hardware entry point {hardware_entry!r}: a {key} backend is "
                            "served as mode simulated, so it must never open the device")
        elif isinstance(value, str) and value.partition(":")[0] == HARDWARE_MODULE:
            problems.append(f"backends[{key!r}] = {value!r} uses {HARDWARE_MODULE}, the hardware backend module; a "
                            f"{key} backend is served as mode simulated (use '.fake:Fake...')")
    out["backends"] = dict(backends)
    watchdog = out.get("watchdog_ms")
    if watchdog is not None and not any(
            "watchdog" in fact.text.lower() and fact.source in ("vendor_doc", "upstream_code", "operator")
            for fact in out["facts"]):
        problems.append(f"watchdog_ms = {watchdog} declares a device-side watchdog, which the OpenMHS runtime does "
                        "not implement: cite it with a Fact('... watchdog ...', source='vendor_doc' or "
                        "'upstream_code', ref='path:LINE') or remove watchdog_ms")
    fidelity = _attr(cls, "fidelity")
    if fidelity is not None and not isinstance(fidelity, Mapping):
        problems.append("fidelity must be a fidelity contract object (engine, fidelity_level, determinism, ...)")
        fidelity = None
    out["fidelity"] = copy.deepcopy(dict(fidelity)) if fidelity is not None else None
    upstream = _attr(cls, "upstream")
    if upstream is not None and not (isinstance(upstream, Mapping) and isinstance(upstream.get("repo"), str)
                                     and upstream.get("repo") and isinstance(upstream.get("commit"), str)
                                     and re.match(r"^[0-9a-f]{40}$", upstream["commit"])):
        problems.append("upstream must be {'repo': <url>, 'commit': <40-hex sha>}")
        upstream = None
    out["upstream"] = dict(upstream) if upstream is not None else None
    models = _attr(cls, "models", ()) or ()
    if isinstance(models, str) or not all(isinstance(item, str) and _DEVICE_ID.match(item) for item in models):
        problems.append("models must be a list of mhs:// device ids")
        models = ()
    out["models"] = tuple(models)
    title = _attr(cls, "resource_title")
    out["resource_title"] = title if isinstance(title, str) and title else None
    return out


def _extra_resources(raw: Any, main: str, problems: list[str]) -> tuple[ResourceModel, ...]:
    """``extra_resources = {resource_id: {"kind": <resource kind>, "title": <optional>}}``, validated."""
    if raw is None or (isinstance(raw, Mapping) and not raw):
        return ()
    shape = ("extra_resources must map resource ids to {'kind': <catalogue resource kind>} with an optional "
             "'title'")
    if not isinstance(raw, Mapping):
        problems.append(f"{shape}, got {raw!r}"[:500])
        return ()
    if len(raw) > MAX_EXTRA_RESOURCES:
        problems.append(f"extra_resources declares {len(raw)} resources; a composed package has at most "
                        f"{MAX_EXTRA_RESOURCES} besides its main resource")
        return ()
    out: list[ResourceModel] = []
    for resource_id, spec in raw.items():
        if not isinstance(resource_id, str) or not _RESOURCE_ID.match(resource_id):
            problems.append(f"extra_resources key {resource_id!r} must match [a-z0-9][a-z0-9_.-]*")
            continue
        if resource_id == main:
            problems.append(f"extra_resources[{resource_id!r}] repeats the main resource_id; the main resource "
                            "is declared by resource_id and device_kind")
            continue
        if not isinstance(spec, Mapping) or "kind" not in spec or set(spec) - {"kind", "title"}:
            problems.append(f"extra_resources[{resource_id!r}]: {shape}")
            continue
        kind = spec["kind"]
        if not isinstance(kind, str) or not _KIND.match(kind):
            problems.append(f"extra_resources[{resource_id!r}].kind must be a resource kind such as "
                            f"'sensor.depth' (python3 -m mhs.driver catalog kinds), got {kind!r}")
            continue
        title = spec.get("title")
        if title is not None and (not isinstance(title, str) or not title.strip() or len(title) > 200
                                  or any(ord(char) < 32 or ord(char) == 127 for char in title)):
            problems.append(f"extra_resources[{resource_id!r}].title must be a non-empty string of at most 200 "
                            f"characters without control characters, got {title!r}")
            continue
        out.append(ResourceModel(resource_id, kind, title))
    return tuple(out)


# ---------------------------------------------------------------------------
# decorated classes
# ---------------------------------------------------------------------------


def _members(cls: type, stop: Sequence[type]) -> dict[str, Any]:
    """Attributes of ``cls`` and its bases below the ``stop`` classes (subclass definitions win)."""
    out: dict[str, Any] = {}
    for klass in reversed(cls.__mro__):
        if klass in stop or klass is object:
            continue
        for name, value in vars(klass).items():
            out[name] = value
    return out


def model_for_class(cls: type, *, stop: Sequence[type], reserved: frozenset[str], native_symbol: Any,
                    safe_state: Any) -> DriverModel:
    """The :class:`DriverModel` of a decorated Driver class (not yet resolved; see :func:`finish`)."""
    problems: list[str] = []
    attrs = check_class_attributes(cls, problems, native_symbol=native_symbol, safe_state=safe_state)
    model = DriverModel(
        driver=cls.__qualname__, device_id=attrs["device_id"], device_kind=attrs["device_kind"],
        resource_id=attrs["resource_id"], mode=attrs["mode"], declared_risk=attrs["risk"],
        safe_state=attrs["safe_state"], estop_physical_ref=attrs["estop_physical_ref"],
        estop_latency_ms=attrs["estop_latency_ms"], estop_terminal=attrs["estop_terminal"],
        watchdog_ms=attrs["watchdog_ms"], fidelity=attrs["fidelity"],
        display_name=attrs["display_name"], vendor=attrs["vendor"], model=attrs["model"], tags=attrs["tags"],
        facts=attrs["facts"], native_symbol=attrs["native_symbol"], upstream=attrs["upstream"],
        resource_title=attrs["resource_title"], models=attrs["models"], problems=problems,
        extra_resources=list(attrs["extra_resources"]),
    )
    if model.mode == "simulated" and not model.fidelity:
        problems.append("a simulated driver declares its fidelity contract: fidelity = {engine, fidelity_level, "
                        "determinism, timestep_ms, realtime_factor, reset, snapshot_restore, gaps}")
    if model.mode == "hardware" and model.fidelity:
        problems.append("fidelity is declared by simulated drivers only; a hardware driver's fake backend is "
                        "served with the fake fidelity contract")
    params: dict[str, ParamModel] = {}
    actions: list[BindingModel] = []
    for attr, value in _members(cls, stop).items():
        roles = getattr(value, ROLE_ATTR, None) if callable(value) else None
        if not roles:
            continue
        if attr in reserved:
            problems.append(f"method name {attr!r} is reserved by the Driver base class; rename the method")
            continue
        if len(roles) > 1:
            problems.append(f"{attr}() has several driver decorators; give each role its own method")
            continue
        role = roles[0]
        sig = signature_of(value)
        if sig.var_args:
            problems.append(f"{attr}() must not take *args; name its inputs")
        if isinstance(role, ParamRole):
            _param_role(params, attr, role, sig, problems)
        elif isinstance(role, ActionRole):
            actions.append(binding_from_action(role.capability_id, role.declared, problems, attr=attr, signature=sig))
        elif isinstance(role, EstopRole):
            if model.estop is not None:
                problems.append(f"only one @estop method is allowed ({model.estop.attr} and {attr})")
                continue
            extra = [name for name in sig.names if name != "reason"]
            if extra:
                problems.append(f"@estop {attr}() may take only 'reason', not {extra}")
            model.estop = EstopModel(attr, role.native or attr, role.latency_ms, "reason" in sig.names)
        elif isinstance(role, InterlockRole):
            if any(item.id == role.id for item in model.interlocks):
                problems.append(f"interlock id {role.id!r} is declared twice")
                continue
            if sig.params:
                problems.append(f"@interlock {attr}() takes no parameters")
            model.interlocks.append(InterlockModel(attr, role.id, role.description, role.blocks, role.source,
                                                   role.reset_exempt))
        elif isinstance(role, ResetRole):
            if model.reset_attr is not None:
                problems.append(f"only one @reset method is allowed ({model.reset_attr} and {attr})")
                continue
            if sig.params:
                problems.append(f"@reset {attr}() takes no parameters")
            model.reset_attr = attr
    model.params = list(params.values())
    for param in model.params:
        _check_param(param, problems)
    configure = configure_binding(model.params, problems)
    model.bindings = ([configure] if configure is not None else []) + actions
    return model


def _param_role(params: dict[str, ParamModel], attr: str, role: ParamRole, sig: Signature,
                problems: list[str]) -> None:
    name = role.name or attr
    if not isinstance(name, str) or not _IDENT.match(name) or len(name) > 128:
        problems.append(f"parameter name {name!r} of {attr}() must be an identifier")
        return
    entry = params.get(name)
    if role.kind == "read":
        if sig.params:
            problems.append(f"@read getter {attr}() takes no parameters (it returns the value of {name!r})")
        if role.field.limits:
            problems.append(f"read-only parameter {name!r} cannot carry limits (only writes and inputs are limited)")
        if entry is None:
            params[name] = ParamModel(name, role.field, getter=attr, getter_signature=sig)
            return
        if entry.getter is not None:
            problems.append(f"parameter {name!r} has two @read getters ({entry.getter}, {attr})")
            return
        _same_field(name, entry.field, role.field, problems)
        entry.getter, entry.getter_signature = attr, sig
        if not entry.field.description and role.field.description:
            entry.field.description = role.field.description
        return
    if len(sig.params) != 1:
        problems.append(f"@write setter {attr}() takes exactly one parameter (the new value of {name!r})")
    if entry is None:
        params[name] = ParamModel(name, role.field, setter=attr, setter_signature=sig, risk=role.risk)
        return
    if entry.setter is not None:
        problems.append(f"parameter {name!r} has two @write setters ({entry.setter}, {attr})")
        return
    _same_field(name, entry.field, role.field, problems)
    description = entry.field.description
    entry.field = role.field
    if not entry.field.description and description:
        entry.field.description = description
    entry.setter, entry.setter_signature, entry.risk = attr, sig, role.risk


def _same_field(name: str, left: Field, right: Field, problems: list[str]) -> None:
    for key in ("type", "unit", "native_unit"):
        if getattr(left, key) != getattr(right, key):
            problems.append(f"parameter {name!r}: @read and @write disagree on {key} "
                            f"({getattr(left, key)!r} vs {getattr(right, key)!r})")


def _check_param(param: ParamModel, problems: list[str]) -> None:
    if param.field.type is None:
        problems.append(f"parameter {param.name!r} needs a type")
    if param.field.native_unit is not None:
        _check_conversion(param.field.unit, param.field.native_unit, param.field.delta, f"parameter {param.name!r}",
                          problems)
        if param.field.type not in ("number", "integer", "array"):
            problems.append(f"parameter {param.name!r}: native_unit needs a numeric field")


def _check_conversion(unit: Any, native_unit: Any, delta: bool, what: str, problems: list[str]) -> None:
    try:
        _units.convert(1.0, str(native_unit), str(unit), delta=delta)
    except _units.UnitError as exc:
        problems.append(f"{what}: cannot convert {native_unit!r} to {unit!r} ({exc})")


def configure_binding(params: Sequence[ParamModel], problems: list[str]) -> BindingModel | None:
    """The ``cap.device.configure.v1`` binding of the writable parameters (``None`` without any)."""
    writable = [item for item in params if item.is_writable]
    if not writable:
        return None
    limits: dict[str, Any] = {}
    reasons: dict[str, str] = {}
    for param in writable:
        for key, limit in param.field.limit_entries(param.name):
            if key in limits:
                problems.append(f"parameter {param.name!r}: two limits for path {key!r}")
                continue
            limits[key] = limit.to_json()
            if limit.is_operator_required:
                reasons[key] = str(limit.reason)
    risks = [item.risk for item in writable if item.risk]
    return BindingModel(CONFIGURE, "configure", limits=limits, operator_reasons=reasons,
                        risk=_catalog.risk_at_least(*risks) if risks else None, exclusive=None)


# ---------------------------------------------------------------------------
# actions
# ---------------------------------------------------------------------------


def binding_from_action(capability_id: str, declared: Action, problems: list[str], *, attr: str | None = None,
                        signature: Signature | None = None) -> BindingModel:
    """A :class:`BindingModel` for one action (decorated method or config-only :class:`Action`)."""
    what = f"{attr}()" if attr else capability_id
    name = declared.name or attr or capability_id.replace(".", "_")
    if not isinstance(name, str) or not _IDENT.match(name) or len(name) > 128:
        problems.append(f"{what}: action name {name!r} must be an identifier")
    if declared.risk is not None and declared.risk not in RISKS:
        # Action() validates it too; this catches a risk assigned after construction.
        problems.append(f"{what}: risk must be one of {list(RISKS)}, got {declared.risk!r}")
    binding = BindingModel(capability_id, name, attr=attr, signature=signature, title=declared.description,
                           exclusive=declared.exclusive, requires_permit=declared.requires_permit,
                           examples=list(declared.examples), safe_state=declared.safe_state, risk=declared.risk,
                           reenable=bool(getattr(declared, "reenable", False)))
    resource = getattr(declared, "resource", None)
    if resource is not None:
        if not isinstance(resource, str) or not _RESOURCE_ID.match(resource):
            problems.append(f"{what}: resource must be the id of the main resource or of one of extra_resources, "
                            f"got {resource!r}")
        else:
            binding.resource = resource
    if not isinstance(capability_id, str) or not _catalog._CAPABILITY_ID.match(capability_id):
        problems.append(f"{what}: {capability_id!r} is not a capability id (cap.<domain>.<name>.vN or "
                        "x-cap.<owner>.<name>.vN)")
        return binding
    if capability_id == CONFIGURE:
        problems.append(f"{what}: {CONFIGURE} is generated from the @write parameters; do not bind it as an action")
    if capability_id == MOTION_ESTOP:
        problems.append(f"{what}: {MOTION_ESTOP} is the e-stop latch; declare the native stop with @estop")
    if declared.description is not None and (not isinstance(declared.description, str) or len(declared.description) > 2000):
        problems.append(f"{what}: description must be a string of at most 2000 characters")
    fields: dict[str, Field] = {}
    if _catalog.is_extension(capability_id):
        _extension_schemas(binding, declared, signature, problems, what, fields)
    else:
        _class_schemas(binding, declared, signature, problems, what, fields)
    for key, limit in _limit_entries(fields, declared.limits, problems, what):
        binding.limits[key] = limit.to_json()
        if limit.is_operator_required:
            binding.operator_reasons[key] = str(limit.reason)
    for field_name, item in fields.items():
        if item.native_unit is not None:
            _check_conversion(item.unit, item.native_unit, item.delta, f"{what} input {field_name!r}", problems)
            binding.native_units[field_name] = (str(item.unit), str(item.native_unit), item.delta)
    constraints: dict[str, Any] = {}
    duration = declared.max_duration_ms
    if duration is not None and (not isinstance(duration, int) or isinstance(duration, bool) or duration < 1):
        problems.append(f"{what}: max_duration_ms must be a positive integer, got {duration!r}")
        duration = None
    if declared.long_running:
        constraints["long_running"] = True
        if duration is None and not _catalog.is_extension(capability_id):
            entry = _catalog.get(capability_id) or {}
            bound = (entry.get("constraints") or {}).get("max_duration_ms")
            if isinstance(bound, int) and not isinstance(bound, bool) and bound > 0:
                duration = bound
        if duration is None:
            problems.append(f"{what}: long_running=True needs max_duration_ms (the execution bound; the class "
                            "declares none)")
    if duration is not None:
        constraints["max_duration_ms"] = duration
    if declared.cancellable is not None:
        constraints["cancellable"] = bool(declared.cancellable)
    binding.constraints = constraints
    if declared.verb is not None:
        if not _catalog.is_extension(capability_id):
            problems.append(f"{what}: verb comes from the catalogue class; only x-cap actions declare one")
        elif declared.verb not in ("read", "write", "invoke"):
            problems.append(f"{what}: verb must be read, write or invoke, got {declared.verb!r}")
        else:
            binding.verb = declared.verb
    elif _catalog.is_extension(capability_id):
        binding.verb = "invoke"
    for index, example in enumerate(declared.examples):
        if not isinstance(example, Mapping):
            problems.append(f"{what}: examples[{index}] must be an input object")
    return binding


def _class_schemas(binding: BindingModel, declared: Action, signature: Signature | None, problems: list[str],
                   what: str, fields: dict[str, Field]) -> None:
    entry = _catalog.get(binding.capability_id)
    if entry is None:
        problems.append(f"{what}: {binding.capability_id} is not in the capability catalogue (search it with "
                        "python3 -m mhs.driver catalog search <words>, or use x-cap.<owner>.<name>.v1 with an "
                        "inline schema)")
        return
    if declared.output is not None:
        problems.append(f"{what}: the output of {binding.capability_id} is the class's; output= is only for x-cap actions")
    class_input = entry.get("input_schema") if isinstance(entry.get("input_schema"), Mapping) else {}
    class_props = class_input.get("properties") if isinstance(class_input.get("properties"), Mapping) else {}
    class_required = [str(item) for item in class_input.get("required") or []]
    open_class = class_input.get("additionalProperties", False) is not False or class_input.get("x-mhs-open") is True
    refinements = dict(declared.input or {})
    if signature is None:
        names: list[str] = list(refinements)
        required: list[str] = []
        var_kwargs = True
    else:
        names = list(signature.names)
        required = list(signature.required)
        var_kwargs = signature.var_kwargs
        if signature.positional_only:
            problems.append(f"{what}: positional-only parameters {list(signature.positional_only)} cannot be input fields")
    if not open_class:
        unknown = [item for item in names + list(refinements) if item not in class_props]
        if unknown:
            names = sorted(set(unknown))
            problems.append(f"{what}: {names} {'is not a field' if len(names) == 1 else 'are not fields'} of "
                            f"{binding.capability_id} (class fields: {sorted(class_props)}); method parameters must "
                            "be named exactly like the class fields")
    if signature is not None and not var_kwargs:
        missing = [item for item in class_required if item not in names]
        if missing:
            problems.append(f"{what}: {binding.capability_id} requires {missing}; add "
                            f"{'it' if len(missing) == 1 else 'them'} as method parameter{'s' if len(missing) != 1 else ''}")
        stray = [item for item in refinements if item not in names]
        if stray:
            problems.append(f"{what}: input refines {stray}, which the method does not take")
    for key, item in refinements.items():
        fields[key] = item
    if signature is not None and var_kwargs and not names and not refinements:
        return  # the class schema is inherited as is
    if signature is None and not refinements:
        return
    properties: dict[str, Any] = {}
    for key in names + [item for item in refinements if item not in names]:
        properties[key] = refinements[key].to_schema(what=f"{what} {key}") if key in refinements else {}
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if not var_kwargs:
        schema["additionalProperties"] = False
    if signature is not None:
        wanted = [item for item in dict.fromkeys(class_required + required) if item in properties]
        if wanted:
            schema["required"] = wanted
    binding.input_schema = schema


def _extension_schemas(binding: BindingModel, declared: Action, signature: Signature | None, problems: list[str],
                       what: str, fields: dict[str, Field]) -> None:
    inputs = dict(declared.input or {})
    if signature is not None:
        names = list(signature.names)
        missing = [item for item in names if item not in inputs]
        if missing:
            problems.append(f"{what}: x-cap input {missing} {'needs a Field' if len(missing) == 1 else 'need Fields'} "
                            "in input={...}")
        stray = [item for item in inputs if item not in names]
        if stray and not signature.var_kwargs:
            problems.append(f"{what}: input declares {stray}, which the method does not take")
        required = [item for item in signature.required if item in inputs]
        required += [item for item in inputs if item not in names and inputs[item].required is not False]
    else:
        required = [item for item, value in inputs.items() if value.required is not False]
    properties: dict[str, Any] = {}
    for key, item in inputs.items():
        if item.type is None:
            problems.append(f"{what}: x-cap input {key!r} needs a type")
        properties[key] = item.to_schema(what=f"{what} {key}")
        fields[key] = item
    input_schema: dict[str, Any] = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        input_schema["required"] = list(dict.fromkeys(required))
    outputs = dict(declared.output or {})
    out_properties: dict[str, Any] = {}
    for key, item in outputs.items():
        if item.type is None:
            problems.append(f"{what}: x-cap output {key!r} needs a type")
        if item.limits:
            problems.append(f"{what}: output {key!r} cannot carry limits")
        out_properties[key] = item.to_schema(what=f"{what} output {key}")
    output_schema: dict[str, Any] = {"type": "object", "properties": out_properties, "additionalProperties": False}
    out_required = [key for key, item in outputs.items() if item.required is not False]
    if out_required:
        output_schema["required"] = out_required
    binding.input_schema = input_schema
    binding.output_schema = output_schema
    binding.schema_digest = _catalog.extension_digest(input_schema, output_schema)


def _limit_entries(fields: Mapping[str, Field], absolute: Mapping[str, Limit], problems: list[str],
                   what: str) -> list[tuple[str, Limit]]:
    out: list[tuple[str, Limit]] = []
    seen: set[str] = set()
    for name, item in fields.items():
        for key, limit in item.limit_entries(name):
            if key in seen:
                problems.append(f"{what}: two limits for path {key!r}")
                continue
            seen.add(key)
            out.append((key, limit))
    for key, limit in absolute.items():
        if key in seen:
            problems.append(f"{what}: two limits for path {key!r}")
            continue
        try:
            _limits.parse_path(key)
        except _limits.LimitConfigError as exc:
            problems.append(f"{what}: limit path {key!r} is invalid ({exc})")
            continue
        seen.add(key)
        out.append((key, limit))
    return out


# ---------------------------------------------------------------------------
# resolution against the catalogue
# ---------------------------------------------------------------------------


def finish(model: DriverModel, *, mode: str | None = None) -> DriverModel:
    """Resolve every binding against the catalogue, compute the risk and raise the collected problems."""
    problems = model.problems
    seen: set[str] = set()
    floors: list[str] = []
    risks: list[str] = [model.declared_risk]
    state_schema = model.state_schema()
    served_mode = mode or model.mode
    cat = _catalog.default_catalog()
    for binding in model.bindings:
        if binding.capability_id in seen:
            problems.append(f"{binding.capability_id} is bound twice (one binding per capability)")
            continue
        seen.add(binding.capability_id)
        if binding.risk:
            risks.append(binding.risk)
        # Each binding resolves against the kind of the resource it is served on (package composition);
        # without extra_resources that is always the main resource and device_kind, as before.
        resource_id = model.resource_of(binding)
        kind = model.resource_kind(resource_id)
        if kind is None:
            declared = [model.resource_id] + [item.resource_id for item in model.extra_resources]
            problems.append(f"{binding.attr + '()' if binding.attr else binding.capability_id}: resource "
                            f"{resource_id!r} is not declared (resources: {declared}); declare it in "
                            "extra_resources or bind the main resource")
            continue
        main = resource_id == model.resource_id
        try:
            # Only cap.device.configure.v1 reads the state schema, and that binding is generated from the @write
            # parameters on the main resource (an action cannot bind it), so the main schema is the only one needed.
            effective = cat.resolve_binding(
                binding.capability_id, binding.input_schema, binding.output_schema, kind, served_mode,
                state_schema=state_schema, binding_limits=binding.limits or None,
                binding_verb=binding.verb if binding.extension else None,
                binding_requires_permit=binding.requires_permit)
        except _catalog.UnknownCapabilityError:
            continue  # already a problem of the binding
        except Exception as exc:  # noqa: BLE001 - a malformed binding is a definition problem
            problems.append(f"{binding.capability_id}: cannot be resolved ({type(exc).__name__}: {exc})")
            continue
        binding.effective = effective
        where = f"{binding.attr}()" if binding.attr else binding.capability_id
        for drift in effective.drift:
            problems.append(f"{where}: drifts from {binding.capability_id} ({drift.kind} at {drift.path}: "
                            f"{drift.message})")
        if not effective.extension:
            floors.append(effective.risk_floor)
            if not effective.kind_ok:
                kinds = (cat.get(binding.capability_id) or {}).get("resource_kinds") or []
                if main:
                    problems.append(f"{where}: {binding.capability_id} does not bind resource kind "
                                    f"{model.device_kind!r} (kinds: {kinds}); change device_kind or use an x-cap action")
                else:
                    problems.append(f"{where}: {binding.capability_id} does not bind resource kind {kind!r} of "
                                    f"resource {resource_id!r} (kinds: {kinds}); bind it on a resource of one of "
                                    "these kinds or use an x-cap action")
            if not effective.mode_ok:
                modes = (cat.get(binding.capability_id) or {}).get("modes") or []
                problems.append(f"{where}: {binding.capability_id} is not defined for mode {served_mode!r} "
                                f"(modes: {modes})")
        _output_rules(binding, effective)
        binding.takes_lock = _takes_lock(binding, effective, cat)
        if binding.safe_state:
            schema = effective.input_schema if isinstance(effective.input_schema, Mapping) else {}
            if schema.get("required") or (isinstance(schema.get("minProperties"), int) and schema["minProperties"] > 0):
                problems.append(f"{where}: a safe_state action is called with an empty input; "
                                f"{binding.capability_id} requires {schema.get('required') or 'input'}")
    if not model.bindings:
        problems.append("the driver declares no capability: a device needs at least one (a writable @write "
                        "parameter, or an @action; a read-only sensor binds a catalogue read class such as "
                        "cap.measure.temperature.v1 as an @action)")
    if model.extra_resources:
        known = set(getattr(cat, "resource_kinds", ()) or ())
        served = {model.resource_of(binding) for binding in model.bindings}
        for item in model.extra_resources:
            if item.kind not in known:
                problems.append(f"extra_resources[{item.resource_id!r}].kind {item.kind!r} is not a catalogue "
                                "resource kind (python3 -m mhs.driver catalog kinds)")
            if item.resource_id not in served:
                problems.append(f"extra_resources[{item.resource_id!r}] binds no capability; bind one with "
                                f"Action(resource={item.resource_id!r}) or @action(..., resource="
                                f"{item.resource_id!r}), or remove the resource")
    for interlock in model.interlocks:
        for pattern in interlock.blocks or ():
            if not any(_limits.pattern_matches(pattern, item) for item in seen):
                problems.append(f"interlock {interlock.id!r}: blocks {pattern!r}, which matches no bound capability "
                                f"(bound: {sorted(seen)})")
    _recovery_problems(model, problems)
    model.risk_floor = _catalog.risk_at_least(*floors)
    model.risk = _catalog.risk_at_least(model.risk_floor, *risks)
    if problems:
        raise DriverDefinitionError(list(dict.fromkeys(problems)), driver=model.driver)
    return model


def empty_input_problem(schema: Any) -> str | None:
    """Why the empty object is not a valid input of ``schema``, or None when it is (CORE-086).

    The SDK's JSON-schema validator decides (:func:`mhs.schema.validate`, the
    one that checks command inputs), so a requirement in ``oneOf``,
    ``anyOf`` or ``allOf``, a ``minProperties`` or a non-object ``type``
    counts as well as a top-level ``required``.  A schema the validator
    cannot evaluate cannot promise an empty input either.
    """
    if schema is None or (isinstance(schema, Mapping) and not schema):
        return None
    if not isinstance(schema, Mapping):
        return "its input schema is not a JSON object schema"
    from ..schema import validate as _validate  # deferred: keeps the driver model free of import cycles

    try:
        errors = _validate({}, dict(schema))
    except Exception as exc:  # noqa: BLE001 - an unevaluable schema cannot promise an empty input
        return f"its input schema cannot be evaluated ({type(exc).__name__})"
    return "; ".join(str(item) for item in errors[:3]) if errors else None


def _recovery_problems(model: DriverModel, problems: list[str]) -> None:
    """The declared recovery after an e-stop is well formed (CORE-086, CORE-087).

    A re-enable (``reenable=True``) is an ordinary effectful command the latch
    refuses: it is never a safe-state action, a stop class or a read, and it
    is called with an empty input (the conformance probe and an operator
    console send it without arguments; the empty object must validate
    against its input schema).  A decorated driver that declares one has no
    ``@reset`` hook: its reset only releases the latch, and any native
    recovery, fault clearing included, belongs in the re-enable (SAFE-042).
    A terminal e-stop (``estop_terminal``) describes a native stop whose
    effect a reset cannot undo: it needs that stop and excludes a re-enable.
    """
    reenable = [item for item in model.bindings if item.reenable]
    if len(reenable) > 1:
        problems.append("only one action may be declared reenable=True (the device's one re-enable after a safety "
                        f"reset), got {[item.capability_id for item in reenable]}")
    for binding in reenable:
        where = f"{binding.attr}()" if binding.attr else binding.capability_id
        if binding.safe_state:
            problems.append(f"{where}: a re-enable cannot be a safe_state action: safe-state actions run while the "
                            "device is latched, and the re-enable must be refused then (CORE-086)")
        if binding.capability_id in STOP_CLASSES:
            problems.append(f"{where}: the stop class {binding.capability_id} cannot be the re-enable (CORE-086)")
        effective = binding.effective
        verb = effective.verb if effective is not None else binding.verb
        if verb == "read":
            problems.append(f"{where}: a read cannot re-enable the device; the re-enable is an effectful "
                            "command (CORE-086)")
        schema = (effective.input_schema if effective is not None and isinstance(effective.input_schema, Mapping)
                  else binding.input_schema or {})
        refused = empty_input_problem(schema)
        if refused is not None:
            problems.append(f"{where}: the re-enable is called with an empty input, which {binding.capability_id} "
                            f"does not accept: {refused}")
    if reenable and model.reset_attr is not None:
        problems.append(f"@reset {model.reset_attr}(): a driver that declares a re-enable "
                        f"({reenable[0].capability_id}) has no @reset hook: a safety reset of such a device only "
                        "releases the latch, and any native recovery, fault clearing included, belongs in the "
                        "re-enable action (SAFE-042, CORE-086)")
    if model.estop_terminal is not None:
        if reenable:
            problems.append("estop_terminal declares an e-stop that a reset cannot undo; such a device has no "
                            "re-enable (remove reenable=True or estop_terminal, CORE-087)")
        if model.estop is None and not model.achieved_by:
            problems.append("estop_terminal describes the native stop: declare the @estop method (or a "
                            "safety_bindings stop) whose effect a reset cannot undo (CORE-087)")


def _output_rules(binding: BindingModel, effective: Any) -> None:
    schema = effective.output_schema if isinstance(effective.output_schema, Mapping) else {}
    properties = schema.get("properties") if isinstance(schema.get("properties"), Mapping) else {}
    required = [str(item) for item in schema.get("required") or []]
    binding.stamps_sampled_at = "sampled_at" in required and "sampled_at" in properties
    principal = [item for item in required if item not in SERVER_OUTPUTS | STAMPED_OUTPUTS]
    if len(principal) == 1:
        binding.principal_output = principal[0]
        return
    if not principal:
        members = [item for item in properties if item not in SERVER_OUTPUTS | STAMPED_OUTPUTS]
        if len(members) == 1:
            binding.principal_output = members[0]
            return
    binding.principal_output = None


def _takes_lock(binding: BindingModel, effective: Any, cat: Any) -> bool:
    if binding.safe_state or binding.capability_id in STOP_CLASSES:
        return False  # a stop or safe-state action never waits for a running call
    if binding.exclusive is not None:
        return bool(binding.exclusive)
    if effective.extension:
        return effective.verb != "read"
    entry = cat.get(binding.capability_id) or {}
    return entry.get("concurrency") == "exclusive"

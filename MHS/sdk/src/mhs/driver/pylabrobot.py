"""Finite PyLabRobot LiquidHandler helper (profile ``plr-liquid-handler-v1``).

A package declares one :class:`PlrProfile` on a config-only :class:`PyLabRobotDriver` subclass::

    class StarSim(PyLabRobotDriver):
        device_id, device_kind, mode, risk = "star-sim", "lab.liquid_handler", "simulated", "R2"
        native = "star_sim.env:RobotEnv"
        backends = {"fake": ".fake:FakeRobotEnv"}
        safe_state = "..."
        plr_profile = PlrProfile(
            handler="lh", handler_ref="star_sim/env.py:60",
            setup="setup", setup_ref="star_sim/env.py:59", close="teardown", close_ref="star_sim/env.py:68",
            channels=8, channels_ref="star_sim/env.py:33",
            tip_tracking_ref="star_sim/lab.py:35", volume_tracking_ref="star_sim/lab.py:36",
            labware=(PlrLabware("tip_rack", "tip_rack", "star_sim/deck.py:47"), ...),
            operations={"x-cap.oelemento.transfer.v1": PlrOperation("transfer", "star_sim/primitives.py:55-66")},
            volume_limit=Limit(min=1, max=1000, source="upstream_code", ref="agent.py:54"))

The helper binds a fixed, finite set of self-contained operations (see :mod:`mhs.bridge.pylabrobot`) as
``x-cap`` extensions with generated inline schemas: ``transfer`` and ``mix`` (R2, exclusive) and
``tracked_volumes`` (R0 read).  Labware is a declared allowlist (name, ``plate`` or ``tip_rack``, and the clone line
that creates it); the volume and the mix cycles carry a sourced :class:`Limit` or ``Limit.operator_required``.
Tips are selected from PyLabRobot's tip tracking and liquid is reported from its volume tracking, so the profile
cites the upstream lines that switch them on (``tip_tracking_ref``, ``volume_tracking_ref``).

Safety: ``LiquidHandler.stop()`` (``Machine.stop``) is teardown, never an e-stop.  A native stop exists only when
the profile names a source-backed one (:class:`PlrStop`); without it the e-stop is the runtime's software latch, a
hardware backend is refused before its factory runs (fail closed), and gate G3 refuses a hardware package at R1 or
above.  The loader still refuses an unreviewed model-written R2/R3 hardware backend.  No PyLabRobot code is
imported by this module, the bridge or the gate.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from ..bridge.base import make_mhs_error
from . import _natives
from . import model as _model
from .families import PythonObjectDriver, _FamilyDriver, _TOKENS, _message, _parameters
from .spec import Action, DriverDefinitionError, Field, Limit
from .upstream import parse_ref

__all__ = ["PLR_PROFILE", "PlrLabware", "PlrOperation", "PlrProfile", "PlrStop", "PyLabRobotDriver",
           "compile_profile"]

PLR_PROFILE = "plr-liquid-handler-v1"
#: Operation kinds of the profile and the PyLabRobot front-end calls each one makes (checked against its ref).
OPERATION_CALLS: Mapping[str, tuple[str, ...]] = {
    "transfer": ("pick_up_tips", "aspirate", "dispense", "discard_tips"),
    "mix": ("pick_up_tips", "aspirate", "dispense", "discard_tips"),
    "tracked_volumes": ("get_used_volume",),
}
LABWARE_KINDS = ("plate", "tip_rack")
#: A6..P24 style identifiers: rows A-P and columns 1-24 (6- to 384-well plates and tip racks).
WELL_PATTERN = "^[A-P](?:[1-9]|1[0-9]|2[0-4])$"
#: Native names that are PyLabRobot teardown or connection lifecycle, never a stop.
TEARDOWN_NAMES = frozenset({"stop", "teardown", "close", "disconnect", "shutdown", "__aexit__"})
MAX_WELLS = 384
_PATH = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\- ]{0,127}$")
_XCAP = re.compile(r"^x-cap\.[a-z0-9][a-z0-9_\-]*\.[a-z][a-z0-9_]*\.v[0-9]+$")


@dataclass(frozen=True)
class PlrLabware:
    """One deck resource an operation may name: ``kind`` is ``plate`` or ``tip_rack``; ``ref`` shows the name."""

    name: str
    kind: str
    ref: str


@dataclass(frozen=True)
class PlrOperation:
    """One bound operation: ``kind`` (``transfer``, ``mix``, ``tracked_volumes``) and the clone span (``ref``,
    ``path:START-END``, at most 40 lines) that shows the PyLabRobot calls it makes; ``description`` optionally
    replaces the tool text; ``volume_limit`` (transfer, mix) replaces the profile's for this operation, so each
    operation can cite its own line."""

    kind: str
    ref: str
    description: str | None = None
    volume_limit: Limit | None = None


@dataclass(frozen=True)
class PlrStop:
    """A source-backed native stop: an attribute path on the backend object (never a teardown) and its ref."""

    native: str
    ref: str
    description: str


@dataclass(frozen=True)
class PlrProfile:
    """The complete, immutable PyLabRobot declaration of one driver (see the module docstring)."""

    handler: str
    handler_ref: str
    setup: str
    setup_ref: str
    close: str
    close_ref: str
    channels: int
    channels_ref: str
    tip_tracking_ref: str | None = None
    volume_tracking_ref: str | None = None
    labware: tuple = ()
    operations: Any = ()
    volume_limit: Limit | None = None
    cycles_limit: Limit | None = None
    well_pattern: str = WELL_PATTERN
    stop: PlrStop | None = None
    timeout_ms: int = 120000
    setup_timeout_ms: int = 120000
    profile: str = field(default=PLR_PROFILE)

    def __post_init__(self) -> None:
        operations = self.operations
        if isinstance(operations, Mapping):
            operations = tuple((str(key), value) for key, value in operations.items())
        elif isinstance(operations, (list, tuple)):
            operations = tuple(tuple(item) if isinstance(item, (list, tuple)) else item for item in operations)
        object.__setattr__(self, "operations", operations)
        if isinstance(self.labware, list):
            object.__setattr__(self, "labware", tuple(self.labware))


@dataclass
class _Compiled:
    commands: dict[str, dict[str, Any]]
    actions: dict[str, Action]
    runtime: dict[str, Any]
    setup: dict[str, Any]
    close: dict[str, Any]
    safety: dict[str, Any]
    stop: PlrStop | None


def _ref_ok(value: Any) -> bool:
    return isinstance(value, str) and parse_ref(value) is not None


def _limit_ok(limit: Any, what: str, problems: list[str], *, volume: bool) -> bool:
    if not isinstance(limit, Limit):
        problems.append(f"{what} must be a Limit (sourced, or Limit.operator_required)")
        return False
    if limit.is_operator_required:
        return True
    if limit.source not in ("vendor_doc", "upstream_code") or not _ref_ok(limit.ref):
        problems.append(f"{what} needs source vendor_doc/upstream_code and a path:LINE ref, or "
                        "Limit.operator_required(reason)")
        return False
    if limit.min is None or limit.max is None or isinstance(limit.min, list) or isinstance(limit.max, list):
        problems.append(f"{what} must state a scalar min and max")
        return False
    if limit.min <= 0 if volume else limit.min < 1:
        problems.append(f"{what} minimum must be positive")
        return False
    return True


def _wells(profile: PlrProfile, description: str, *, maximum: int | None = None) -> Field:
    # The array carries the description; items stay terse (the MCP tool budget is 2048 bytes, gate G8).
    return Field("array", min_items=1, max_items=maximum or profile.channels,
                 items=Field("string", pattern=profile.well_pattern), description=description)


def _action(kind: str, operation: PlrOperation, profile: PlrProfile, plates: list[str], racks: list[str]) -> Action:
    if kind == "tracked_volumes":
        return Action(
            name="tracked_volumes", verb="read", risk="R0", exclusive=False,
            description=operation.description or ("Tracked liquid volume of declared wells (PyLabRobot volume "
                                                  "tracker bookkeeping, not a measurement)"),
            input={"labware": Field("string", enum=plates, description="Declared plate"),
                   "wells": _wells(profile, "Wells to report (A1..)", maximum=MAX_WELLS)},
            output={"volumes": Field("array", unit="uL", items=Field("number"),
                                     description="Tracked volume per requested well, in order")})
    own = operation.volume_limit
    volume = Field("number", unit="uL", description="Volume per channel",
                   limit=own if own is not None else profile.volume_limit)
    rack = Field("string", enum=racks, description="Tip rack; fresh tips are taken from it")
    tips = Field("array", items=Field("string"), description="Tip spots picked up, channel 0 first")
    if kind == "transfer":
        return Action(
            name="transfer", risk="R2", exclusive=True,
            description=operation.description or ("Pick up fresh tips, aspirate the source wells, dispense the "
                                                  "target wells, discard the tips; no cleanup after a failure"),
            input={"tip_rack": rack, "source": Field("string", enum=plates, description="Declared source plate"),
                   "source_wells": _wells(profile, "Source well per channel (A1..), channel 0 first"),
                   "target": Field("string", enum=plates, description="Declared target plate"),
                   "target_wells": _wells(profile, "Target well per channel, same count"), "volume": volume},
            output={"transferred_volume": Field("number", unit="uL",
                                                description="Volume per channel; every step returned"),
                    "channels": Field("integer", unit="1", description="Channels used"), "tips": tips})
    return Action(
        name="mix", risk="R2", exclusive=True,
        description=operation.description or ("Pick up fresh tips, aspirate and dispense the same wells per "
                                              "cycle, discard the tips; no cleanup after a failure"),
        input={"tip_rack": rack, "labware": Field("string", enum=plates, description="Declared plate"),
               "wells": _wells(profile, "Well per channel (A1..), channel 0 first"), "volume": volume,
               "cycles": Field("integer", unit="1", description="Aspirate-dispense cycles",
                               limit=profile.cycles_limit)},
        output={"mixed_volume": Field("number", unit="uL", description="Volume per channel per cycle"),
                "cycles": Field("integer", unit="1", description="Cycles completed"),
                "channels": Field("integer", unit="1", description="Channels used"), "tips": tips})


_INPUTS = {"transfer": ("tip_rack", "source", "source_wells", "target", "target_wells", "volume"),
           "mix": ("tip_rack", "labware", "wells", "volume", "cycles"),
           "tracked_volumes": ("labware", "wells")}
_OUTPUTS = {"transfer": ("transferred_volume", "channels", "tips"), "mix": ("mixed_volume", "cycles", "channels", "tips"),
            "tracked_volumes": ("volumes",)}


def compile_profile(profile: Any, problems: list[str], *, mode: str | None = None) -> _Compiled | None:
    """Validate ``profile`` and compile the bridge configuration, actions and runtime spec (``None``: invalid)."""
    if type(profile) is not PlrProfile:
        problems.append("plr_profile must be an exact PlrProfile(...)")
        return None
    before = len(problems)
    if profile.profile != PLR_PROFILE:
        problems.append(f"plr_profile.profile must be {PLR_PROFILE!r}")
    for name in ("handler", "setup", "close"):
        value = getattr(profile, name)
        if not isinstance(value, str) or (value and not _PATH.match(value)) or (name != "handler" and not value):
            problems.append(f"plr_profile.{name} must be an attribute path on the backend object")
        if not _ref_ok(getattr(profile, f"{name}_ref")):
            problems.append(f"plr_profile.{name}_ref must be 'path/in/clone:LINE'")
    if isinstance(profile.close, str) and profile.close.split(".")[-1] not in TEARDOWN_NAMES:
        problems.append("plr_profile.close must name the PyLabRobot teardown (stop/teardown/close/disconnect)")
    if not isinstance(profile.channels, int) or isinstance(profile.channels, bool) or not 1 <= profile.channels <= 96:
        problems.append("plr_profile.channels must be an integer from 1 to 96")
    if not _ref_ok(profile.channels_ref):
        problems.append("plr_profile.channels_ref must be 'path/in/clone:LINE'")
    for name in ("timeout_ms", "setup_timeout_ms"):
        value = getattr(profile, name)
        if not isinstance(value, int) or isinstance(value, bool) or not 1000 <= value <= 3_600_000:
            problems.append(f"plr_profile.{name} must be an integer from 1000 to 3600000")
    try:
        re.compile(profile.well_pattern)
    except (re.error, TypeError):
        problems.append("plr_profile.well_pattern must be a regular expression")
    if not isinstance(profile.well_pattern, str) or not profile.well_pattern.startswith("^") \
            or not profile.well_pattern.endswith("$"):
        problems.append("plr_profile.well_pattern must be anchored with ^ and $")
    labware: dict[str, str] = {}
    if not isinstance(profile.labware, tuple) or not profile.labware:
        problems.append("plr_profile.labware must declare at least one PlrLabware")
    for item in profile.labware if isinstance(profile.labware, tuple) else ():
        if type(item) is not PlrLabware:
            problems.append("plr_profile.labware entries must be PlrLabware(name, kind, ref)")
            continue
        if not isinstance(item.name, str) or not _NAME.match(item.name):
            problems.append(f"labware name {item.name!r} must be 1-128 plain characters")
        elif item.name in labware:
            problems.append(f"labware {item.name!r} is declared twice")
        if item.kind not in LABWARE_KINDS:
            problems.append(f"labware {item.name!r}: kind must be one of {list(LABWARE_KINDS)}")
        if not _ref_ok(item.ref):
            problems.append(f"labware {item.name!r}: ref must be 'path/in/clone:LINE'")
        labware[str(item.name)] = str(item.kind)
    plates = sorted(name for name, kind in labware.items() if kind == "plate")
    racks = sorted(name for name, kind in labware.items() if kind == "tip_rack")
    operations = profile.operations if isinstance(profile.operations, tuple) else ()
    if not operations:
        problems.append("plr_profile.operations must bind at least one capability")
    kinds: dict[str, str] = {}
    for entry in operations:
        if not (isinstance(entry, tuple) and len(entry) == 2):
            problems.append("plr_profile.operations maps an x-cap capability id to a PlrOperation")
            continue
        capability_id, operation = entry
        if not isinstance(capability_id, str) or not _XCAP.match(capability_id):
            problems.append(f"operation {capability_id!r}: the id must be x-cap.<owner>.<name>.vN")
        if capability_id in kinds:
            problems.append(f"operation {capability_id!r} is bound twice")
        if type(operation) is not PlrOperation or operation.kind not in OPERATION_CALLS:
            problems.append(f"operation {capability_id!r}: PlrOperation(kind, ref) with a kind of "
                            f"{sorted(OPERATION_CALLS)}")
            continue
        if not _ref_ok(operation.ref):
            problems.append(f"operation {capability_id!r}: ref must be 'path/in/clone:LINE' or 'path:START-END'")
        if operation.description is not None and (not isinstance(operation.description, str)
                                                  or not 10 <= len(operation.description) <= 200):
            problems.append(f"operation {capability_id!r}: description must be 10 to 200 characters")
        kinds[str(capability_id)] = operation.kind
        if operation.kind in ("transfer", "mix"):
            effective = operation.volume_limit if operation.volume_limit is not None else profile.volume_limit
            label = (f"operation {capability_id!r} volume_limit" if operation.volume_limit is not None
                     else "plr_profile.volume_limit")
            _limit_ok(effective, label, problems, volume=True)
        elif operation.volume_limit is not None:
            problems.append(f"operation {capability_id!r}: only transfer and mix take a volume_limit")
        if not plates:
            problems.append(f"operation {capability_id!r} needs at least one declared plate")
        if operation.kind != "tracked_volumes" and not racks:
            problems.append(f"operation {capability_id!r} needs at least one declared tip rack")
    composite = any(kind in ("transfer", "mix") for kind in kinds.values())
    if composite and not _ref_ok(profile.tip_tracking_ref):
        problems.append("plr_profile.tip_tracking_ref must cite the upstream line that switches PyLabRobot tip "
                        "tracking on (tips are chosen from it)")
    if "tracked_volumes" in kinds.values():
        if not _ref_ok(profile.volume_tracking_ref):
            problems.append("plr_profile.volume_tracking_ref must cite the upstream line that switches PyLabRobot "
                            "volume tracking on")
    uses_default = any(isinstance(operation, PlrOperation) and operation.kind in ("transfer", "mix")
                       and operation.volume_limit is None for _, operation in
                       (entry for entry in operations if isinstance(entry, tuple) and len(entry) == 2))
    if profile.volume_limit is not None and not uses_default:
        problems.append("plr_profile.volume_limit is unused: no transfer or mix operation without its own limit")
    if "mix" in kinds.values():
        _limit_ok(profile.cycles_limit, "plr_profile.cycles_limit", problems, volume=False)
    elif profile.cycles_limit is not None:
        problems.append("plr_profile.cycles_limit is only used by mix")
    stop = profile.stop
    if stop is not None:
        if type(stop) is not PlrStop:
            problems.append("plr_profile.stop must be a PlrStop(native, ref, description) or None")
        else:
            if not isinstance(stop.native, str) or not _PATH.match(stop.native):
                problems.append("plr_profile.stop.native must be an attribute path on the backend object")
            elif stop.native.split(".")[-1] in TEARDOWN_NAMES or stop.native == profile.close:
                problems.append("plr_profile.stop.native names a teardown; PyLabRobot stop()/teardown closes the "
                                "connection and never stops a running command")
            if not _ref_ok(stop.ref):
                problems.append("plr_profile.stop.ref must be 'path/in/clone:LINE'")
            if not isinstance(stop.description, str) or not 10 <= len(stop.description) <= 300:
                problems.append("plr_profile.stop.description must be 10 to 300 characters")
    if len(problems) > before:
        return None
    commands: dict[str, dict[str, Any]] = {}
    actions: dict[str, Action] = {}
    runtime_ops: dict[str, dict[str, str]] = {}
    for index, (capability_id, operation) in enumerate(operations):
        native = f"_mhs_plr_op.op{index}"
        actions[capability_id] = _action(operation.kind, operation, profile, plates, racks)
        commands[capability_id] = {
            "native": native, "invoke": "await",
            "args": {name: {"from": f"input.{name}"} for name in _INPUTS[operation.kind]},
            "result": {"map": {name: f"output.{name}" for name in _OUTPUTS[operation.kind]}},
            "concurrency": "shared" if operation.kind == "tracked_volumes" else "exclusive",
            "timeout_ms": 30000 if operation.kind == "tracked_volumes" else int(profile.timeout_ms),
        }
        runtime_ops[native] = {"capability_id": capability_id, "kind": operation.kind}
    safety: dict[str, Any] = {}
    if stop is not None:
        safety["estop"] = {"native": stop.native, "invoke": "call", "description": stop.description}
    runtime = {"handler": profile.handler, "labware": dict(sorted(labware.items())), "channels": profile.channels,
               "operations": runtime_ops}
    return _Compiled(commands, actions, runtime,
                     {"native": profile.setup, "timeout_ms": int(profile.setup_timeout_ms)},
                     {"native": profile.close}, safety, stop)


#: Class attributes a PyLabRobot package sets (besides the Driver declarations); every runtime map is generated.
_GENERATED = ("commands", "actions", "writes", "safety_bindings", "native_setup", "native_close")


class PyLabRobotDriver(PythonObjectDriver):
    """A PyLabRobot ``LiquidHandler`` front end (or an object holding one) through ``plr_profile``.

    Subclasses are data only: ``plr_profile`` plus the ordinary Driver declarations, and optionally read-only
    ``parameters`` with ``reads`` getters on the backend object.  ``commands``, ``actions``, ``writes``,
    ``safety_bindings``, ``native_setup`` and ``native_close`` are generated and cannot be set.
    """

    family = "pylabrobot"
    plr_profile: PlrProfile | None = None

    # -- definition checks ------------------------------------------------------------------------------------
    @classmethod
    def _check_plr_class(cls, problems: list[str]) -> None:
        from .base import Driver, _NativeAttr, _SafeStateAttr
        from ..bridge.base import Bridge
        protected = {name for base in (PyLabRobotDriver, PythonObjectDriver, _FamilyDriver, Driver, Bridge)
                     for name, value in vars(base).items()
                     if callable(value) or isinstance(value, (classmethod, staticmethod, property))}
        protected.difference_update({"native", "safe_state"})
        for owner in cls.__mro__:
            if owner is PyLabRobotDriver:
                break
            for name, value in vars(owner).items():
                if (name.startswith("__") and name.endswith("__")) or name == "_model_cache":
                    continue  # interpreter-managed class attributes (__annotate__, __module__, ...)
                if (name in protected or callable(value) and not isinstance(value, type)
                        or isinstance(value, (classmethod, staticmethod, property))
                        or (hasattr(type(value), "__get__") and type(value) not in (_NativeAttr, _SafeStateAttr)
                            and not isinstance(value, (str, int, float, bool, type(None))))):
                    problems.append(f"{name}: PyLabRobot packages are data only; methods and descriptors cannot "
                                    "be declared")
                if name in _GENERATED and value not in ({}, None):
                    problems.append(f"{name} is generated from plr_profile; do not set it")
                if name == "_needs_instance" and value:
                    problems.append("PyLabRobot profiles do not support instance-specific model hooks")

    # -- model ------------------------------------------------------------------------------------------------
    @classmethod
    def driver_model(cls) -> _model.DriverModel:
        # No shared mutable cache: every caller and instance owns its model.
        return copy.deepcopy(cls._family_model(None))

    @classmethod
    def _fill_model(cls, model: _model.DriverModel, instance: Any, problems: list[str]) -> None:
        cls._check_plr_class(problems)
        compiled = compile_profile(cls.plr_profile, problems, mode=model.mode)
        params = _parameters(cls.parameters, problems)
        model.params = params
        reads = dict(cls.reads or {})
        for param in params:
            if param.is_writable:
                problems.append(f"parameter {param.name!r}: PyLabRobot packages expose read-only parameters only")
            elif param.name not in reads:
                problems.append(f"read-only parameter {param.name!r} has no entry in reads")
        for name in reads:
            if model.param(name) is None:
                problems.append(f"reads[{name!r}] names no parameter (declare it in parameters)")
        if compiled is None:
            return
        model.bindings = [_model.binding_from_action(capability_id, action, problems)
                          for capability_id, action in compiled.actions.items()]
        model.interlocks = []
        try:
            bridge = cls._validation_bridge(model)
        except Exception as exc:  # noqa: BLE001 - a config the bridge refuses is a definition problem
            problems.append(f"the pylabrobot configuration is invalid: {_message(exc)}")
            return
        if compiled.stop is not None:
            model.estop = _model.EstopModel(None, compiled.stop.native[:128])
        bridge.close()

    @classmethod
    def _compiled(cls) -> _Compiled:
        problems: list[str] = []
        compiled = compile_profile(cls.plr_profile, problems)
        if compiled is None:
            raise DriverDefinitionError(problems, driver=cls.__qualname__)
        return compiled

    @classmethod
    def bridge_config(cls, resource_id: str, target: str = "mhs.driver._natives:validation") -> dict[str, Any]:
        compiled = cls._compiled()
        config: dict[str, Any] = {"target": target, "factory": {"kind": "none"},
                                  "capabilities": {key: dict(value, resource=resource_id)
                                                   for key, value in compiled.commands.items()},
                                  "setup": dict(compiled.setup), "close": dict(compiled.close)}
        reads = dict(cls.reads or {})
        if reads:
            config["reads"] = {resource_id: {"fields": copy.deepcopy(reads)}}
        if compiled.safety:
            config["safety_bindings"] = copy.deepcopy(compiled.safety)
        return config

    @classmethod
    def _validation_bridge(cls, model: _model.DriverModel) -> Any:
        from ..bridge.pylabrobot import PlrBridge

        compiled = cls._compiled()
        return PlrBridge(cls.bridge_config(model.resource_id), plr=compiled.runtime, load=False, strict=True)

    def _driver_model(self) -> _model.DriverModel:
        model = type(self).driver_model()
        # Freeze the served configuration: later class edits never reach this instance's bridge.
        self._plr_config = copy.deepcopy(type(self).bridge_config(model.resource_id))
        self._plr_runtime = copy.deepcopy(type(self)._compiled().runtime)
        self._plr_stop = type(self).plr_profile.stop
        self._plr_signature = json.dumps(self._plr_config, sort_keys=True, default=str)
        return model

    # -- runtime ----------------------------------------------------------------------------------------------
    def open_native(self) -> Any:
        if self.backend == "hardware" and self._plr_stop is None:
            raise make_mhs_error(
                "MHS.DEVICE.NOT_READY",
                f"{type(self).__name__}: no source-backed PyLabRobot stop is bound (plr_profile.stop); the "
                "hardware backend is refused before its factory runs", {"retryable": False})
        return super().open_native()

    def make_bridge(self, native: Any) -> Any:
        from ..bridge.pylabrobot import PlrBridge

        if native is None:
            raise make_mhs_error("MHS.DEVICE.NOT_READY", f"{type(self).__name__}: the {self.backend!r} backend "
                                 "produced no object", {"retryable": False})
        if json.dumps(self._plr_config, sort_keys=True, default=str) != self._plr_signature:
            raise DriverDefinitionError("PyLabRobot configuration changed after the driver was constructed")
        token = f"n{next(_TOKENS)}"
        setattr(_natives, token, native)
        self._native_token = token
        config = copy.deepcopy(self._plr_config)
        config["target"] = f"mhs.driver._natives:{token}"
        return PlrBridge(config, plr=copy.deepcopy(self._plr_runtime), outer_epoch=lambda: self.estop_epoch,
                         device_id=self.device_id, strict=True, base_dir=self.base_dir,
                         capability_schemas=self._schemas(self._model), safe_state_capabilities=[])

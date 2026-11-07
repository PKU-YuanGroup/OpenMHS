"""Config-only family drivers over the bundled bridges (plan 3.12, pilot helpers).

A family member is a subclass that sets class attributes only -- no methods::

    class CartPole(GymnasiumDriver):
        device_id = "cartpole"
        env_id = "CartPole-v1"

    class SR860(ScpiDriver):
        device_id, device_kind, risk = "sr860", "instrument.lockin", "R1"
        native = "srsinst.sr860:SR860"
        idn = {"expect": "^Stanford_Research_Systems,SR860"}
        parameters = {"frequency": Field("number", unit="Hz", writable=True,
                                         limit=Limit(min=0.001, max=500000, source="vendor_doc", ref="manual.pdf:112"))}
        reads = {"frequency": {"query": "FREQ?", "parse": {"kind": "float"}}}
        writes = {"frequency": {"write": "FREQ {value:g}"}}
        commands = {"x-cap.srs.auto_gain.v1": {"write": "AGAN"}}
        actions = {"x-cap.srs.auto_gain.v1": Action(name="auto_gain", description="Run auto gain")}
        safety_bindings = {"estop": {"write": "SLVL 0"}}
        backends = {"fake": ".fake:FakeLockin"}       # or transcript = "fixtures/session.json"

Shared attributes of the declarative families (:class:`PythonObjectDriver`,
:class:`SerialDriver`, :class:`ScpiDriver`), besides the :class:`Driver`
declarations (``device_id``, ``device_kind``, ``mode``, ``risk``, ``native``,
``backends``, ``tags``, ``facts``, ``safe_state`` ...):

* ``parameters`` -- ``{name: Field(..., writable=True|False, limit=...)}``: the
  resource state schema; writable parameters bind ``cap.device.configure.v1``.
* ``reads`` / ``writes`` -- the bridge's per-field read and per-parameter
  write specs, keyed by parameter name (the driver adds the resource).
* ``commands`` -- the bridge's capability map keyed by capability id (the
  python-object/serial ``capabilities``, the SCPI ``commands``).
* ``actions`` -- ``{capability id: Action(...)}``: names, limits, schemas of
  ``x-cap`` actions, ``safe_state=True`` (catalogue classes need no entry).
* ``safety_bindings`` -- the bridge's e-stop / safe-state / reset / interlock
  map; an interlock entry may add ``blocks`` (the capability ids it gates),
  ``source`` and ``reset_exempt``, which go to the manifest.

The bridge enforces nothing the server does not already enforce: limits,
interlocks and the latch stay server-side.  Family drivers cannot mix in
decorated methods (a definition error says so).
"""

from __future__ import annotations

import copy
import itertools
import json
import re
import sys
import threading
import types
from pathlib import Path
from typing import Any, Mapping

from ..bridge.base import Bridge, make_mhs_error
from . import _natives
from . import model as _model
from .base import Driver
from .spec import Action, DriverDefinitionError, Field
from .upstream import parse_ref, safe_relpath

__all__ = ["Sila2Driver", "GymnasiumDriver", "HttpDriver", "MujocoDriver", "OphydDriver", "PythonObjectDriver", "QcodesDriver", "RosDriver", "ScpiDriver", "SerialDriver"]

_TOKENS = itertools.count(1)
#: Interlock members that describe the manifest entry; the bridge never sees them.
_INTERLOCK_MANIFEST_KEYS = ("blocks", "source", "reset_exempt")


class _NullTransport:
    """A transport that is never used: lets a config be compiled without I/O."""

    def write(self, line: str, *, timeout_s: float | None = None) -> None:  # pragma: no cover - never called
        raise RuntimeError("validation transport")

    def read(self, *, timeout_s: float | None = None) -> str:  # pragma: no cover
        raise RuntimeError("validation transport")

    def query(self, line: str, *, timeout_s: float | None = None) -> str:  # pragma: no cover
        raise RuntimeError("validation transport")


class _FamilyDriver(Driver):
    """Base of the family drivers: the runtime is an inner WP-05 bridge built from class attributes."""

    _family_base = True
    #: True when the contract (schemas, limits) is derived from the backend (simulators).
    _needs_instance = False
    family = "abstract"

    parameters: Mapping[str, Field] = {}
    actions: Mapping[str, Action] = {}
    commands: Mapping[str, Mapping[str, Any]] = {}
    reads: Mapping[str, Any] = {}
    writes: Mapping[str, Any] = {}
    safety_bindings: Mapping[str, Any] = {}

    # -- model -----------------------------------------------------------------
    @classmethod
    def driver_model(cls) -> _model.DriverModel:
        cached = cls.__dict__.get("_model_cache")
        if cached is not None:
            return cached
        if cls._needs_instance:
            raise DriverDefinitionError(f"{cls.__qualname__} derives its contract from its backend; build it from "
                                        "an instance", driver=cls.__qualname__)
        model = cls._family_model(None)
        cls._model_cache = model
        return model

    def _driver_model(self) -> _model.DriverModel:
        if type(self)._needs_instance:
            return type(self)._family_model(self)
        return type(self).driver_model()

    @classmethod
    def _family_model(cls, instance: Any) -> _model.DriverModel:
        problems: list[str] = []
        attrs = _model.check_class_attributes(cls, problems, native_symbol=cls._native_symbol,
                                              safe_state=_text(cls._safe_state_text, problems))
        for klass in cls.__mro__:
            if klass in (_FamilyDriver, Driver, Bridge, object):
                continue
            for name, value in vars(klass).items():
                if callable(value) and getattr(value, _model.ROLE_ATTR, None):
                    problems.append(f"{name}(): family drivers are config-only; declare it in the class "
                                    "attributes (commands/actions/reads/writes) or write a plain Driver")
        extras = list(attrs["extra_resources"])
        if extras and not issubclass(cls, RosDriver):
            # Package composition is bounded to the families whose bridge routes bindings by resource and reads
            # an empty extra state without native I/O; any other family would serve a resource it cannot route.
            problems.append(f"extra_resources: the {cls.family} family serves one resource; several typed resources "
                            "in one package are supported for decorated Driver classes and RosDriver only")
            extras = []
        model = _model.DriverModel(
            driver=cls.__qualname__, device_id=attrs["device_id"], device_kind=attrs["device_kind"],
            resource_id=attrs["resource_id"], mode=attrs["mode"], declared_risk=attrs["risk"],
            safe_state=attrs["safe_state"], estop_physical_ref=attrs["estop_physical_ref"],
            estop_latency_ms=attrs["estop_latency_ms"], estop_terminal=attrs["estop_terminal"],
            watchdog_ms=attrs["watchdog_ms"],
            fidelity=attrs["fidelity"], display_name=attrs["display_name"], vendor=attrs["vendor"],
            model=attrs["model"], tags=attrs["tags"], facts=attrs["facts"], native_symbol=attrs["native_symbol"],
            upstream=attrs["upstream"], resource_title=attrs["resource_title"], models=attrs["models"],
            problems=problems, extra_resources=extras)
        cls._fill_model(model, instance, problems)
        return _model.finish(model)

    @classmethod
    def _fill_model(cls, model: _model.DriverModel, instance: Any, problems: list[str]) -> None:
        """Declarative families: parameters, configure binding, actions, safety from the class attributes."""
        params = _parameters(cls.parameters, problems)
        reads, writes = cls._field_maps()
        model.params = params
        configure = _model.configure_binding(params, problems)
        bindings = [configure] if configure is not None else []
        command_ids = list(dict(cls.commands or {}))
        declared = dict(cls.actions or {})
        for capability_id, item in declared.items():
            if not isinstance(item, Action):
                problems.append(f"actions[{capability_id!r}] must be an Action(...)")
            if capability_id not in command_ids:
                problems.append(f"actions declares {capability_id}, which no entry of commands binds")
        for capability_id in command_ids:
            action = declared.get(capability_id)
            if not isinstance(action, Action):
                action = Action()
                if capability_id.startswith(("x-cap.", "cap.x.")):
                    problems.append(f"{capability_id}: an x-cap command needs actions[{capability_id!r}] = "
                                    "Action(input={...}, output={...}) with its inline schema")
            bindings.append(_model.binding_from_action(capability_id, action, problems))
        model.bindings = bindings
        for param in params:
            if param.is_writable and param.name not in dict(writes or {}):
                problems.append(f"parameter {param.name!r} is writable but writes has no entry for it")
            if param.name not in dict(reads or {}) and not param.is_writable:
                problems.append(f"read-only parameter {param.name!r} has no entry in reads")
        for name in dict(reads or {}):
            if model.param(name) is None:
                problems.append(f"reads[{name!r}] names no parameter (declare it in parameters)")
        for name in dict(writes or {}):
            param = model.param(name)
            if param is None or not param.is_writable:
                problems.append(f"writes[{name!r}] needs a parameters[{name!r}] Field with writable=True")
        model.interlocks = _interlocks(cls.safety_bindings, problems)
        _reset_is_not_reenable(cls.commands, declared, cls.safety_bindings, problems)
        try:
            bridge = cls._validation_bridge(model)
        except Exception as exc:  # noqa: BLE001 - a config the bridge refuses is a definition problem
            problems.append(f"the {cls.family} configuration is invalid: {_message(exc)}")
            return
        native = getattr(bridge, "estop_native", None) or _safe_state_native(cls.safety_bindings)
        if native is not None:
            model.estop = _model.EstopModel(None, str(native)[:128])
        close = getattr(bridge, "close", None)
        if callable(close):
            close()

    @classmethod
    def _validation_bridge(cls, model: _model.DriverModel) -> Any:  # pragma: no cover - overridden
        raise NotImplementedError

    @classmethod
    def _field_maps(cls) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
        """Pure field compilation hook; default family behavior is unchanged."""
        return cls.reads, cls.writes

    @classmethod
    def _resource_maps(cls, resource_id: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        reads, writes = cls._field_maps()
        if reads:
            out["reads"] = {resource_id: {"fields": copy.deepcopy(dict(reads))}}
        if writes:
            out["writes"] = {resource_id: {"params": copy.deepcopy(dict(writes))}}
        safety = _bridge_safety(cls.safety_bindings)
        if safety:
            out["safety_bindings"] = safety
        return out

    # -- inner bridge ------------------------------------------------------------
    def make_bridge(self, native: Any) -> Any:  # pragma: no cover - overridden
        raise NotImplementedError

    def __init__(self, **kwargs: Any) -> None:
        self._inner_lock = threading.RLock()
        super().__init__(**kwargs)
        if self._model.estop is None:
            # No native stop is configured: the runtime reports a software-only latch (never "engaged"
            # with nothing called), exactly as for a Driver without an @estop method.
            self.estop = types.MethodType(Bridge.estop, self)

    @property
    def inner(self) -> Any:
        """The bridge doing the translation (created on first use from ``self.native``)."""
        bridge = self.__dict__.get("_inner_bridge")
        if bridge is not None:
            return bridge
        with self._inner_lock:
            bridge = self.__dict__.get("_inner_bridge")
            if bridge is None:
                bridge = self.make_bridge(self.native)
                self.__dict__["_inner_bridge"] = bridge
        return bridge

    def open(self) -> "Driver":
        super().open()
        _ = self.inner
        return self

    # -- Bridge contract: delegated ------------------------------------------------
    def call(self, capability_id: str, args: Mapping[str, Any] | None = None, ctx: Any = None) -> Any:
        self.ensure_open()
        return self.inner.call(capability_id, dict(args or {}), ctx)

    def read(self, resource_id: str, fields: Any = None, ctx: Any = None) -> Any:
        return self.inner.read(resource_id, fields, ctx)

    def write(self, resource_id: str, patch: Mapping[str, Any], ctx: Any = None) -> Any:
        self.ensure_open()
        return self.inner.write(resource_id, patch, ctx)

    def estop(self, reason: str = "", ctx: Any = None) -> Any:
        self._engage_estop()
        return self.inner.estop(reason, ctx)

    def interlocks(self) -> list[dict[str, str]]:
        return self.inner.interlocks()

    def reset(self, ctx: Any = None) -> Any:
        return self.inner.reset(ctx)

    def safety_status(self) -> dict[str, Any]:
        return self.inner.safety_status()

    def _run_safe_state(self, ctx: Any = None) -> Any:
        return self.inner.safe_state(ctx)

    def snapshot(self, device_id: str | None = None) -> dict[str, Any]:
        return self.inner.snapshot(device_id)

    def restore(self, snapshot: Any) -> dict[str, Any]:
        return self.inner.restore(snapshot)

    @property
    def estop_native(self) -> str | None:
        estop = self._model.estop
        return estop.native if estop is not None else None

    def close(self) -> None:
        bridge = self.__dict__.get("_inner_bridge")
        try:
            if bridge is not None:
                bridge.close()
        finally:
            super().close()

    def describe(self) -> dict[str, Any]:
        out = super().describe()
        bridge = self.__dict__.get("_inner_bridge")
        if bridge is not None:
            out["inner"] = bridge.describe()
        return out



def _text(value: Any, problems: list[str]) -> Any:
    if callable(value) and not isinstance(value, str):
        problems.append("safe_state is a description string, not a method")
        return None
    return value


def _message(exc: BaseException) -> str:
    text = getattr(exc, "message", None) or str(exc)
    data = getattr(exc, "data", None)
    errors = ((data or {}).get("details") or {}).get("errors") if isinstance(data, Mapping) else None
    if isinstance(errors, list) and errors and str(errors[0]) not in text:
        text += f" ({errors[0]})"
    return text[:500]


def _widening(declared: Any, derived: Any) -> str | None:
    """Why the ``declared`` rule does not narrow the ``derived`` rule of the same limit path (``None`` when it does).

    Both are limit rules in their JSON form.  The declared rule keeps every
    side the derived one bounds, each element inside it (scalar or
    per-element ``min``/``max``), and an ``allowed`` set inside the
    derived one; a derived ``operator_required`` is narrowed by any rule.
    """
    if not isinstance(derived, Mapping):
        return None
    if not isinstance(declared, Mapping):
        return "operator_required would drop the derived bound"
    for kind, inside in (("min", lambda new, old: new >= old), ("max", lambda new, old: new <= old)):
        bound = derived.get(kind)
        if bound is None:
            continue
        value = declared.get(kind)
        if value is None:
            return f"it states no {kind}, which the derived rule bounds"
        lists = [item for item in (bound, value) if isinstance(item, (list, tuple))]
        size = max((len(item) for item in lists), default=1)
        if any(len(item) != size for item in lists):
            return f"its {kind} has a different number of elements"
        for index in range(size):
            old = bound[index] if isinstance(bound, (list, tuple)) else bound
            new = value[index] if isinstance(value, (list, tuple)) else value
            if not inside(new, old):
                where = f" at element {index}" if lists else ""
                return f"{kind} {new} is outside the derived {kind} {old}{where}"
    allowed = derived.get("allowed")
    if isinstance(allowed, (list, tuple)):
        mine = declared.get("allowed")
        if not isinstance(mine, (list, tuple)) or any(item not in allowed for item in mine):
            return "its allowed values are not a subset of the derived ones"
    return None


def _parameters(raw: Any, problems: list[str]) -> list[_model.ParamModel]:
    if not isinstance(raw, Mapping):
        problems.append("parameters must map parameter names to Field objects")
        return []
    out = []
    for name, item in raw.items():
        if not isinstance(item, Field):
            problems.append(f"parameters[{name!r}] must be a Field, got {item!r}")
            continue
        if not isinstance(name, str) or not _model._IDENT.match(name):
            problems.append(f"parameter name {name!r} must be an identifier")
            continue
        if item.limits and not item.writable:
            problems.append(f"read-only parameter {name!r} cannot carry limits (only writes and inputs are limited)")
        if item.native_unit is not None:
            problems.append(f"parameter {name!r}: native_unit is not supported by family drivers; declare the "
                            "bridge's unit conversion in writes/reads ('units')")
        param = _model.ParamModel(name, item, writable=item.writable)
        _model._check_param(param, problems)
        out.append(param)
    return out


def _interlocks(raw: Any, problems: list[str]) -> list[_model.InterlockModel]:
    entries = (raw or {}).get("interlocks") if isinstance(raw, Mapping) else None
    out: list[_model.InterlockModel] = []
    for index, entry in enumerate(entries or []):
        if not isinstance(entry, Mapping) or not isinstance(entry.get("id"), str):
            continue  # the bridge reports it
        blocks = entry.get("blocks")
        if blocks is not None and (isinstance(blocks, str) or not all(isinstance(item, str) for item in blocks)):
            problems.append(f"safety_bindings.interlocks[{index}].blocks must be a list of capability ids")
            blocks = None
        source = entry.get("source", "hardware")
        if source not in ("hardware", "software", "operator", "simulated"):
            problems.append(f"safety_bindings.interlocks[{index}].source must be hardware, software, operator or "
                            "simulated")
            source = "hardware"
        out.append(_model.InterlockModel(None, entry["id"], entry.get("description"),
                                         tuple(blocks) if blocks is not None else None, source,
                                         bool(entry.get("reset_exempt", False))))
    return out


#: Members of a command or safety binding that name its native target (service, action, method, SCPI line ...).
_TARGET_KEYS = ("service", "action", "topic", "call", "method", "native", "write", "query", "command", "path",
                "tag", "register")


def _target(spec: Any) -> dict[str, Any]:
    if not isinstance(spec, Mapping):
        return {}
    return {key: spec[key] for key in _TARGET_KEYS if spec.get(key) is not None}


def _reset_is_not_reenable(commands: Any, declared: Mapping[str, Any], safety: Any, problems: list[str]) -> None:
    """SAFE-042 / CORE-086: the reset binding never calls the re-enable's native target.

    A device that declares a re-enable stays disabled after a reset until that
    command runs; a ``safety_bindings.reset`` that calls the re-enable's native
    target would re-arm the device inside the reset.  What is compared is the
    target members (``_TARGET_KEYS``) of the reset binding and of the
    re-enable's ``commands`` entry, exactly as declared (a ROS name is already
    absolute and normalised by the bridge validator).  A reset binding that
    re-arms the device through another target, or the same one spelled
    differently, is not detected: that stays the author's obligation, checked
    by review (CORE-086).
    """
    reset = _target((safety or {}).get("reset") if isinstance(safety, Mapping) else None)
    if not reset:
        return
    for capability_id, action in declared.items():
        if not (isinstance(action, Action) and action.reenable):
            continue
        if _target(dict(commands or {}).get(capability_id)) == reset:
            problems.append(f"safety_bindings.reset calls the native target of {capability_id}, the declared "
                            "re-enable: a reset never re-arms the device (SAFE-042, CORE-086); keep the re-enable "
                            "as its own command only")


def _safe_state_native(raw: Any) -> str | None:
    """The native a bridge's e-stop runs when only ``safety_bindings.safe_state`` is configured."""
    spec = raw.get("safe_state") if isinstance(raw, Mapping) else None
    if isinstance(spec, list) and spec:
        spec = spec[0]
    if isinstance(spec, str) and spec.strip():
        return spec
    if isinstance(spec, Mapping):
        for key in ("native", "command", "write"):
            value = spec.get(key)
            if isinstance(value, list) and value:
                value = value[0]
            if isinstance(value, str) and value.strip():
                return value
    return None


def _bridge_safety(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    out = copy.deepcopy(dict(raw))
    interlocks = out.get("interlocks")
    if isinstance(interlocks, list):
        out["interlocks"] = [{key: value for key, value in item.items() if key not in _INTERLOCK_MANIFEST_KEYS}
                             if isinstance(item, Mapping) else item for item in interlocks]
    return out


def _no_transport(driver: Driver) -> Exception:
    """The refusal of a non-hardware view whose backend produced no transport (never fall back to the device)."""
    return make_mhs_error(
        "MHS.DEVICE.NOT_READY",
        f"{type(driver).__name__}: the {driver.backend!r} backend produced no transport; a {driver.backend} view is "
        "served as mode simulated and never opens the configured port or host", {"retryable": False})


def _hardware_only(driver: Driver) -> Exception:
    return make_mhs_error(
        "MHS.DEVICE.NOT_READY",
        f"{type(driver).__name__} is a simulated driver; it has no hardware backend", {"retryable": False})


def _with_resource(commands: Mapping[str, Any], resource_id: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for capability_id, spec in dict(commands or {}).items():
        entry = copy.deepcopy(dict(spec)) if isinstance(spec, Mapping) else spec
        if isinstance(entry, dict):
            entry.setdefault("resource", resource_id)
        out[str(capability_id)] = entry
    return out


# ---------------------------------------------------------------------------
# python-object
# ---------------------------------------------------------------------------


class PythonObjectDriver(_FamilyDriver):
    """A Python object (sync or async SDK) behind :class:`mhs.bridge.python.PythonObjectBridge`.

    ``commands`` are canonical MHS-006 bindings (``native``, ``invoke``,
    ``args``, ``result``, ``errors``, ``concurrency``, ``timeout_ms``);
    ``reads`` map parameter names to a getter path or a native call;
    ``writes`` map parameter names to ``{native, invoke}`` (``invoke`` ``set``
    for a property, ``call``/``await`` for a method taking the value);
    ``native_setup`` / ``native_close`` name the object's open/close calls.
    The backend object (``backends[...]``) is the bridge's target.
    """

    family = "python-object"
    native_setup: Any = None
    native_close: Any = None

    @classmethod
    def bridge_config(cls, resource_id: str, target: str = "mhs.driver._natives:validation") -> dict[str, Any]:
        config: dict[str, Any] = {"target": target, "factory": {"kind": "none"}}
        commands = _with_resource(cls.commands, resource_id)
        if commands:
            config["capabilities"] = commands
        config.update(cls._resource_maps(resource_id))
        if cls.native_setup is not None:
            config["setup"] = cls.native_setup
        if cls.native_close is not None:
            config["close"] = cls.native_close
        return config

    @classmethod
    def _schemas(cls, model: _model.DriverModel) -> dict[str, Any]:
        return {binding.capability_id: {"output_schema": copy.deepcopy(binding.effective.output_schema)}
                for binding in model.bindings if binding.effective is not None}

    @classmethod
    def _validation_bridge(cls, model: _model.DriverModel) -> Any:
        from ..bridge.python import PythonObjectBridge

        return PythonObjectBridge(cls.bridge_config(model.resource_id), load=False, strict=True,
                                  safe_state_capabilities=[binding.capability_id for binding in model.bindings
                                                           if binding.safe_state])

    def _runtime_bridge_config(self, target: str) -> dict[str, Any]:
        return self.bridge_config(self._model.resource_id, target)

    def make_bridge(self, native: Any) -> Any:
        from ..bridge.python import PythonObjectBridge

        if native is None:
            raise make_mhs_error("MHS.DEVICE.NOT_READY", f"{type(self).__name__}: the {self.backend!r} backend "
                                 "produced no object", {"retryable": False})
        token = f"n{next(_TOKENS)}"
        setattr(_natives, token, native)
        self._native_token = token
        return PythonObjectBridge(self._runtime_bridge_config(f"mhs.driver._natives:{token}"),
                                  device_id=self.device_id, strict=True, base_dir=self.base_dir,
                                  capability_schemas=self._schemas(self._model),
                                  safe_state_capabilities=[binding.capability_id for binding in self._model.bindings
                                                           if binding.safe_state])

    def close(self) -> None:
        try:
            super().close()
        finally:
            token = getattr(self, "_native_token", None)
            if token is not None and hasattr(_natives, token):
                delattr(_natives, token)


# ---------------------------------------------------------------------------
# QCoDeS Parameters
# ---------------------------------------------------------------------------


class QcodesDriver(PythonObjectDriver):
    """Finite, explicit QCoDeS Parameter bindings over the retained Python bridge.

    ``parameter_bindings`` maps resource fields to ``parameter`` (a public
    dotted path), boolean ``get``/``set``, ``timeout_ms`` and ``source_ref``.
    A same-file Parameter factory may additionally name ``factory_ref``.
    Gets call ``Parameter.get`` and sets await the whole ``Parameter.set``
    operation, including native stepping/delays. Cache/get_latest are never
    substituted for a measurement. Source metadata is checked by G7.

    No QCoDeS import, discovery or native I/O occurs during definition or
    construction. The bounded declaration is copied per instance. Native
    completion, timeout retention, cancellation and safety use the existing
    PythonObjectBridge; a Parameter setter is not a stop acknowledgement.
    """

    family = "qcodes"
    parameter_bindings: Mapping[str, Mapping[str, Any]] = {}

    @classmethod
    def _field_maps(cls) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
        from .qcodes_config import compile_parameters

        return compile_parameters(cls.parameter_bindings, cls.parameters, cls.reads, cls.writes)

    @classmethod
    def driver_model(cls) -> _model.DriverModel:
        # No shared mutable model cache: config inspection and each instance
        # own a distinct model and never publish another instance's edits.
        return copy.deepcopy(cls._family_model(None))

    def _driver_model(self) -> _model.DriverModel:
        model = type(self).driver_model()
        self._qcodes_config = copy.deepcopy(type(self).bridge_config(model.resource_id))
        self._qcodes_backends = copy.deepcopy(dict(type(self).backends or {}))
        self.options = copy.deepcopy(self.options)
        return model

    def _backend_factory(self, backend: str) -> Any:
        from .base import _resolve_symbol

        if backend not in self._qcodes_backends:
            raise make_mhs_error("MHS.DEVICE.NOT_READY", f"no declared {backend!r} QCoDeS backend",
                                 {"retryable": False})
        target = self._qcodes_backends[backend]
        if callable(target) and not isinstance(target, str):
            return target
        try:
            return _resolve_symbol(str(target), self._package)
        except Exception as exc:
            raise make_mhs_error("MHS.DEVICE.NOT_READY", "QCoDeS backend could not be loaded",
                                 {"retryable": False}) from exc

    def _runtime_bridge_config(self, target: str) -> dict[str, Any]:
        config = copy.deepcopy(self._qcodes_config)
        config["target"] = target
        return config


# ---------------------------------------------------------------------------
# Classic Ophyd Signals
# ---------------------------------------------------------------------------


class OphydDriver(PythonObjectDriver):
    """Explicit Signal get/set mappings using retained native Status completion.

    No Ophyd import, device discovery, cached read or raw put is substituted.
    Source selectors are separately checked against pinned Component declarations.
    """
    family = "ophyd"
    signal_bindings: Mapping[str, Mapping[str, Any]] = {}
    unit_bindings: Mapping[str, str] = {}
    fake_unit_defaults: Mapping[str, str] = {}

    @classmethod
    def _check_runtime_hooks(cls):
        # These hooks can bypass frozen data entirely. Config/model hooks may
        # be compared, but alternate bridge/factory/schema construction is not
        # part of this declarative helper profile.
        protected = {'_driver_model', '_runtime_bridge_config', 'make_bridge',
                     '_schemas', '_backend_factory'}
        for owner in cls.__mro__:
            if owner is OphydDriver:
                break
            changed = protected.intersection(vars(owner))
            if changed:
                raise DriverDefinitionError('Ophyd does not support runtime-construction hook overrides: ' + ', '.join(sorted(changed)))

    def __init__(self, **kwargs):
        OphydDriver._check_runtime_hooks.__func__(type(self))
        super().__init__(**kwargs)

    @classmethod
    def _unit_class(cls, parameters, actions):
        # Bind only trusted SDK compilation hooks. User overrides may produce a
        # candidate model, but cannot define its expected hardware authority.
        return type(cls.__name__, (cls,), {
            "__module__": cls.__module__, "__qualname__": cls.__qualname__,
            "parameters": parameters, "actions": actions,
            "_fill_model": classmethod(_FamilyDriver._fill_model.__func__),
            "_field_maps": classmethod(OphydDriver._field_maps.__func__),
            "_resource_maps": classmethod(_FamilyDriver._resource_maps.__func__),
            "bridge_config": classmethod(PythonObjectDriver.bridge_config.__func__),
            "_validation_bridge": classmethod(PythonObjectDriver._validation_bridge.__func__),
        })

    @classmethod
    def _declared_model(cls, options, backend):
        from .ophyd_config import compile_unit_metadata
        parameters, actions, _ = compile_unit_metadata(cls.parameters, cls.actions, cls.unit_bindings,
                                                       cls.fake_unit_defaults, options, backend)
        configured = OphydDriver._unit_class.__func__(cls, parameters, actions)
        return _FamilyDriver._family_model.__func__(configured, None)

    @classmethod
    def _declared_runtime_config(cls, model, options, backend):
        from .ophyd_config import compile_unit_metadata
        parameters, actions, _ = compile_unit_metadata(cls.parameters, cls.actions, cls.unit_bindings,
                                                       cls.fake_unit_defaults, options, backend)
        configured = OphydDriver._unit_class.__func__(cls, parameters, actions)
        return PythonObjectDriver.bridge_config.__func__(configured, model.resource_id)

    @classmethod
    def _fill_model(cls, model, instance, problems):
        from .ophyd_config import compile_unit_metadata
        parameters, actions, options = compile_unit_metadata(cls.parameters, cls.actions, cls.unit_bindings,
            cls.fake_unit_defaults, instance.options if instance is not None else {},
            instance.backend if instance is not None else None)
        if instance is not None:
            instance.options = options
        configured = OphydDriver._unit_class.__func__(cls, parameters, actions)
        _FamilyDriver._fill_model.__func__(configured, model, instance, problems)

    @classmethod
    def _field_maps(cls):
        from .ophyd_config import compile_signals
        return compile_signals(cls.signal_bindings, cls.parameters, cls.reads, cls.writes)

    @classmethod
    def driver_model(cls):
        if cls._needs_instance:
            raise DriverDefinitionError("this Ophyd declaration requires an instance with explicit deployment options")
        return copy.deepcopy(cls._family_model(None))

    def _driver_model(self):
        if "_ophyd_model" in self.__dict__:
            return copy.deepcopy(self._ophyd_model)
        cls = type(self)
        OphydDriver._check_runtime_hooks.__func__(cls)
        from .ophyd_config import compile_unit_metadata, model_contract
        _, _, self.options = compile_unit_metadata(cls.parameters, cls.actions, cls.unit_bindings,
                                                   cls.fake_unit_defaults, self.options, self.backend)
        options = copy.deepcopy(self.options)
        factories = copy.deepcopy(dict(cls.backends or {}))
        # Capture both model authority and the full native mapping before an
        # author hook can change its comparator or execution identity.
        expected = OphydDriver._declared_model.__func__(cls, options, self.backend)
        authority = model_contract(expected)
        runtime = OphydDriver._declared_runtime_config.__func__(cls, expected, options, self.backend)
        runtime_authority = model_contract(runtime)
        model = cls._family_model(self) if cls._needs_instance else cls.driver_model()
        candidate_runtime = cls.bridge_config(model.resource_id)
        after = OphydDriver._declared_model.__func__(cls, self.options, self.backend)
        after_runtime = OphydDriver._declared_runtime_config.__func__(cls, after, self.options, self.backend)
        if (model_contract(model) != authority or model_contract(after) != authority
                or model_contract(candidate_runtime) != runtime_authority
                or model_contract(after_runtime) != runtime_authority
                or model_contract(self.options) != model_contract(options)
                or dict(cls.backends or {}) != factories):
            raise DriverDefinitionError("Ophyd instance model/runtime differs from the complete declared contract; only explicit unit_bindings refinements are supported")
        self._ophyd_config = copy.deepcopy(runtime)
        self._ophyd_backends = factories
        self._ophyd_options = options
        self._ophyd_model = copy.deepcopy(model)
        self._ophyd_contract = copy.deepcopy(authority)
        self._ophyd_runtime_contract = copy.deepcopy(runtime_authority)
        return model

    def _backend_factory(self, backend):
        from .base import _resolve_symbol
        if backend not in self._ophyd_backends:
            raise make_mhs_error("MHS.DEVICE.NOT_READY", f"no declared {backend!r} Ophyd backend", {"retryable": False})
        factory = self._ophyd_backends[backend]
        resolved = factory if callable(factory) and not isinstance(factory, str) else _resolve_symbol(str(factory), self._package)
        options = copy.deepcopy(self._ophyd_options)
        return lambda **_ignored: resolved(**copy.deepcopy(options))

    def _runtime_bridge_config(self, target):
        config = copy.deepcopy(self._ophyd_config)
        config["target"] = target
        return config


# ---------------------------------------------------------------------------
# Finite HTTP workflow
# ---------------------------------------------------------------------------


class HttpDriver(_FamilyDriver):
    """Finite HTTP workflow configuration; native admission remains blocked.

    The only current request-shape profile is ot2-run-v1. Backends are injected
    controlled peers, never automatically constructed HTTP clients. Class
    methods and runtime hooks cannot be overridden by a config-only package.
    """
    family = "http"
    http_config: Mapping[str, Any] = {}

    @classmethod
    def _check_http_class(cls):
        from .base import _NativeAttr, _SafeStateAttr
        from .http_config import compile_http
        from .spec import Limit
        protected = {name for base in (HttpDriver, _FamilyDriver, Driver, Bridge)
                     for name, value in vars(base).items()
                     if callable(value) or isinstance(value, (classmethod, staticmethod, property))}
        protected.difference_update({'native', 'safe_state'})  # SDK declaration descriptors, not caller hooks.
        for owner in cls.__mro__:
            if owner is HttpDriver:
                break
            for name, value in vars(owner).items():
                if (name in protected or callable(value)
                        or isinstance(value, (classmethod, staticmethod, property))
                        or (hasattr(type(value), '__get__') and type(value) not in (_NativeAttr, _SafeStateAttr)
                            and name not in ('__dict__', '__weakref__'))):
                    raise DriverDefinitionError('HTTP config-only classes cannot override methods: ' + name)
            if vars(owner).get('_needs_instance', False):
                raise DriverDefinitionError('HTTP profiles do not support instance-specific model hooks')
        config = compile_http(cls.http_config, cls.commands, cls.reads, cls.writes)
        if cls.mode != 'hardware' or cls.risk not in ('R2', 'R3') or cls.estop_physical_ref is not None:
            raise DriverDefinitionError('OT2 is an R2+ hardware declaration with no proven physical stop; fake mode is selected by the backend')
        for key, spec in config['commands'].items():
            action = cls.actions.get(key)
            operation = spec['operation']
            if type(action) is not Action or (action.safe_state and operation != 'cancel'):
                raise DriverDefinitionError('HTTP actions must be explicit; only cancellation can be a safe-state action')
            if operation in ('run', 'pause', 'resume', 'cancel') and action.risk not in (None, 'R2', 'R3'):
                raise DriverDefinitionError('HTTP effectful actions cannot lower the OT2 risk')
            if operation in ('run', 'resume') and not action.requires_permit:
                raise DriverDefinitionError('HTTP run and resume require explicit input-bound permits')
            if operation == 'run':
                fields = action.input or {}
                field = fields.get('protocol')
                if (set(fields) != {'protocol'} or type(field) is not Field or field.type != 'string'
                        or len(field.limits) != 1 or type(field.limits[0]) is not Limit or not field.limits[0].is_operator_required
                        or set(field.enum or ()) != set(config['artifacts'])
                        or not action.long_running or not action.cancellable):
                    raise DriverDefinitionError('HTTP run requires a cancellable operation and exact operator-required protocol choices')
            elif action.input:
                raise DriverDefinitionError('HTTP controls have no arbitrary caller-supplied request fields')
        if cls.safety_bindings != {'estop': {'operation': 'cancel'}}:
            raise DriverDefinitionError('HTTP requires the explicit owned-run cancellation safety binding')
        cancels = [key for key, spec in cls.commands.items() if spec.get('operation') == 'cancel']
        if not cancels or any(not isinstance(cls.actions.get(key), Action) or not cls.actions[key].safe_state for key in cancels):
            raise DriverDefinitionError('HTTP cancellation must have an explicit safe-state action contract')

    def __init__(self, **kwargs):
        HttpDriver._check_http_class.__func__(type(self))
        if kwargs.get('backend', 'fake') != 'fake':
            from ..bridge.http import native_unavailable
            native_unavailable()
        super().__init__(**kwargs)

    @classmethod
    def bridge_config(cls, resource_id):
        from .http_config import compile_http
        return compile_http(cls.http_config, cls.commands, cls.reads, cls.writes)

    @classmethod
    def _validation_bridge(cls, model):
        from ..bridge.http import HttpBridge
        return HttpBridge(HttpDriver.bridge_config.__func__(cls, model.resource_id), validation=True)

    @classmethod
    def driver_model(cls):
        from .ophyd_config import model_contract
        HttpDriver._check_http_class.__func__(cls)
        result = _FamilyDriver._family_model.__func__(cls, None)
        model_contract(result)
        return copy.deepcopy(result)

    def _driver_model(self):
        from .ophyd_config import model_contract
        if '_http_model' in self.__dict__:
            return HttpDriver._verified_model(self)
        model = HttpDriver.driver_model.__func__(type(self))
        self._http_config = HttpDriver.bridge_config.__func__(type(self), model.resource_id)
        self._http_model = copy.deepcopy(model)
        self._http_contract = model_contract(model)
        self._http_runtime_contract = model_contract(self._http_config)
        self._http_factories = copy.deepcopy(dict(type(self).backends))
        self._http_options = copy.deepcopy(self.options)
        return model

    def _verified_model(self):
        from .ophyd_config import model_contract
        current = HttpDriver.driver_model.__func__(type(self))
        runtime = HttpDriver.bridge_config.__func__(type(self), current.resource_id)
        if (model_contract(current) != self._http_contract
                or model_contract(self._model) != self._http_contract
                or model_contract(self._http_model) != self._http_contract
                or model_contract(runtime) != self._http_runtime_contract
                or model_contract(self._http_config) != self._http_runtime_contract
                or dict(type(self).backends) != self._http_factories
                or self.options != self._http_options):
            raise DriverDefinitionError('HTTP model/runtime differs from its immutable declared contract')
        return copy.deepcopy(self._http_model)

    def _backend_factory(self, backend):
        from .base import _resolve_symbol
        if backend != 'fake':
            from ..bridge.http import native_unavailable
            native_unavailable()
        factory = self._http_factories.get(backend)
        if factory is None:
            raise make_mhs_error('MHS.DEVICE.NOT_READY', 'HTTP needs an explicit controlled fake peer')
        resolved = factory if callable(factory) and not isinstance(factory, str) else _resolve_symbol(str(factory), self._package)
        return lambda **_ignored: resolved(**copy.deepcopy(self._http_options))

    def make_bridge(self, native):
        from ..bridge.http import HttpBridge
        model = HttpDriver._verified_model(self)
        return HttpBridge(copy.deepcopy(self._http_config), transport=native,
                          device_id=self.device_id, resource_id=model.resource_id, base_dir=self.base_dir)


# ---------------------------------------------------------------------------
# serial
# ---------------------------------------------------------------------------


class SerialDriver(_FamilyDriver):
    """A line-oriented serial instrument behind :class:`mhs.bridge.serial.SerialBridge`.

    ``commands`` map capability ids to ``{command, args, parse, result,
    response}``; ``reads`` map parameters to ``{command, parse}``; ``writes``
    to ``{command: "SP {value}", type}``.  The hardware backend opens pyserial
    with ``port`` (from ``options["port"]`` or the class attribute) and the
    line settings; a ``fake``/``sim`` backend is ``backends[...]`` (a
    pyserial-like object) or the recorded ``transcript`` (a path relative to
    the driver).  Only the hardware view opens the port: a fake view whose
    backend yields no object is refused ``MHS.DEVICE.NOT_READY``.
    """

    family = "serial"
    port: str | None = None
    baudrate: int = 115200
    timeout_s: float = 0.5
    encoding: str = "ascii"
    terminator: str = "\n"
    bytesize: Any = None
    parity: Any = None
    stopbits: Any = None
    transcript: str | None = None

    @classmethod
    def bridge_config(cls, resource_id: str, options: Mapping[str, Any] | None = None, *,
                      device: bool = True) -> dict[str, Any]:
        """The SerialBridge config; ``device=False`` (a fake view) leaves the port out."""
        config: dict[str, Any] = {"baudrate": cls.baudrate, "timeout_s": cls.timeout_s, "encoding": cls.encoding,
                                  "terminator": cls.terminator,
                                  "resources": [{"resource_id": resource_id, "kind": cls.device_kind}]}
        port = (options or {}).get("port", cls.port) if device else None
        if port is not None:
            config["port"] = port
        for key in ("bytesize", "parity", "stopbits"):
            value = (options or {}).get(key, getattr(cls, key))
            if value is not None:
                config[key] = value
        commands = _with_resource(cls.commands, resource_id)
        if commands:
            config["capabilities"] = commands
        config.update(cls._resource_maps(resource_id))
        return config

    @classmethod
    def _validation_bridge(cls, model: _model.DriverModel) -> Any:
        from ..bridge.serial import SerialBridge

        return SerialBridge(cls.bridge_config(model.resource_id))

    def open_native(self) -> Any:
        if self.backend in dict(type(self).backends or {}):
            return super().open_native()
        if self.backend == "hardware":
            if not self.is_hardware:
                raise _hardware_only(self)
            return None  # the bridge opens pyserial on the configured port
        if type(self).transcript:
            from ..bridge.transcript import Transcript

            return Transcript.load(self.base_dir / str(type(self).transcript)).serial(encoding=type(self).encoding)
        return super().open_native()

    def make_bridge(self, native: Any) -> Any:
        from ..bridge.serial import SerialBridge

        # Only the hardware view may open the configured port: a fake view needs its transport object.
        if native is None and not self.is_hardware:
            raise _no_transport(self)
        factory = (lambda **_options: native) if native is not None else None
        keys = ("port", "bytesize", "parity", "stopbits") if self.is_hardware else ("bytesize", "parity", "stopbits")
        options = {key: value for key, value in self.options.items() if key in keys}
        return SerialBridge(self.bridge_config(self._model.resource_id, options, device=self.is_hardware),
                            device_id=self.device_id, serial_factory=factory)


# ---------------------------------------------------------------------------
# SCPI
# ---------------------------------------------------------------------------


class ScpiDriver(_FamilyDriver):
    """A SCPI (or other query/write text protocol) instrument behind :class:`mhs.bridge.scpi.ScpiBridge`.

    ``commands`` map capability ids to ``{query|write, args, parse, result,
    opc, errors}``; ``reads`` map parameters to ``{query, parse}``; ``writes``
    to ``{write: "FREQ {value:g}", type}``; ``idn`` is the ``*IDN?`` check
    and ``error_query`` the error queue.  The hardware backend connects to
    ``host``/``port`` (stdlib socket) or ``visa_resource`` (pyvisa), from
    ``options`` or the class attributes; a ``fake``/``sim`` backend is
    ``backends[...]`` (an object with ``write/read/query``) or the recorded
    ``transcript`` (strict replay).  Only the hardware view connects: a fake
    view whose backend yields no transport is refused ``MHS.DEVICE.NOT_READY``.
    """

    family = "scpi"
    host: str | None = None
    port: int = 5025
    visa_resource: str | None = None
    visa_backend: str | None = None
    timeout_s: float = 2.0
    terminator: str = "\n"
    encoding: str = "ascii"
    idn: Any = True
    error_query: str | None = None
    error_ok: str | None = None
    transcript: str | None = None

    @classmethod
    def bridge_config(cls, resource_id: str, options: Mapping[str, Any] | None = None, *,
                      device: bool = True) -> dict[str, Any]:
        """The ScpiBridge config; ``device=False`` (a fake view) leaves host, port and VISA resource out."""
        config: dict[str, Any] = {"timeout_s": cls.timeout_s, "terminator": cls.terminator, "encoding": cls.encoding,
                                  "idn": copy.deepcopy(cls.idn),
                                  "resources": [{"resource_id": resource_id, "kind": cls.device_kind}]}
        for key in ("host", "port", "visa_resource", "visa_backend") if device else ():
            value = (options or {}).get(key, getattr(cls, key))
            if value is not None:
                config[key] = value
        if cls.error_query is not None:
            config["error_query"] = cls.error_query
        if cls.error_ok is not None:
            config["error_ok"] = cls.error_ok
        commands = _with_resource(cls.commands, resource_id)
        if commands:
            config["commands"] = commands
        config.update(cls._resource_maps(resource_id))
        config["strict"] = True
        return config

    @classmethod
    def _validation_bridge(cls, model: _model.DriverModel) -> Any:
        from ..bridge.scpi import ScpiBridge

        return ScpiBridge(cls.bridge_config(model.resource_id), transport=_NullTransport())

    def open_native(self) -> Any:
        if self.backend in dict(type(self).backends or {}):
            return super().open_native()
        if self.backend == "hardware":
            if not self.is_hardware:
                raise _hardware_only(self)
            return None  # the bridge opens the socket / VISA resource
        if type(self).transcript:
            from ..bridge.transcript import Transcript

            return Transcript.load(self.base_dir / str(type(self).transcript)).line_transport()
        return super().open_native()

    def make_bridge(self, native: Any) -> Any:
        from ..bridge.scpi import ScpiBridge

        # Only the hardware view may open the configured socket / VISA resource.
        if native is None and not self.is_hardware:
            raise _no_transport(self)
        options = {key: value for key, value in self.options.items()
                   if key in ("host", "port", "visa_resource", "visa_backend")} if self.is_hardware else {}
        return ScpiBridge(self.bridge_config(self._model.resource_id, options, device=self.is_hardware),
                          device_id=self.device_id, transport=native)


# ---------------------------------------------------------------------------
# ROS (rosbridge)
# ---------------------------------------------------------------------------


#: The server's e-stop budget when ``safety.estop.latency_ms`` is not declared (``mhs.server._DEFAULT_ESTOP_BUDGET_MS``).
_DEFAULT_ESTOP_BUDGET_MS = 1000


def _stall_budget(cls: type, model: _model.DriverModel, problems: list[str]) -> None:
    """SAFE-028 for a stall read-back (E1): the e-stop's worst case must fit in its declared budget.

    The bridge sends the stop, then ``samples`` read-backs ``interval_ms`` apart; with every request taking its whole
    timeout that is ``estop timeout + samples x read-back timeout + (samples - 1) x interval_ms``, which must not
    exceed ``estop_latency_ms`` (the server's 1000 ms when undeclared): otherwise every slow but correct confirmation
    would be reported as an e-stop timeout. A stop without a timeout (an action bound to the caller's budget) has no
    worst case to compare. A malformed stall is the bridge's definition problem, not repeated here.
    """
    safety = dict(getattr(cls, "safety_bindings", {}) or {})
    readback, stop = safety.get("safe_state"), safety.get("estop")
    stall = readback.get("stall") if isinstance(readback, Mapping) else None
    if not isinstance(stall, Mapping):
        return
    samples, interval = stall.get("samples"), stall.get("interval_ms")
    if type(samples) is not int or isinstance(interval, bool) or not isinstance(interval, (int, float)):
        return
    default_ms = float(getattr(cls, "timeout_s", 2.0)) * 1000

    def timeout_ms(spec: Any) -> float | None:
        if not isinstance(spec, Mapping):
            return 0.0
        if "action" in spec and "timeout_ms" not in spec:
            return None
        value = spec.get("timeout_ms", default_ms)
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    stop_ms, read_ms = timeout_ms(stop), timeout_ms(readback)
    budget = model.estop_latency_ms if model.estop_latency_ms else _DEFAULT_ESTOP_BUDGET_MS
    if stop_ms is None or read_ms is None:
        problems.append("safety_bindings.safe_state.stall: the e-stop and its read-back need timeout_ms, so that the "
                        "stall confirmation has a worst case to fit in the e-stop budget (SAFE-028)")
        return
    worst = stop_ms + samples * read_ms + (samples - 1) * float(interval)
    if worst > budget:
        problems.append(f"safety_bindings.safe_state.stall: the e-stop's worst case {worst:.0f} ms (stop {stop_ms:.0f} "
                        f"+ {samples} x read-back {read_ms:.0f} + {samples - 1} x interval {float(interval):.0f}) "
                        f"exceeds its budget {budget} ms; declare estop_latency_ms or shorten the timeouts (SAFE-028)")


def _fresh_budget(cls: type, model: _model.DriverModel, problems: list[str]) -> None:
    """SAFE-028 for a fresh-sample topic read-back (E2): the e-stop's worst case must fit in its declared budget.

    The bridge sends the stop, then waits at most ``fresh.within_ms`` for the confirming samples; the worst case is
    ``estop timeout + within_ms``, which must not exceed ``estop_latency_ms`` (the server's 1000 ms when undeclared).
    A stop without a timeout (an action bound to the caller's budget) has no worst case to compare and is refused
    here, as for a stall. A malformed ``fresh`` is the bridge's definition problem, not repeated here.
    """
    safety = dict(getattr(cls, "safety_bindings", {}) or {})
    readback, stop = safety.get("safe_state"), safety.get("estop")
    fresh = readback.get("fresh") if isinstance(readback, Mapping) else None
    if not isinstance(fresh, Mapping):
        return
    within = fresh.get("within_ms")
    if isinstance(within, bool) or not isinstance(within, (int, float)):
        return
    stop_ms: float | None = 0.0
    if isinstance(stop, Mapping):
        if "action" in stop and "timeout_ms" not in stop:
            stop_ms = None
        else:
            value = stop.get("timeout_ms", float(getattr(cls, "timeout_s", 2.0)) * 1000)
            stop_ms = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    if stop_ms is None:
        problems.append("safety_bindings.safe_state.fresh: the e-stop needs timeout_ms, so that the fresh-sample "
                        "confirmation has a worst case to fit in the e-stop budget (SAFE-028)")
        return
    budget = model.estop_latency_ms if model.estop_latency_ms else _DEFAULT_ESTOP_BUDGET_MS
    worst = stop_ms + float(within)
    if worst > budget:
        problems.append(f"safety_bindings.safe_state.fresh: the e-stop's worst case {worst:.0f} ms (stop "
                        f"{stop_ms:.0f} + within_ms {float(within):.0f}) exceeds its budget {budget} ms; declare "
                        "estop_latency_ms or shorten the bounds (SAFE-028)")


def _operator_bridges(cls: type, model: _model.DriverModel, problems: list[str]) -> None:
    """E3: the bridges the operator must run, declared on the class as ``operator_bridges``.

    A list of 1 to 8 entries ``{"args": <one ros_gz parameter_bridge argument>, "ref": <a citation that shows its ROS
    type>, "description"?: <one sentence>}`` (:func:`mhs.driver.ros_check.parse_operator_bridge`). The package never
    starts them; gate G7 checks each against the bindings and its citation, and the reference file lists them under
    "Operator must run". Malformed entries are definition problems (G3).
    """
    from .ros_check import parse_operator_bridge

    raw = getattr(cls, "operator_bridges", ()) or ()
    if raw == ():
        return
    if not isinstance(raw, (list, tuple)) or not 1 <= len(raw) <= 8:
        problems.append("operator_bridges must be a list of 1 to 8 {args, ref} entries")
        return
    out: list[dict[str, str]] = []
    names: set[str] = set()
    for index, item in enumerate(raw):
        label = f"operator_bridges[{index}]"
        if not isinstance(item, Mapping) or not {"args", "ref"} <= set(item) or set(item) - {"args", "ref", "description"}:
            problems.append(f"{label} must be an object with args, ref and an optional description")
            continue
        args, ref, description = item.get("args"), item.get("ref"), item.get("description")
        parsed = parse_operator_bridge(args)
        if parsed is None:
            problems.append(f"{label}.args is not one ros_gz parameter_bridge argument (<name>@<ROS type> for a service, "
                            "<name>@<ROS type>@|[|]<Gazebo type> for a topic)")
            continue
        if not isinstance(ref, str) or not ref.strip():
            problems.append(f"{label}.ref must cite the line that shows the bridge's ROS type")
            continue
        if description is not None and (not isinstance(description, str) or not description.strip()
                                        or len(description) > 300):
            problems.append(f"{label}.description must be one sentence of at most 300 characters")
            continue
        if parsed["name"] in names:
            problems.append(f"{label} bridges {parsed['name']} a second time")
            continue
        names.add(parsed["name"])
        entry = {"args": args, "ref": ref}
        if description is not None:
            entry["description"] = description
        out.append(entry)
    model.operator_bridges = tuple(out)


class RosDriver(_FamilyDriver):
    """A configuration-only ROS 1/2 endpoint through rosbridge JSON over WebSocket.

    ``commands`` bind services, topic publications or explicit action
    profiles (ROS 1 actionlib or ROS 2 native rosbridge); ``reads`` bind topic
    messages or explicit service requests. ``writes`` bind acknowledged
    service requests, including the deployment's parameter service. Native
    stop/reset/interlock bindings are explicit: action cancellation and node
    shutdown are never inferred to be emergency stops.

    A fake/offline sim backend supplies its own ``send/recv/close`` transport.
    A simulated class can use a live ``sim`` backend with an explicit runtime
    ``simulation_deployment`` containing ``endpoint``, complete ``fidelity``
    and ``deployment_id``. This is operator configuration, not proof of graph
    isolation. Every ROS hardware backend requires a valid human hardware
    review in ``driver.lock.json``, irrespective of risk or author. Checking
    the declaration and simulation deployment performs no network I/O.

    Package composition: ``extra_resources`` declares further typed resources
    of the same device (for example images on the main ``sensor.camera``
    resource and a point cloud on a ``sensor.depth`` resource); an
    ``actions[cap] = Action(resource=...)`` entry binds a command to one. The
    one bridge and transport serve every resource; an extra resource reads as
    ``{}`` without a transport request. A command map's own ``resource`` key is
    not authority: it must equal the declared binding resource.
    """

    family = "ros"
    ros_version: int = 2
    endpoint: str | None = None
    timeout_s: float = 2.0
    max_message_bytes: int = 1_048_576
    #: E3: the ros_gz parameter_bridge arguments the operator must run for this package (never started by it), each
    #: ``{"args": ..., "ref": <citation showing the ROS type>, "description"?: ...}``; G7 checks them and the
    #: reference file lists them (:func:`_operator_bridges`).
    operator_bridges: Any = ()

    @classmethod
    def _sensed_declaration(cls) -> tuple[Any, list[str]]:
        """The checked ``safety_bindings['sensed_stop']`` (SAFE-049) and its problems, computed once per class."""
        cached = cls.__dict__.get("_sensed_cache")
        if cached is None:
            from . import sensed_stop

            problems: list[str] = []
            cached = (sensed_stop.declaration(cls, problems), problems)
            cls._sensed_cache = cached
        return cached

    @classmethod
    def _fill_model(cls, model: _model.DriverModel, instance: Any, problems: list[str]) -> None:
        if type(cls.ros_version) is not int or cls.ros_version not in (1, 2):
            problems.append("ros_version must be 1 or 2 (the ROS node's version, not the rosbridge version)")
        sensed, sensed_problems = cls._sensed_declaration()
        problems.extend(sensed_problems)
        action_specs = list(dict(cls.commands or {}).items()) + [
            (f"safety_bindings.{name}", spec) for name, spec in dict(cls.safety_bindings or {}).items()
            if name not in ("interlocks", "sensed_stop")]
        for capability_id, binding in action_specs:
            if isinstance(binding, Mapping) and "action" in binding:
                expected = "ros1-actionlib" if cls.ros_version == 1 else "ros2-native"
                if binding.get("profile") != expected:
                    problems.append(f"{capability_id}: action profile must be {expected!r} for ros_version "
                                    f"{cls.ros_version}")
        super()._fill_model(model, instance, problems)
        _stall_budget(cls, model, problems)
        _fresh_budget(cls, model, problems)
        _operator_bridges(cls, model, problems)
        declared_actions = dict(cls.actions or {})
        for capability_id, command in dict(cls.commands or {}).items():
            if not isinstance(command, Mapping) or "resource" not in command:
                continue
            declared = declared_actions.get(capability_id)
            bound = (declared.resource if isinstance(declared, Action) else None) or model.resource_id
            if command["resource"] != bound:
                # Like safe_state, routing comes from the declared contract, never from the raw command map.
                problems.append(f"{capability_id}: commands[...]['resource'] is {command['resource']!r}, but the "
                                f"declared binding resource is {bound!r}; declare it with Action(resource=...)")
        for capability_id, command in dict(cls.commands or {}).items():
            if not isinstance(command, Mapping) or "point_cloud" not in command:
                continue
            expected = "sensor_msgs/" + ("msg/" if cls.ros_version == 2 else "") + "PointCloud2"
            if command.get("type") != expected:
                problems.append(f"{capability_id}: PointCloud2 type must match ros_version {cls.ros_version}")
            declared = dict(cls.actions or {}).get(capability_id)
            if isinstance(declared, Action) and declared.input:
                problems.append(f"{capability_id}: fixed point-cloud subscriptions take no caller controls")
            for binding in model.bindings:
                if binding.capability_id == capability_id:
                    binding.input_schema = {"type": "object", "properties": {}, "additionalProperties": False,
                                            "allOf": [{"type": "object"}]}
        for capability_id, command in dict(cls.commands or {}).items():
            if not isinstance(command, Mapping) or not ("image" in command or "cameras" in command):
                continue
            from ..bridge.ros_images import camera_sources
            sources = None
            if "cameras" in command:
                try:
                    sources = camera_sources(command["cameras"])
                    if command.get("safe_state", False) is not False:
                        problems.append(f"{capability_id}: image selectors cannot declare a safe-state stop")
                except ValueError as exc:
                    problems.append(f"{capability_id}: {exc}")
                    continue
            expected = ("sensor_msgs/" if cls.ros_version == 1 else "sensor_msgs/msg/")
            for source in sources.values() if sources is not None else [command]:
                if source.get("type") not in (expected + "Image", expected + "CompressedImage"):
                    problems.append(f"{capability_id}: image type must match ros_version {cls.ros_version}")
            declared = dict(cls.actions or {}).get(capability_id)
            if isinstance(declared, Action) and declared.input:
                problems.append(f"{capability_id}: image inputs are derived from the fixed source declaration")
            for binding in model.bindings:
                if binding.capability_id == capability_id:
                    # The catalogue resolver treats a bare empty object as a
                    # placeholder. An explicit object branch makes this closed,
                    # intentionally empty contract survive resolution.
                    binding.input_schema = ({"type": "object", "properties": {
                        "camera": {"type": "string", "enum": list(sources), "maxLength": 64,
                                   "description": "Select one declared image source; each capture is independent."}},
                        "required": ["camera"], "additionalProperties": False} if sources is not None else
                        {"type": "object", "properties": {}, "additionalProperties": False,
                         "allOf": [{"type": "object"}]})
        if sensed is not None and not sensed_problems:
            # SAFE-049: published as safety.estop.confirmation (thresholds as declared: cited or operator_required).
            model.estop_confirmation = sensed.manifest()

    @classmethod
    def bridge_config(cls, resource_id: str, options: Mapping[str, Any] | None = None, *,
                      device: bool = True, extra_resources: Any = (),
                      sensed: Any = None) -> dict[str, Any]:
        """The RosBridge configuration; ``extra_resources`` are the validated ``ResourceModel`` objects of the
        model (package composition), never the raw class attribute. ``sensed`` is the resolved thresholds, client
        bounds and ROS 2 source histories of a sensed-confirmation stop (:class:`mhs.driver.sensed_stop.Resolved`;
        ``None``: validation placeholders, never used for I/O)."""
        extras = list(extra_resources or ())
        config: dict[str, Any] = {
            "timeout_s": cls.timeout_s,
            "max_message_bytes": cls.max_message_bytes,
            "resources": [{"resource_id": resource_id, "kind": cls.device_kind}]
                         + [{"resource_id": item.resource_id, "kind": item.kind} for item in extras],
        }
        if device:
            endpoint = (options or {}).get("endpoint", cls.endpoint)
            if endpoint is not None:
                config["endpoint"] = endpoint
        commands = _with_resource(cls.commands, resource_id)
        for capability_id, command in commands.items():
            declared = dict(cls.actions or {}).get(capability_id)
            # Only the declared contract can grant the bypass used by a
            # safe-state action. A raw command-map flag is not authority.
            command["safe_state"] = isinstance(declared, Action) and declared.safe_state
            if extras and isinstance(command, dict):
                # The same rule routes a composed package: the declared binding resource, not the raw map.
                command["resource"] = (declared.resource if isinstance(declared, Action) else None) or resource_id
        if commands:
            config["commands"] = commands
        config.update(cls._resource_maps(resource_id))
        safety = config.get("safety_bindings")
        if isinstance(safety, dict) and "sensed_stop" in safety:
            declaration, problems = cls._sensed_declaration()
            if declaration is None or problems:
                safety.pop("sensed_stop")  # the definition problems are reported; the rest still compiles
            elif sensed is None:
                safety["sensed_stop"] = declaration.bridge_json(cls.ros_version, None)
            else:
                safety["sensed_stop"] = declaration.bridge_json(cls.ros_version, sensed.values, sensed.bounds,
                                                                sensed.history)
        if not cls.parameters:
            # Action-only ROS drivers still declare their main resource. Its
            # empty state must be readable without inventing a topic or waiting
            # for one (a paused simulator may publish no observations at all).
            config.setdefault("reads", {}).setdefault(resource_id, {"fields": {}})
        for item in extras:
            # An extra resource has no parameters: it reads as {} without a transport request.
            config.setdefault("reads", {})[item.resource_id] = {"fields": {}}
        return config

    @classmethod
    def _validation_bridge(cls, model: _model.DriverModel) -> Any:
        from ..bridge.ros import RosBridge

        return RosBridge(cls.bridge_config(model.resource_id, device=False, extra_resources=model.extra_resources),
                         transport=_NullTransport(), device_mode=cls.mode)

    def __init__(self, *, simulation_deployment: Mapping[str, Any] | None = None, **kwargs: Any) -> None:
        # Keep the operator's data separate from package/factory options and
        # immutable after validation. Caller mutations cannot retarget a lazy
        # connection or change fidelity under the same served identity.
        self._simulation_deployment_json: str | None = None
        #: resolved thresholds, client bounds, ROS 2 source histories and operator-filled names of a
        #: sensed-confirmation stop (SAFE-049; :class:`mhs.driver.sensed_stop.Resolved`)
        self._sensed_resolved: Any = None
        if simulation_deployment is not None:
            if kwargs.get("backend", "fake") != "sim" or type(self).mode != "simulated":
                raise ValueError("simulation_deployment requires backend='sim' and a mode='simulated' RosDriver")
            if "sim" in dict(type(self).backends or {}):
                raise ValueError("simulation_deployment cannot be combined with a declared sim backend factory")
            if "endpoint" in (kwargs.get("options") or {}):
                raise ValueError("supply the simulation endpoint only in simulation_deployment")
            if kwargs.get("device_id") is not None:
                raise ValueError("simulation_deployment determines the live simulation device_id")
            self._simulation_deployment_json = self._check_simulation_deployment(simulation_deployment)
            if "native" in kwargs:
                self._check_simulation_transport(kwargs["native"])
        sensed, sensed_problems = type(self)._sensed_declaration()
        deployment = json.loads(self._simulation_deployment_json or "null")
        if deployment is not None and "estop_confirmation" in deployment and (sensed is None or sensed_problems):
            raise ValueError("simulation_deployment.estop_confirmation is only for a driver with a sensed_stop")
        if deployment is not None and sensed is not None and not sensed_problems:
            from . import sensed_stop

            # SAFE-049: a live simulated driver with an unfilled operator_required threshold, or an unstated
            # operator_required ROS 2 source history (verification F1), does not construct.
            self._sensed_resolved = sensed_stop.deployment_member(sensed, deployment.get("estop_confirmation"))
        super().__init__(**kwargs)
        self._require_hardware_review()
        if sensed is not None and not sensed_problems and self._sensed_resolved is None:
            from . import sensed_stop

            # An offline backend (fake, or a declared sim factory, which never uses the live transport) reads the
            # package's placeholder thresholds and source histories; nothing else does.
            self._sensed_resolved = sensed_stop.fixture_resolved(self.base_dir, sensed)

    @staticmethod
    def _check_simulation_deployment(deployment: Mapping[str, Any]) -> str:
        from ..bridge.ros_transport import WebSocketTransport
        from ..schema import Validator, default_store
        from .._server.strict import _fidelity_findings

        required = {"endpoint", "fidelity", "deployment_id"}
        if not isinstance(deployment, Mapping) or set(deployment) - {"estop_confirmation"} != required:
            raise ValueError("simulation_deployment must contain exactly endpoint, fidelity and deployment_id "
                             "(and estop_confirmation for a sensed-confirmation stop)")
        try:
            encoded = json.dumps(dict(deployment), allow_nan=False, ensure_ascii=True)
            copied = json.loads(encoded)
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError("simulation_deployment must contain finite JSON data") from exc
        deployment_id = copied["deployment_id"]
        if not isinstance(deployment_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", deployment_id) is None:
            raise ValueError("simulation deployment_id must be one 1..64 character alphanumeric/_.- path segment")
        # The transport constructor checks the URL without importing a
        # WebSocket library or connecting; reuse exactly its URL policy.
        WebSocketTransport(copied["endpoint"])
        fidelity = copied["fidelity"]
        store = default_store()
        document, base = store.load("device.schema.json")
        schema = copy.deepcopy(document["properties"]["fidelity"])
        schema["required"] = ["engine", "fidelity_level", "determinism", "timestep_ms",
                              "realtime_factor", "reset", "snapshot_restore", "gaps"]
        errors = Validator(resolver=store).validate(fidelity, schema, base_uri=base)
        if not errors:
            errors = [item.message for item in _fidelity_findings(
                types.SimpleNamespace(mode="simulated", fidelity=fidelity), deployment_id)]
        if not errors and fidelity["fidelity_level"] == "F3":
            validation = fidelity.get("validation", {})
            if (not all(isinstance(validation.get(key), str) and validation[key].strip()
                        for key in ("against_device", "evidence_ref", "validated_at"))
                    or not isinstance(validation.get("metrics"), dict) or not validation["metrics"]):
                errors.append("F3 validation requires against_device, nonempty metrics, evidence_ref and validated_at")
        if errors:
            raise make_mhs_error("MHS.FIDELITY.CONTRACT_REQUIRED",
                                 "simulation_deployment requires complete deployed fidelity: " + "; ".join(errors),
                                 {"retryable": False})
        return encoded

    def _driver_model(self) -> _model.DriverModel:
        model = super()._driver_model()
        if self._simulation_deployment_json is None:
            return model
        deployment = json.loads(self._simulation_deployment_json)
        model = copy.deepcopy(model)
        model.fidelity = deployment["fidelity"]
        model.device_id = f"{model.device_id}/sim/{deployment['deployment_id']}"
        sensed, _problems = type(self)._sensed_declaration()
        if self._sensed_resolved is not None and sensed is not None and model.estop_confirmation is not None:
            # The deployment's thresholds and client bounds are what this device confirms with; its e-stop latency
            # covers the request timeouts plus the deployment's confirm_within_ms (SAFE-028 timing stays truthful).
            resolved = self._sensed_resolved
            model.estop_confirmation = sensed.manifest(resolved.values, operator=resolved.operator,
                                                       bounds=resolved.bounds, history=resolved.history,
                                                       history_operator=resolved.history_operator)
            bounds = resolved.bounds
            confirm = int(bounds.get("confirm_within_ms", sensed.bound("confirm_within_ms")))
            model.estop_latency_ms = max(int(model.estop_latency_ms or 0), sensed.request_timeout_ms() + confirm)
        return model

    def _validate_backend_projection(self, backend: str | None) -> None:
        """A deployed instance's copied model describes only its actual backend."""
        if self._simulation_deployment_json is not None and backend not in (None, "sim"):
            raise ValueError("a live simulation instance cannot be projected as another backend; use the driver class")

    def _check_simulation_transport(self, transport: Any) -> None:
        from ..bridge.ros_transport import WebSocketTransport
        from ..testing import Recorder

        while isinstance(transport, Recorder):
            transport = object.__getattribute__(transport, "_mhs_target")
        deployment = json.loads(self._simulation_deployment_json or "null")
        if (deployment is None or not isinstance(transport, WebSocketTransport)
                or transport.url != deployment["endpoint"]):
            raise ValueError("a simulation_deployment native must be a WebSocketTransport for its exact endpoint")

    def _require_hardware_review(self) -> None:
        if self.backend != "hardware":
            return
        if not self.is_hardware:
            raise _hardware_only(self)
        from .loader import read_lock, review_problem

        lock, problems = read_lock(self.base_dir)
        problem = review_problem(lock, problems, risk=self._model.risk, require_human=True)
        if problem is not None:
            raise PermissionError(f"{type(self).__name__}: {problem}")

    def open_native(self) -> Any:
        self._require_hardware_review()
        if self._simulation_deployment_json is not None:
            return None  # The validated simulation endpoint uses the SDK's lazy transport.
        if self.backend in dict(type(self).backends or {}):
            return super().open_native()
        if self.is_hardware:
            return None  # RosBridge opens the WebSocket only when an operation needs it.
        return super().open_native()

    def make_bridge(self, native: Any) -> Any:
        from ..bridge.ros import RosBridge
        from ..bridge.ros_transport import WebSocketTransport
        from ..testing import Recorder

        self._require_hardware_review()
        live_sim = self._simulation_deployment_json is not None
        if native is None and not self.is_hardware and not live_sim:
            raise _no_transport(self)
        transport = native
        while isinstance(transport, Recorder):
            transport = object.__getattribute__(transport, "_mhs_target")
        if live_sim and native is not None:
            self._check_simulation_transport(native)
        if not self.is_hardware and not live_sim and isinstance(transport, WebSocketTransport):
            raise make_mhs_error("MHS.DEVICE.NOT_READY", "a ROS fake/sim backend cannot use the live WebSocket transport",
                                 {"retryable": False})
        options = {"endpoint": self.options["endpoint"]} if self.is_hardware and "endpoint" in self.options else {}
        if live_sim:
            options = {"endpoint": json.loads(self._simulation_deployment_json)["endpoint"]}
        bridge = RosBridge(self.bridge_config(self._model.resource_id, options, device=self.is_hardware or live_sim,
                                              extra_resources=self._model.extra_resources,
                                              sensed=self._sensed_resolved),
                           device_id=self.device_id, transport=native, device_mode=type(self).mode,
                           capability_schemas={binding.capability_id: {
                               "output_schema": copy.deepcopy(binding.effective.output_schema)}
                               for binding in self._model.bindings if binding.effective is not None})
        # SAFE-049 / CORE-088 (verification F3): a sensed confirmation stands for a stop only on a bridge the endpoint
        # bound to the mode it serves (:meth:`_grant_served_mode`); the class's mode above can only refuse.
        bridge._bind_served_mode(self.__dict__.get("_mhs_served_mode"))
        return bridge

    def _grant_served_mode(self, mode: str) -> None:
        """Bind this driver's ROS bridge, now or when it is built, to the mode the endpoint serves the device with.

        Only :class:`mhs.server.MHSServer` calls it: for a device it serves on the SDK's own ROS route whose served
        manifest declares mode ``simulated`` and a sensed confirmation (SAFE-049, CORE-088; verification F3 of phase 3).
        Without it a sensed confirmation never commits a safe state (``not_simulated``), so no constructor argument
        or class attribute of a package grants one.
        """
        from ..bridge.ros import RosBridge

        with self._inner_lock:
            self.__dict__["_mhs_served_mode"] = mode
            bridge = self.__dict__.get("_inner_bridge")
            if type(bridge) is RosBridge:  # built by make_bridge above; nothing else is ever bound
                bridge._bind_served_mode(mode)


# ---------------------------------------------------------------------------
# simulators
# ---------------------------------------------------------------------------


_WORLD_STATE = {
    "observation": Field("object", description="Last observation (derived from the observation space)"),
    "reward": Field("number", nullable=True, description="Reward of the last step"),
    "terminated": Field("boolean"),
    "truncated": Field("boolean"),
    "tick": Field("integer", description="Transitions since the last reset"),
    "episode": Field("integer"),
    "seed": Field("integer", nullable=True),
    "info": Field("object"),
}


class _SimDriver(_FamilyDriver):
    _needs_instance = True
    mode = "simulated"
    device_kind = "world.sim"
    resource_id = "world"
    risk = "R0"
    #: fidelity contract members that override the derived defaults
    fidelity: Mapping[str, Any] | None = None
    #: Selected backend members override the common fidelity last (top-level merge).
    fidelity_by_backend: Mapping[str, Mapping[str, Any]] = {}

    @classmethod
    def _state_fields(cls) -> Mapping[str, Field]:
        return _WORLD_STATE

    @classmethod
    def _fill_model(cls, model: _model.DriverModel, instance: Any, problems: list[str]) -> None:
        if instance is None:
            problems.append(f"{cls.__qualname__} derives its contract from its backend; build it from an instance")
            return
        cls._backend_fidelity_overrides()  # reject malformed declarations before opening a backend
        if model.mode != "simulated":
            problems.append(f"{cls.__qualname__} serves a simulator: mode must be 'simulated'")
        if model.resource_id != "world":
            problems.append(f"{cls.__qualname__}: resource_id must be 'world' (the bridge serves that resource)")
        for name in ("commands", "reads", "writes", "parameters", "safety_bindings"):
            if getattr(cls, name):
                problems.append(f"{cls.__qualname__}: {name} is not used by simulator families")
        model.params = [_model.ParamModel(name, field) for name, field in cls._state_fields().items()]
        try:
            bridge = instance.inner
            listed = bridge.capabilities()
        except Exception as exc:  # noqa: BLE001 - the simulator cannot open: a definition problem here
            problems.append(f"the {cls.family} backend cannot be opened: {_message(exc)}")
            return
        declared = dict(cls.actions or {})
        names = {"cap.world.step.v1": "step", "cap.world.reset.v1": "reset", "cap.world.seed.v1": "seed"}
        bindings = []
        for entry in listed:
            capability_id = str(entry["capability_id"])
            action = declared.get(capability_id) or Action(name=names.get(capability_id))
            binding = _model.binding_from_action(capability_id, action, problems)
            if capability_id == "cap.world.step.v1":
                try:
                    binding.input_schema = copy.deepcopy(bridge.step_input_schema())
                    derive = getattr(bridge, "derive_step_limits", None)
                    if callable(derive):
                        # A rule the driver declares on the control vector takes precedence: the bridge derives only
                        # the paths no declared rule covers (MuJoCo: the model's ranges, operator_required for the
                        # rest) and reports a declared rule that would widen a model range.
                        derived, reasons, declared_problems = derive(copy.deepcopy(binding.limits))
                        derived, reasons = copy.deepcopy(dict(derived)), dict(reasons)
                        problems.extend(f"the step limits: {item}" for item in declared_problems)
                    else:
                        derived, reasons = copy.deepcopy(bridge.action_limits()), {}
                        for path in sorted(set(derived) & set(binding.limits)):
                            # A declared rule replaces the derived one of the same path only when it narrows it.
                            why = _widening(binding.limits[path], derived.pop(path))
                            if why:
                                problems.append(f"the step limits: {path}: the declared rule does not narrow the "
                                                f"bound the {cls.family} bridge derives ({why})")
                    binding.limits.update(derived)
                    binding.derived_limits = tuple(sorted(derived))
                    # Why a derived control has no bound (a MuJoCo actuator without a ctrlrange): the
                    # reference prints it next to the operator_required path, as for Limit.operator_required.
                    for path, reason in reasons.items():
                        if derived.get(path) == "operator_required" and isinstance(reason, str) and reason:
                            binding.operator_reasons[str(path)] = reason[:500]
                except Exception as exc:  # noqa: BLE001
                    problems.append(f"the step contract cannot be derived: {_message(exc)}")
            if capability_id not in declared:
                cls._describe_world_inputs(binding)
            determinism = entry.get("determinism")
            if determinism in ("exact", "seeded", "statistical", "none"):
                binding.determinism = determinism
            binding.native = str(entry.get("native") or "")[:200] or None
            bindings.append(binding)
        for capability_id in declared:
            if capability_id not in {str(entry["capability_id"]) for entry in listed}:
                problems.append(f"actions declares {capability_id}, which the {cls.family} bridge does not serve")
        model.bindings = bindings
        model.fidelity = instance.fidelity_for(None)

    #: Descriptions of the ``cap.world.*`` inputs the family serves (the catalogue classes carry none).
    _WORLD_INPUTS: Mapping[str, Mapping[str, Mapping[str, Any]]] = {
        "cap.world.step.v1": {
            "ticks": {"description": "Transitions to advance; the action is applied at every tick"},
            "action": {"description": "The action applied at each tick, shaped by the environment's action space"},
        },
        "cap.world.seed.v1": {
            "seed": {"type": "integer", "minimum": 0, "description": "Seed used by the next reset"},
        },
    }
    #: Inputs of ``cap.world.reset.v1`` the bridge honours (the class also lists ``scenario``).
    _RESET_INPUTS: Mapping[str, Mapping[str, Any]] = {}

    @classmethod
    def _describe_world_inputs(cls, binding: _model.BindingModel) -> None:
        """Describe the class fields the family serves, and leave out the ones its bridge refuses."""
        capability_id = binding.capability_id
        if capability_id == "cap.world.reset.v1":
            binding.input_schema = {"type": "object", "properties": copy.deepcopy(dict(cls._RESET_INPUTS)),
                                    "additionalProperties": False}
            return
        fields = cls._WORLD_INPUTS.get(capability_id)
        if not fields:
            return
        schema = copy.deepcopy(binding.input_schema) if isinstance(binding.input_schema, Mapping) else None
        if schema is None:
            schema = {"type": "object", "properties": {}, "additionalProperties": False}
        properties = schema.setdefault("properties", {})
        for name, extra in fields.items():
            if name in properties or capability_id != "cap.world.step.v1":
                entry = properties.setdefault(name, {})
                for key, value in extra.items():
                    entry.setdefault(key, copy.deepcopy(value))
        if capability_id == "cap.world.seed.v1":
            schema["required"] = ["seed"]
        binding.input_schema = schema

    @classmethod
    def _backend_fidelity_overrides(cls) -> Mapping[str, Mapping[str, Any]]:
        overrides = cls.fidelity_by_backend
        if not isinstance(overrides, Mapping):
            raise DriverDefinitionError("fidelity_by_backend must be a mapping of backend names to fidelity objects",
                                        driver=cls.__qualname__)
        for backend, override in overrides.items():
            if not isinstance(backend, str) or backend not in _model.BACKENDS:
                raise DriverDefinitionError(f"fidelity_by_backend has unknown backend {backend!r}; "
                                            f"expected one of {list(_model.BACKENDS)}", driver=cls.__qualname__)
            if not isinstance(override, Mapping):
                raise DriverDefinitionError(f"fidelity_by_backend[{backend!r}] must be a fidelity object",
                                            driver=cls.__qualname__)
        return overrides

    def fidelity_for(self, backend: str | None) -> dict[str, Any]:
        selected = self.backend if backend is None else backend
        if not isinstance(selected, str) or selected not in _model.BACKENDS:
            raise DriverDefinitionError(f"unknown fidelity backend {selected!r}", driver=type(self).__qualname__)
        overrides = type(self)._backend_fidelity_overrides()
        out = copy.deepcopy(self._derived_fidelity())
        override = type(self).fidelity
        if isinstance(override, Mapping):
            out.update(copy.deepcopy(dict(override)))
        out.update(copy.deepcopy(dict(overrides.get(selected, {}))))
        return out

    def _derived_fidelity(self) -> dict[str, Any]:  # pragma: no cover - overridden
        raise NotImplementedError

    def settle_native_work(self, timeout_s: float) -> bool:
        """Bounded wait (e-stop attempts) for the simulator's in-flight native call; True when settled.

        Delegates only to the SDK's own Gym or MuJoCo bridge method (compared by
        function object, as the endpoint does), never to a package override.
        """
        bridge = self.__dict__.get("_inner_bridge")
        if bridge is None:
            return True
        from ..bridge.gymnasium import GymnasiumBridge
        from ..bridge.mujoco import MujocoBridge

        method = getattr(type(bridge), "settle_native_work", None)
        bound = getattr(bridge, "settle_native_work", None)
        if (not any(method is sdk for sdk in (GymnasiumBridge.settle_native_work, MujocoBridge.settle_native_work))
                or getattr(bound, "__func__", None) is not method):
            return True   # not the SDK's hook: nothing is waited on; safety_status decides
        return bool(bound(timeout_s))


class GymnasiumDriver(_SimDriver):
    """A Gymnasium environment behind :class:`mhs.bridge.gymnasium.GymnasiumBridge` (``cap.world.*``).

    ``env_id`` (``gymnasium.make``), ``env_kwargs``, ``autoreset``, ``seed``
    and ``max_ticks`` configure it.  The ``fake``/``sim`` backend is
    ``gymnasium.make(env_id, **env_kwargs)`` unless ``backends`` names an
    environment factory.  ``cap.world.step.v1`` takes ``{ticks, action}``
    with the action derived from the action space (``Discrete`` ->
    ``{index}``, ``Box`` -> ``{values}`` with per-element limits).

    The limits derived from the space of a ``backends`` environment (the
    package's fake) carry no ``source``, only a ``ref`` naming that backend;
    ``action_space_ref`` (``path/in/clone:LINE``, the upstream line that
    defines the space the fake copies) makes them ``upstream_code`` with that
    ref, which gate G4 checks like the ref of any limit.
    """

    family = "gymnasium"
    _RESET_INPUTS = {
        "seed": {"type": "integer", "minimum": 0, "description": "Seed of the environment's random generator"},
        "options": {"type": "object", "description": "Environment-specific options of gymnasium reset()"},
    }
    env_id: str | None = None
    env_kwargs: Mapping[str, Any] = {}
    autoreset: bool = False
    seed: int | None = None
    max_ticks: int = 10_000
    fidelity_level: str = "F0"
    #: ``path/in/clone:LINE`` of the upstream code that defines the action space (None: not cited)
    action_space_ref: str | None = None
    timing_by_backend: Mapping[str, Mapping[str, Any]] = {}
    #: Explicit bounded JSON checkpoint methods; method presence alone is insufficient.
    #: ``{"profile": "none", "reason": ...}`` opts a backend out explicitly (no protocol snapshots).
    checkpoint_by_backend: Mapping[str, Mapping[str, Any]] = {}
    #: Asynchronous environments (``asyncio_owned_loop_v1``, :mod:`mhs.bridge.gym_async`), per backend.
    async_by_backend: Mapping[str, Mapping[str, Any]] = {}
    #: dm_env / dm_control composer environments (``dm_env_v1``, :mod:`mhs.bridge.dm_env_adapter`), per backend.
    dm_env_by_backend: Mapping[str, Mapping[str, Any]] = {}
    #: Environments built and driven in a child process the endpoint owns (``isolated_process_v1``,
    #: :mod:`mhs.bridge.sim_host`), per backend; the backend's ``backends`` entry runs in that process only.
    process_by_backend: Mapping[str, Mapping[str, Any]] = {}
    #: An environment that a factory function of the clone builds from a class outside the clone: ``native`` names the
    #: function, this ``{"returns": "package.module.Class", "ref": "path:LINE-END"}`` names the class it returns and
    #: cites the return statement (gate G7, :mod:`mhs.driver.factory_check`). None: ``native`` is the class.
    native_factory: Mapping[str, Any] | None = None

    @classmethod
    def _fill_model(cls, model: _model.DriverModel, instance: Any, problems: list[str]) -> None:
        ref = cls.action_space_ref
        parsed = parse_ref(ref) if isinstance(ref, str) else None
        if ref is not None and (parsed is None or safe_relpath(parsed.path) is None):
            problems.append(f"{cls.__qualname__}: action_space_ref must cite the upstream line that defines the "
                            f"action space as 'path/in/clone:LINE', got {ref!r}")
        if cls.native_factory is not None:
            from .factory_check import declaration_problems

            problems.extend(f"{cls.__qualname__}: {item}" for item in declaration_problems(cls.native_factory))
        super()._fill_model(model, instance, problems)
        if instance is not None and not problems:
            bridge = instance.inner
            remote_stop = bridge.estop_native
            if remote_stop is not None:
                # The declared remote stop of an asynchronous environment is the native e-stop path.
                model.estop = _model.EstopModel(None, str(remote_stop)[:128])
            allowed = set(bridge.reset_inputs())
            reset = model.binding("cap.world.reset.v1")
            if (reset is not None and "cap.world.reset.v1" not in dict(cls.actions or {})
                    and isinstance(reset.input_schema, dict)):
                properties = reset.input_schema.setdefault("properties", {})
                if "options" not in allowed:
                    properties.pop("options", None)   # never advertise options the native reset cannot take
                if "seed" not in allowed:
                    # A propertyless schema would inherit the class's undescribed fields, and the class output
                    # requires a seed: keep the input, say it is not used (the MuJoCo family's precedent).
                    properties["seed"] = {
                        "type": "integer", "minimum": 0,
                        "description": ("Accepted for the class contract; this environment's native reset takes "
                                        "no seed, so the value is not used and the output seed is 0")}
            notes = bridge.operating_notes()
            if notes:
                model.operating_notes = tuple(notes)
            if instance.inner.snapshot_supported:
                for binding in model.bindings:
                    if binding.exclusive is False:
                        problems.append("JSON checkpoints require exclusive world step/reset/seed bindings")
                    binding.exclusive = True
                model.params.append(_model.ParamModel("native_checkpoint", Field("object", description=(
                    "Bounded JSON native checkpoint plus adapter seed/timing metadata; included in world state hashes. "
                    "Does not establish hidden-state or RNG completeness."))))
            descriptor = instance.inner.timing_descriptor()
            if descriptor is not None:
                model.operating_notes = tuple(descriptor["notes"])
                model.binding("cap.world.step.v1").simulation_timing = copy.deepcopy(descriptor)
                if descriptor.get("reset_advances_physics") is True and model.binding("cap.world.reset.v1"):
                    # The reset receipt reports the physics ticks the reset integrated.
                    model.binding("cap.world.reset.v1").simulation_timing = copy.deepcopy(descriptor)
                model.param("tick").field = Field("integer", description=(
                    "Verified physics ticks since reset; a lower bound after a timing fault. "
                    "Per-command completed ticks and duration are in receipt timing notes."))

    @classmethod
    def _timing_configs(cls) -> Mapping[str, Mapping[str, Any]]:
        configs = cls.timing_by_backend
        if not isinstance(configs, Mapping) or any(
                key not in _model.BACKENDS or not isinstance(value, Mapping) for key, value in configs.items()):
            raise DriverDefinitionError("timing_by_backend must map known backends to timing objects")
        return configs

    @classmethod
    def _checkpoint_configs(cls) -> Mapping[str, Mapping[str, Any]]:
        from ..bridge.gym_checkpoint import JsonCheckpoint, checkpoint_opt_out
        configs = cls.checkpoint_by_backend
        if not isinstance(configs, Mapping) or any(
                key not in _model.BACKENDS or not isinstance(value, Mapping) for key, value in configs.items()):
            raise DriverDefinitionError("checkpoint_by_backend must map known backends to checkpoint profiles")
        try:
            for config in configs.values():
                if config.get("profile") == "none":
                    checkpoint_opt_out(config)
                else:
                    JsonCheckpoint.resolve(config)
        except ValueError as exc:
            raise DriverDefinitionError(f"invalid checkpoint_by_backend: {exc}") from exc
        return configs

    @classmethod
    def _async_configs(cls) -> Mapping[str, Mapping[str, Any]]:
        from ..bridge.gym_async import AsyncProfile, AsyncProfileError
        configs = cls.async_by_backend
        if not isinstance(configs, Mapping) or any(
                key not in _model.BACKENDS or not isinstance(value, Mapping) for key, value in configs.items()):
            raise DriverDefinitionError("async_by_backend must map known backends to asynchronous profiles")
        try:
            for config in configs.values():
                AsyncProfile.resolve(config)
        except AsyncProfileError as exc:
            raise DriverDefinitionError(f"invalid async_by_backend: {exc}") from exc
        return configs

    @classmethod
    def _process_configs(cls) -> Mapping[str, Mapping[str, Any]]:
        from ..bridge.sim_host import ProcessProfile, ProcessProfileError
        configs = cls.process_by_backend
        if not isinstance(configs, Mapping) or any(
                key not in _model.BACKENDS or not isinstance(value, Mapping) for key, value in configs.items()):
            raise DriverDefinitionError("process_by_backend must map known backends to isolated-process profiles")
        if "hardware" in configs:
            raise DriverDefinitionError("process_by_backend: a simulator has no hardware backend")
        backends = dict(cls.backends or {})
        try:
            for backend, config in configs.items():
                ProcessProfile.resolve(config)
                entry = backends.get(backend)
                if not isinstance(entry, str) or not entry.startswith("."):
                    raise ProcessProfileError(f"backends[{backend!r}] must be a package-relative '.module:attribute' "
                                              "that the host process imports and calls")
        except ProcessProfileError as exc:
            raise DriverDefinitionError(f"invalid process_by_backend: {exc}") from exc
        for name, declared in (("async_by_backend", cls.async_by_backend), ("dm_env_by_backend",
                                                                            cls.dm_env_by_backend),
                               ("timing_by_backend", cls.timing_by_backend)):
            if isinstance(declared, Mapping) and set(declared) & set(configs):
                raise DriverDefinitionError(f"process_by_backend does not combine with {name} on one backend")
        return configs

    @classmethod
    def _dm_env_configs(cls) -> Mapping[str, Mapping[str, Any]]:
        from ..bridge.dm_env_adapter import DmEnvError, DmEnvProfile
        configs = cls.dm_env_by_backend
        if not isinstance(configs, Mapping) or any(
                key not in _model.BACKENDS or not isinstance(value, Mapping) for key, value in configs.items()):
            raise DriverDefinitionError("dm_env_by_backend must map known backends to dm_env profiles")
        try:
            for config in configs.values():
                DmEnvProfile.resolve(config)
        except DmEnvError as exc:
            raise DriverDefinitionError(f"invalid dm_env_by_backend: {exc}") from exc
        return configs

    def _validate_backend_projection(self, backend: str | None) -> None:
        selected = self.backend if backend is None else backend
        checkpoints = type(self)._checkpoint_configs()
        if checkpoints.get(selected) != checkpoints.get(self.backend):
            raise DriverDefinitionError("checkpoint backends require a manifest from their own constructed instance")
        for configs, what in ((type(self)._async_configs(), "asynchronous"), (type(self)._dm_env_configs(), "dm_env"),
                              (type(self)._process_configs(), "isolated-process")):
            if configs.get(selected) != configs.get(self.backend):
                raise DriverDefinitionError(f"{what} backends require a manifest from their own constructed instance")
        configs = type(self)._timing_configs()
        if selected != self.backend and (selected in configs or self.backend in configs):
            raise DriverDefinitionError("timed backends require a manifest from their own constructed instance")

    def fidelity_for(self, backend: str | None) -> dict[str, Any]:
        self._validate_backend_projection(backend)
        out = super().fidelity_for(backend)
        if out.get("snapshot_restore") and not self.inner.snapshot_supported:
            raise DriverDefinitionError(
                "snapshot_restore=True requires checkpoint_by_backend for the selected backend; "
                "configure source-backed json_state_v1 methods covering native/wrapper/RNG state, "
                "or declare snapshot_restore=False and remove unsupported snapshot claims")
        opt_out = self.inner.checkpoint_opt_out_reason()
        if opt_out is not None:
            out["gaps"] = list(out.get("gaps") or [])
            gap = f"no protocol snapshots on this backend (explicit checkpoint opt-out): {opt_out}"
            if gap not in out["gaps"]:
                out["gaps"].append(gap)
        descriptor = self.inner.timing_descriptor()
        if descriptor is not None:
            if isinstance(out.get("timestep_ms"), bool) or out.get("timestep_ms") != descriptor["physics_timestep_ms"]:
                raise DriverDefinitionError("fidelity timestep_ms contradicts the resolved physics timestep")
            if out.get("realtime_factor") != 0 or out.get("clock") != "lockstep":
                raise DriverDefinitionError("physics_ticks_v1 requires lockstep fidelity with no wall-clock pacing")
            out["gaps"] = list(out.get("gaps") or [])
            if not any("no wall-clock pacing" in gap.lower() for gap in out["gaps"]):
                out["gaps"].append("no wall-clock pacing")
        return out

    def open_native(self) -> Any:
        type(self)._timing_configs()
        type(self)._checkpoint_configs()
        type(self)._async_configs()
        type(self)._dm_env_configs()
        processes = type(self)._process_configs()
        if self.backend in processes:
            # The backend entry is imported and called in the host process only, never here.
            from ..bridge.sim_host import ProcessHost, ProcessProfileError
            package = sys.modules.get(self._package or "")
            paths = list(getattr(package, "__path__", None) or [])
            try:
                host = ProcessHost(package_dir=paths[0] if paths else self.base_dir,
                                   entry=dict(type(self).backends)[self.backend], options=self.options,
                                   profile=processes[self.backend], label=f"{self.device_id}:{self.backend}")
            except ProcessProfileError as exc:
                raise DriverDefinitionError(f"the {self.backend} host cannot be built: {exc}") from exc
            self.__dict__["_process_host"] = host
            return host
        if self.backend in dict(type(self).backends or {}):
            return super().open_native()
        if self.backend == "hardware":
            raise DriverDefinitionError(f"{type(self).__name__} is a simulator; it has no hardware backend")
        return None  # GymnasiumBridge calls gymnasium.make(env_id)

    @classmethod
    def _describe_world_inputs(cls, binding: _model.BindingModel) -> None:
        super()._describe_world_inputs(binding)
        schema = binding.input_schema
        if binding.capability_id == "cap.world.step.v1" and isinstance(schema, dict) \
                and "action" in (schema.get("properties") or {}):
            # gymnasium step() always takes an action: a missing one is an input error, not a driver crash.
            schema["required"] = sorted(set(schema.get("required") or []) | {"action"})

    def make_bridge(self, native: Any) -> Any:
        from ..bridge.gymnasium import GymnasiumBridge

        cls = type(self)
        spec = {"kwargs": dict(cls.env_kwargs)} if cls.env_kwargs else None
        origin = None
        if native is not None:   # built by a backends entry, not by gymnasium.make(env_id)
            target = dict(cls.backends or {}).get(self.backend)
            name = target if isinstance(target, str) else getattr(target, "__qualname__", type(target).__name__)
            origin = f"the {self.backend} backend {name}"
        ref = cls.action_space_ref if isinstance(cls.action_space_ref, str) else None
        return GymnasiumBridge(env=native, env_id=cls.env_id, env_spec=spec, seed=cls.seed,
                               device_id=self.device_id, autoreset=cls.autoreset, max_ticks=cls.max_ticks,
                               env_origin=origin, action_space_ref=ref,
                               timing=copy.deepcopy(cls._timing_configs().get(self.backend)),
                               checkpoint=copy.deepcopy(cls._checkpoint_configs().get(self.backend)),
                               asynchronous=copy.deepcopy(cls._async_configs().get(self.backend)),
                               dm_env=copy.deepcopy(cls._dm_env_configs().get(self.backend)),
                               **self._process_bridge_options(native))

    def _process_bridge_options(self, native: Any) -> dict[str, Any]:
        """``process``/``host`` for a backend built in an isolated simulator host (nothing for any other backend)."""
        config = type(self)._process_configs().get(self.backend)
        if config is None:
            return {}
        from ..bridge.sim_host import ProcessHost
        host = self.__dict__.get("_process_host")
        if host is None and isinstance(native, ProcessHost):
            host = native   # passed to the constructor (a test): no recorder sits between the bridge and the host
        return {"process": copy.deepcopy(config), "host": host}

    def restore_admission(self, stop_changed=None):
        """Retain native checkpoint ownership across endpoint validation and rollback."""
        return self.inner.restore_admission(stop_changed)

    def validate_restore(self, snapshot: Any) -> dict[str, Any]:
        """Endpoint pre-effect checkpoint validation through the family wrapper."""
        return self.inner.validate_restore(snapshot)

    def _derived_fidelity(self) -> dict[str, Any]:
        bridge = self.inner
        dt = None
        try:
            dt = bridge._env_attr("dt")
        except Exception:  # noqa: BLE001
            dt = None
        timestep = float(dt) * 1000.0 if isinstance(dt, (int, float)) and not isinstance(dt, bool) and dt > 0 else 0
        descriptor = bridge.timing_descriptor()
        if descriptor is not None:
            timestep = descriptor["physics_timestep_ms"]
        snapshot = bool(bridge.snapshot_supported)
        seeded = "seed" in bridge.reset_inputs()
        return {
            "engine": f"gymnasium:{type(self).env_id}" if type(self).env_id else "gymnasium",
            "fidelity_level": type(self).fidelity_level,
            "determinism": ({"kind": "seeded", "seed_control": "parameter"} if seeded
                            else {"kind": "none", "seed_control": "none"}),
            "timestep_ms": timestep,
            "realtime_factor": 0,
            "clock": "lockstep",
            "reset": "full",
            "snapshot_restore": snapshot,
            "gaps": ["the environment is the system of record; no physical device is modelled"],
        }


class MujocoDriver(_SimDriver):
    """A MuJoCo model behind :class:`mhs.bridge.mujoco.MujocoBridge` (``cap.world.step/reset``).

    ``model_path`` (relative to the driver directory) or ``model_xml``
    selects the model; ``seed`` and ``max_ticks`` configure it.  The native
    is the ``mujoco`` module (``backends["fake"]`` may name a stand-in
    module); ``ctrl`` is bounded by the model's ``actuator_ctrlrange``.  An
    actuator the model gives no control range is ``operator_required``
    (:meth:`mhs.bridge.mujoco.MujocoBridge.action_limits`): such a package
    ships a ``site-limits.example.json`` that bounds it, and a deployment its
    own ``site-limits.json``.
    """

    family = "mujoco"
    # An empty schema would publish the class's undescribed fields (an empty input schema inherits the class's).
    _RESET_INPUTS = {
        "seed": {"type": "integer", "minimum": 0,
                 "description": "Accepted for the class contract; a MuJoCo reset restores the model defaults "
                                "(mj_resetData) and does not use a seed"},
    }
    model_path: str | None = None
    model_xml: str | None = None
    seed: int = 0
    max_ticks: int = 10_000
    fidelity_level: str = "F1"

    @classmethod
    def _fill_model(cls, model: _model.DriverModel, instance: Any, problems: list[str]) -> None:
        super()._fill_model(model, instance, problems)
        for binding in model.bindings:
            if binding.exclusive is False:
                problems.append("MuJoCo checkpoints require exclusive world step/reset bindings")
            binding.exclusive = True

    def validate_restore(self, snapshot: Any) -> dict[str, Any]:
        return self.inner.validate_restore(snapshot)

    def restore_admission(self, stop_changed: Any = None):
        return self.inner.restore_admission(stop_changed)

    @classmethod
    def _state_fields(cls) -> Mapping[str, Field]:
        # The fields MujocoBridge.world_state publishes (mhs/bridge/mujoco.py); gate G6 validates the state against them.
        return {
            "time_ms": Field("integer", unit="ms", description="Simulated time since the last reset"),
            "qpos": Field("array", items="number", description="Joint positions of the model (qpos)"),
            "qvel": Field("array", items="number", description="Joint velocities of the model (qvel)"),
            "ctrl": Field("array", items="number", description="Control vector last applied to the actuators (ctrl)"),
            "tick": Field("integer", unit="1", description="Integration steps since the last reset"),
            "timestep_ms": Field("number", unit="ms", nullable=True,
                                 description="Integration step of the model (null when the model states none)"),
            "seed": Field("integer", unit="1", description="Seed the bridge was configured with"),
            "native_checkpoint": Field("object", description=(
                "Declared native checkpoint. Integration profile restores the full native input vector; "
                "basic profile restores only advertised state plus actuator activation and exact native time. "
                "Neither profile certifies external callbacks, plugins, RNG or hardware fidelity."), properties={
                    "profile": Field("string", required=True, enum=["mujoco_integration_v1", "mujoco_basic_v1"]),
                    "engine_version": Field("string", required=True, max_length=100),
                    "signature": Field("integer", required=True),
                    "state_size": Field("integer", required=True),
                    "dimensions": Field("array", items="integer", length=4, required=True),
                    "values": Field("array", items="number", max_items=32768, required=False),
                    "time": Field("number", required=False),
                    "act": Field("array", items="number", max_items=32768, required=False),
                }),
        }

    def open_native(self) -> Any:
        if self.backend in dict(type(self).backends or {}):
            return super().open_native()
        if self.backend == "hardware":
            raise DriverDefinitionError(f"{type(self).__name__} is a simulator; it has no hardware backend")
        return None  # MujocoBridge imports mujoco

    def make_bridge(self, native: Any) -> Any:
        from ..bridge.mujoco import MujocoBridge

        cls = type(self)
        path = str(self.base_dir / cls.model_path) if cls.model_path else None
        return MujocoBridge(model_path=path, model_xml=cls.model_xml, model_name=self._model_name(), device_id=self.device_id,
                            seed=cls.seed, mujoco=native, max_ticks=cls.max_ticks)

    def _model_name(self) -> str | None:
        """The model file as its upstream clone names it (below the nearest git checkout), else as ``model_path`` does."""
        model_path = type(self).model_path
        if not model_path:
            return None
        resolved = (self.base_dir / model_path).resolve()
        for parent in resolved.parents:
            if (parent / ".git").exists():
                return resolved.relative_to(parent).as_posix()
        return Path(model_path).as_posix()

    def _derived_fidelity(self) -> dict[str, Any]:
        bridge = self.inner
        try:
            bridge._ensure_loaded()
        except Exception:  # noqa: BLE001 - reported by the model
            pass
        timestep_s = getattr(bridge, "_timestep_s", None)
        return {
            "engine": "mujoco",
            "fidelity_level": type(self).fidelity_level,
            "determinism": {"kind": "none", "seed_control": "none"},
            "timestep_ms": float(timestep_s) * 1000.0 if timestep_s else 0,
            "realtime_factor": 0,
            "clock": "lockstep",
            "reset": "full",
            "snapshot_restore": True,
            "gaps": ["contact and actuator parameters are those of the model file; not validated against hardware"],
        }


# Imported after _FamilyDriver is defined to keep the finite SiLA family separate.
from .sila2 import Sila2Driver

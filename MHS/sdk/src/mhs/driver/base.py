"""``Driver``: one decorated class per device, served by the unchanged OpenMHS runtime.

A Driver subclasses :class:`mhs.bridge.base.Bridge`, so :class:`mhs.server.MHSServer`
serves it like any bridge and owns every safety rule (plan 3.6): limits,
interlocks, the e-stop latch, permits, receipts and revisions.  The driver
only translates.  :mod:`mhs.driver.build` turns the class into the
``Device``/``Resource``/``Capability``/``SafetyEnvelope`` objects and the
reference file; this module is the runtime half.

Runtime contract (what a driver method may rely on and must do):

* Methods are ``def`` or ``async def``.  Coroutines run on the driver's one
  persistent event loop (:class:`mhs.bridge.base.AsyncRunner`), bounded by the
  call's deadline (or execution bound) and cancelled when the operation is
  cancelled or the device is e-stopped; ``Status``-like and
  ``concurrent.futures.Future`` returns are waited for the same way.  An
  ``async def`` must not block its loop.
* ``self.native`` is the backend object (``backends["fake"]`` or
  ``backends["hardware"]``), created on first use; the class attribute
  ``native`` stays the upstream symbol (``"pkg.module:Class"``).
* An action returns a dict, a scalar (wrapped into the class's single
  output field) or ``None``; a required ``sampled_at`` is stamped.  A setter
  may return the value actually applied.
* Outcomes are raised: ``mhs.signals.Cancelled`` (check ``self.cancelled()``
  in long sync loops), ``DriverFailed(code, message)`` for a failure the
  driver understands; any other exception becomes
  ``MHS.ADAPTER.SHIM_FAILED`` with a redacted message.
* ``@estop`` may run while an action is running: it must not wait for that
  action.  Stop-class and ``safe_state=True`` actions never take the driver
  lock either.
* Optional plain hooks: ``setup(self)`` runs once after the backend object
  is created, ``teardown(self)`` when the driver closes (both may be
  ``async``).  ``self.options`` holds the backend options, ``self.ctx`` the
  current call's context, ``self.backend`` the backend name.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
import functools
import importlib
import inspect
import sys
import threading
import types
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .. import canonical
from .. import signals as _signals
from .. import units as _units
from ..bridge.base import (
    Bridge,
    BridgeContext,
    MappingError,
    driver_failed,
    jsonable,
    make_mhs_error,
    unsupported,
)
from ..errors import MHSError
from . import model as _model

__all__ = ["Driver", "current_context"]

#: The BridgeContext of the call being served (a driver method reads it through ``self.ctx``).
_CURRENT: contextvars.ContextVar[BridgeContext | None] = contextvars.ContextVar("mhs_driver_ctx", default=None)
_UNSET: Any = object()
#: Bridge contract methods a decorated driver must not override (the decorators declare them).
CONTRACT_METHODS = frozenset({"call", "read", "write", "estop", "reset", "interlocks", "safety_status",
                              "snapshot", "restore", "capabilities", "resources", "close", "describe"})


def current_context() -> BridgeContext | None:
    """The :class:`~mhs.bridge.base.BridgeContext` of the driver call running on this thread or task."""
    return _CURRENT.get()


async def _with_context(awaitable: Any, ctx: BridgeContext | None) -> Any:
    _CURRENT.set(ctx)
    return await awaitable


def _resolve_symbol(spec: str, package: str | None) -> Any:
    """``module:attr`` (``.module:attr`` relative to ``package``) -> the object; ``module`` alone -> the module."""
    module_name, _, attribute = spec.partition(":")
    if module_name.startswith("."):
        if not package:
            raise make_mhs_error("MHS.ADAPTER.MANIFEST_INVALID",
                                 f"relative backend {spec!r} needs the driver to be loaded as a package",
                                 {"retryable": False})
        module = importlib.import_module(module_name, package)
    else:
        module = importlib.import_module(module_name)
    target: Any = module
    for part in [item for item in attribute.split(".") if item]:
        target = getattr(target, part)
    return target


class _NativeAttr:
    """``Driver.native``: the upstream symbol on the class, the backend object on an instance."""

    def __get__(self, instance: Any, owner: type) -> Any:
        if instance is None:
            return getattr(owner, "_native_symbol", None)
        return instance._get_native()

    def __set__(self, instance: Any, value: Any) -> None:
        instance._set_native(value)


class _SafeStateAttr:
    """``Driver.safe_state``: the declared description on the class, the Bridge hook on an instance."""

    def __get__(self, instance: Any, owner: type) -> Any:
        if instance is None:
            return getattr(owner, "_safe_state_text", None)
        return functools.partial(type(instance)._run_safe_state, instance)


class Driver(Bridge):
    """Base class of a per-repo OpenMHS driver (see the module docstring and ``docs/driver-authoring.md``).

    Class attributes (declarations):

    ``device_id`` (short name or ``mhs://`` id), ``device_kind`` (catalogue
    resource kind), ``resource_id`` (default ``"main"``), ``mode``
    (``"hardware"`` or ``"simulated"``), ``risk`` (``R0``..``R3``; never below
    the class floors), ``native`` (``"pkg.module:Class"``, checked against the
    pinned clone, never imported), ``backends`` (``{"hardware": ".native:connect",
    "fake": ".fake:FakeX"}``; the names are ``hardware``, ``fake`` and ``sim``
    only, and a ``fake``/``sim`` entry may not be the hardware entry point or
    use the ``.native`` module), ``tags``, ``facts``, ``safe_state`` (one
    sentence), ``estop_physical_ref`` (where an independent hardware e-stop
    is documented; a hardware driver at R2 or above needs it or an
    ``@action(..., safe_state=True)``, SAFE-045), ``estop_latency_ms``,
    ``estop_terminal`` (one sentence: why the native stop cannot be undone
    without a new endpoint, for example a stop that closes the native session
    for good; the endpoint then refuses every reset after an e-stop with that
    reason, CORE-087), ``watchdog_ms``, ``display_name``, ``vendor``,
    ``model``, ``upstream`` (``{repo, commit}``), ``fidelity`` (a simulated
    driver's contract).  An explicit re-enable after a reset is declared on
    its action (``@action(..., reenable=True)``, CORE-086).

    ``watchdog_ms`` declares a *device-side* (native) watchdog: the OpenMHS
    runtime does not implement one, so the class must cite it with a
    ``Fact`` whose text mentions the watchdog (``vendor_doc`` or
    ``upstream_code`` with ``ref``).
    """

    bridge_kind = "driver"
    bridge_id = "mhs.driver"

    # declarations ------------------------------------------------------------
    device_id: Any = None
    device_kind: Any = None
    resource_id: str = "main"
    resource_title: str | None = None
    mode: str = "hardware"
    risk: str = "R0"
    native: Any = _NativeAttr()
    _native_symbol: str | None = None
    backends: Mapping[str, Any] = {}
    tags: Sequence[str] = ()
    facts: Sequence[Any] = ()
    safe_state: Any = _SafeStateAttr()
    _safe_state_text: str | None = None
    estop_physical_ref: str | None = None
    estop_latency_ms: int | None = None
    estop_terminal: str | None = None
    watchdog_ms: int | None = None
    display_name: str | None = None
    vendor: str | None = None
    model: str | None = None
    upstream: Mapping[str, str] | None = None
    fidelity: Mapping[str, Any] | None = None
    models: Sequence[str] = ()

    # runtime bounds (milliseconds) ---------------------------------------------
    #: bound of a native ``@estop`` (it raises an unknown outcome after this)
    estop_timeout_ms: int = 5000
    #: bound of one ``@read`` getter / ``@interlock`` reading / ``@reset``
    read_timeout_ms: int = 5000
    interlock_timeout_ms: int = 1000
    reset_timeout_ms: int = 10000
    #: bound of creating the backend object (an async factory is awaited)
    open_timeout_ms: int = 30000

    #: Family base classes set this: their runtime is their inner bridge, not decorators.
    _family_base = False

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        own = vars(cls)
        if "native" in own and not isinstance(own["native"], _NativeAttr):
            cls._native_symbol = own["native"]
            cls.native = _NativeAttr()
        if "safe_state" in own and not isinstance(own["safe_state"], _SafeStateAttr):
            # A method named safe_state would replace the Bridge hook: driver_model() reports it.
            cls._safe_state_text = own["safe_state"]
            cls.safe_state = _SafeStateAttr()
        cls._model_cache = None
        if cls._uses_decorators():
            # Contract methods the class body itself defines (reported by driver_model(); estop is
            # replaced below, so it must be recorded before that).
            cls._mhs_contract_overrides = tuple(
                name for name in sorted(CONTRACT_METHODS)
                if name in own and callable(own[name]) and own[name] not in (Driver._estop_impl, Bridge.estop))
            # Only a class with an @estop method overrides Bridge.estop: the runtime then reports a native
            # stop path; without one it reports a software-only latch (never "engaged" with nothing called).
            # Resolved like driver_model(): a subclass that redefines the decorated method without @estop
            # (or sets it to None) has no native stop.
            cls.estop = Driver._estop_impl if _has_role(cls, "EstopRole") else Bridge.estop

    @classmethod
    def _uses_decorators(cls) -> bool:
        return not any(getattr(klass, "_family_base", False) for klass in cls.__mro__ if klass is not Driver)

    # -- model -------------------------------------------------------------------
    @classmethod
    def driver_model(cls) -> _model.DriverModel:
        """The resolved model of this class (cached); raises :class:`DriverDefinitionError`."""
        cached = cls.__dict__.get("_model_cache")
        if cached is not None:
            return cached
        safe_state = cls._safe_state_text
        problems_extra: list[str] = []
        if callable(safe_state) and not isinstance(safe_state, str):
            problems_extra.append("safe_state is a description string, not a method; a safe-state routine is an "
                                  "@action(..., safe_state=True)")
            safe_state = None
        overrides = sorted({name for klass in cls.__mro__ for name in vars(klass).get("_mhs_contract_overrides", ())})
        problems_extra.extend(
            f"{name}() is part of the Bridge contract and must not be overridden; declare parameters, actions "
            "and safety with the mhs.driver decorators instead" for name in overrides)
        model = _model.model_for_class(cls, stop=(Driver, Bridge), reserved=_RESERVED,
                                       native_symbol=cls._native_symbol, safe_state=safe_state)
        model.problems[:0] = problems_extra
        _model.finish(model)
        cls._model_cache = model
        return model

    def _driver_model(self) -> _model.DriverModel:
        """The model this instance serves (family drivers build it from their configuration)."""
        return type(self).driver_model()

    # -- construction ------------------------------------------------------------
    def __init__(self, *, backend: str = "fake", native: Any = _UNSET, base_dir: str | Path | None = None,
                 options: Mapping[str, Any] | None = None, device_id: str | None = None,
                 native_wrapper: Callable[[Any], Any] | None = None):
        """``backend`` names an entry of ``backends``; ``native`` passes the backend object directly
        (tests, recorders; ``setup()`` is then not run); ``options`` are keyword arguments of the backend
        factory; ``base_dir`` is the driver package directory (default: the directory of the module
        defining the class); ``native_wrapper`` is applied to the object the backend factory creates,
        before ``setup()`` runs (the acceptance gate wraps it in a :class:`mhs.testing.Recorder`)."""
        if not isinstance(backend, str) or not backend:
            raise TypeError("backend must be a backend name such as 'fake' or 'hardware'")
        if backend not in _model.BACKENDS:
            raise ValueError(f"backend {backend!r} is not one of {list(_model.BACKENDS)} (only 'hardware' drives "
                             "the device; 'fake' and 'sim' are served as mode simulated)")
        super().__init__(device_id=device_id)
        self.backend = backend
        self.options = dict(options or {})
        module = sys.modules.get(type(self).__module__)
        if base_dir is not None:
            self.base_dir = Path(base_dir)
        else:
            path = getattr(module, "__file__", None)
            self.base_dir = Path(path).resolve().parent if path else Path.cwd()
        self._package = getattr(module, "__package__", None) or None
        if native_wrapper is not None and not callable(native_wrapper):
            raise TypeError("native_wrapper must be a callable taking the backend object")
        self._native_wrapper = native_wrapper
        self._native_lock = threading.Lock()
        self._native_value: Any = None
        self._native_ready = False
        if native is not _UNSET:
            self._native_value, self._native_ready = native, True
        self._written: dict[str, Any] = {}
        self._safe_state_achieved: bool | None = None
        self._model = self._driver_model()
        if self._model.estop is None:
            # The served model has no native stop: the runtime must see the Bridge default (a software-only
            # latch), whatever the class attribute says, so an e-stop is never reported "engaged" with nothing
            # called.
            self.estop = types.MethodType(Bridge.estop, self)
        if device_id is None:
            from .build import served_device_id  # local import: build imports this module

            self.device_id = served_device_id(self._model, backend)

    # -- native ------------------------------------------------------------------
    @property
    def is_hardware(self) -> bool:
        """True when this instance drives real hardware (``backend == "hardware"`` of a hardware driver)."""
        return self.backend == "hardware" and self._model.mode == "hardware"

    def _backend_factory(self, backend: str) -> Any:
        declared = dict(type(self).backends or {})
        if backend not in declared:
            raise make_mhs_error(
                "MHS.DEVICE.NOT_READY", f"{type(self).__name__} declares no {backend!r} backend "
                f"(backends: {sorted(declared)})", {"retryable": False})
        target = declared[backend]
        if callable(target) and not isinstance(target, str):
            return target
        try:
            return _resolve_symbol(str(target), self._package)
        except MHSError:
            raise
        except Exception as exc:  # noqa: BLE001 - an import failure is a not-ready device
            raise make_mhs_error("MHS.DEVICE.NOT_READY", f"backend {backend!r} ({target}) cannot be loaded "
                                 f"({type(exc).__name__})", {"retryable": False}) from exc

    def open_native(self) -> Any:
        """Create the backend object (``backends[self.backend](**options)``) and run ``setup()``."""
        factory = self._backend_factory(self.backend)
        value = factory(**self.options) if callable(factory) else factory
        if inspect.isawaitable(value):
            value = self.async_runner.run(value, timeout_ms=self.open_timeout_ms, label=f"{self.backend} backend")
        return value

    def _get_native(self) -> Any:
        if self._native_ready:
            return self._native_value
        with self._native_lock:
            if not self._native_ready:
                self.ensure_open()
                value = self.open_native()
                if value is not None and self._native_wrapper is not None:
                    value = self._native_wrapper(value)
                self._native_value, self._native_ready = value, True
                setup = getattr(self, "setup", None)
                if callable(setup):
                    self._call_hook(setup, label="setup", timeout_ms=self.open_timeout_ms)
        return self._native_value

    def _set_native(self, value: Any) -> None:
        with self._native_lock:
            self._native_value, self._native_ready = value, True

    def open(self) -> "Driver":
        """Create the backend object now (otherwise it is created on first use); returns ``self``."""
        self._get_native()
        return self

    # -- call context ------------------------------------------------------------
    @property
    def ctx(self) -> BridgeContext | None:
        """The context of the call being served (``None`` outside a call)."""
        return _CURRENT.get()

    def cancelled(self) -> bool:
        """True when the running operation was cancelled (or the device e-stopped)."""
        ctx = _CURRENT.get()
        return bool(ctx is not None and ctx.cancelled())

    def check_cancelled(self) -> None:
        """Raise :class:`mhs.signals.Cancelled` when :meth:`cancelled`."""
        if self.cancelled():
            raise _signals.Cancelled("the operation was cancelled")

    def _call_hook(self, fn: Callable[..., Any], *, label: str, timeout_ms: int,
                   kwargs: Mapping[str, Any] | None = None, ctx: BridgeContext | None = None) -> Any:
        token = _CURRENT.set(ctx)
        try:
            value = fn(**dict(kwargs or {}))
            if inspect.isawaitable(value) and asyncio.iscoroutine(value):
                value = _with_context(value, ctx)
            if (inspect.isawaitable(value) or isinstance(value, concurrent.futures.Future)
                    or _is_status(value)):
                value = self.resolve_native(value, ctx, timeout_ms=timeout_ms, label=label)
            return value
        finally:
            _CURRENT.reset(token)

    def _invoke(self, fn: Callable[..., Any], kwargs: Mapping[str, Any], ctx: BridgeContext, label: str) -> Any:
        token = _CURRENT.set(ctx)
        try:
            value = fn(**kwargs)
            if asyncio.iscoroutine(value):
                value = _with_context(value, ctx)
            if inspect.isawaitable(value) or isinstance(value, concurrent.futures.Future) or _is_status(value):
                value = self.resolve_native(value, ctx, label=label)
            return value
        finally:
            _CURRENT.reset(token)

    # -- Bridge contract: capabilities -------------------------------------------
    def call(self, capability_id: str, args: Mapping[str, Any] | None = None, ctx: Any = None) -> Any:
        self.ensure_open()
        context = BridgeContext.coerce(ctx)
        payload = dict(args or {})
        if capability_id == _model.CONFIGURE and self._model.writable:
            return self.write(context.resource or self._model.resource_id, payload, context)
        binding = self._model.binding(str(capability_id))
        if binding is None or binding.attr is None:
            raise unsupported(capability_id)
        if self._model.extra_resources and context.resource is not None \
                and context.resource != self._model.resource_of(binding):
            # A composed driver serves each capability on its declared resource only (the server resolves the
            # binding by (capability_id, resource) first; this refuses a direct call naming another resource).
            raise make_mhs_error(
                "MHS.CAPABILITY.NOT_BOUND", f"{capability_id} is bound to resource "
                f"{self._model.resource_of(binding)!r}, not {context.resource!r}", {"retryable": False})
        if context.cancelled():
            raise _signals.Cancelled("the operation was cancelled before the native call")
        kwargs = self._action_kwargs(binding, payload, context)
        method = getattr(self, binding.attr)
        label = f"{type(self).__name__}.{binding.attr}"
        self._get_native()
        if binding.takes_lock:
            epoch = self.estop_epoch  # taken before waiting for the lock
            with self._lock:
                self._refuse_if_estopped(epoch, f"{binding.capability_id} ({binding.attr})")
                if context.cancelled():
                    raise _signals.Cancelled("the operation was cancelled while it waited for the device")
                result = self._invoke(method, kwargs, context, label)
        else:
            result = self._invoke(method, kwargs, context, label)
        return self._output(binding, result)

    def _action_kwargs(self, binding: _model.BindingModel, payload: dict[str, Any], ctx: BridgeContext) -> dict[str, Any]:
        signature = binding.signature
        if signature is not None and not signature.var_kwargs:
            stray = sorted(key for key in payload if key not in signature.names)
            if stray:
                raise make_mhs_error(
                    "MHS.CAPABILITY.INPUT_INVALID",
                    f"{binding.name} does not take {stray} (accepted: {list(signature.names)})",
                    {"retryable": False, "details": {"capability_id": binding.capability_id, "fields": stray}})
        kwargs = dict(payload)
        for name, (unit, native_unit, delta) in binding.native_units.items():
            if name in kwargs:
                kwargs[name] = _convert(kwargs[name], unit, native_unit, delta, f"{binding.name}.{name}")
        if signature is not None and signature.wants_ctx:
            kwargs["ctx"] = ctx
        return kwargs

    def _output(self, binding: _model.BindingModel, value: Any) -> dict[str, Any]:
        if value is None:
            out: dict[str, Any] = {}
        elif isinstance(value, Mapping):
            out = dict(value)
        elif binding.principal_output is not None:
            out = {binding.principal_output: value}
        else:
            raise driver_failed(
                "MHS.CAPABILITY.OUTPUT_INVALID",
                f"{binding.name} returned a {type(value).__name__}, but {binding.capability_id} has several output "
                "fields; return a dict")
        if binding.stamps_sampled_at and "sampled_at" not in out:
            out["sampled_at"] = canonical.now_rfc3339()
        try:
            return jsonable(out)
        except MappingError as exc:
            raise driver_failed("MHS.CAPABILITY.OUTPUT_INVALID",
                                f"{binding.name} returned a value that is not JSON ({exc})") from exc

    def capabilities(self) -> list[dict[str, Any]]:
        return [binding.manifest(self._model.resource_of(binding)) for binding in self._model.bindings]

    def resources(self) -> list[dict[str, Any]]:
        return self._model.resources_manifest()

    # -- Bridge contract: parameters ---------------------------------------------
    def read(self, resource_id: str, fields: Sequence[str] | None = None, ctx: Any = None) -> Any:
        if resource_id != self._model.resource_id:
            if self._model.extra_resource(resource_id) is not None:
                return {}  # an extra resource has no parameters: its state is empty, read without native I/O
            raise unsupported(resource_id, kind="resource")
        context = BridgeContext.coerce(ctx) if ctx is not None else None
        wanted = set(fields) if fields else None
        state: dict[str, Any] = {}
        for param in self._model.params:
            if wanted is not None and param.name not in wanted:
                continue
            if param.getter is not None:
                value = self._read_param(param, context)
            elif param.name in self._written:
                value = self._written[param.name]
            else:
                continue
            if value is not None:
                state[param.name] = value
        try:
            return jsonable(state)
        except MappingError as exc:
            raise make_mhs_error("MHS.RESOURCE.STATE_INVALID", f"a parameter value is not JSON ({exc})",
                                 {"retryable": False}) from exc

    def _read_param(self, param: _model.ParamModel, ctx: BridgeContext | None) -> Any:
        getter = getattr(self, str(param.getter))
        kwargs = {"ctx": ctx} if param.getter_signature is not None and param.getter_signature.wants_ctx else {}
        try:
            self._get_native()
            value = self._call_hook(getter, label=f"read {param.name}", timeout_ms=self.read_timeout_ms,
                                    kwargs=kwargs, ctx=ctx)
        except MHSError:
            raise
        except BaseException as exc:  # noqa: BLE001 - every outcome of a read becomes a typed error
            raise _as_mhs_error(exc, f"read of {param.name!r}") from exc
        if value is not None and param.field.native_unit is not None:
            value = _convert(value, param.field.native_unit, str(param.field.unit), param.field.delta,
                             f"read {param.name}", direction="output")
        return value

    def write(self, resource_id: str, patch: Mapping[str, Any], ctx: Any = None) -> Any:
        self.ensure_open()
        if resource_id != self._model.resource_id:
            if self._model.extra_resource(resource_id) is not None:
                raise make_mhs_error("MHS.RESOURCE.NOT_WRITABLE", f"resource {resource_id!r} has no parameters "
                                     "(parameters belong to the main resource)", {"retryable": False})
            raise unsupported(resource_id, kind="resource")
        context = BridgeContext.coerce(ctx)
        patch = dict(patch or {})
        writable = {param.name: param for param in self._model.writable}
        unknown = sorted(key for key in patch if self._model.param(key) is None)
        if unknown:
            raise make_mhs_error("MHS.RESOURCE.FIELD_UNKNOWN", f"unknown parameter(s) {unknown}",
                                 {"retryable": False, "details": {"fields": unknown}})
        read_only = sorted(key for key in patch if key not in writable)
        if read_only:
            raise make_mhs_error("MHS.RESOURCE.NOT_WRITABLE", f"read-only parameter(s) {read_only}",
                                 {"retryable": False, "details": {"fields": read_only}})
        self._get_native()
        epoch = self.estop_epoch
        with self._lock:
            self._refuse_if_estopped(epoch, "parameter write")
            applied: dict[str, Any] = {}
            for name, param in writable.items():
                if name not in patch:
                    continue
                if context.cancelled():
                    raise _signals.Cancelled("the write was cancelled")
                applied[name] = self._write_param(param, patch[name], context)
        try:
            return {"applied": jsonable(applied)}
        except MappingError as exc:
            raise driver_failed("MHS.CAPABILITY.OUTPUT_INVALID", f"an applied value is not JSON ({exc})") from exc

    def _write_param(self, param: _model.ParamModel, value: Any, ctx: BridgeContext) -> Any:
        native_value = value
        if param.field.native_unit is not None:
            native_value = _convert(value, str(param.field.unit), param.field.native_unit, param.field.delta,
                                    f"write {param.name}")
        setter = getattr(self, str(param.setter))
        kwargs: dict[str, Any] = {}
        signature = param.setter_signature
        if signature is not None and signature.params:
            kwargs[signature.params[0][0]] = native_value
        if signature is not None and signature.wants_ctx:
            kwargs["ctx"] = ctx
        result = self._invoke(setter, kwargs, ctx, f"{type(self).__name__}.{param.setter}")
        if result is None or isinstance(result, (Mapping, list, tuple)):
            applied = value
        elif param.field.native_unit is not None:
            applied = _convert(result, param.field.native_unit, str(param.field.unit), param.field.delta,
                               f"write {param.name}", direction="output")
        else:
            applied = result
        self._written[param.name] = applied
        return applied

    # -- Bridge contract: safety -------------------------------------------------
    @property
    def estop_native(self) -> str | None:
        estop = self._model.estop
        return estop.native if estop is not None else None

    @property
    def reset_hook(self) -> str | None:
        """The decorated ``@reset`` method this driver runs on a reset, or None.

        The endpoint's start-up check refuses a device that declares a
        re-enable and runs such a hook (SAFE-042, CORE-086).  A family
        driver has none: its reset is a ``safety_bindings.reset`` entry.
        """
        return self._model.reset_attr

    def _estop_impl(self, reason: str = "", ctx: Any = None) -> Any:
        """The native e-stop (installed as ``estop`` on classes with an ``@estop`` method)."""
        self._engage_estop()
        estop = self._model.estop
        if estop is None or estop.attr is None:  # pragma: no cover - __init__ installs Bridge.estop then
            # Fail closed: no native stop ran, so the runtime must not report "engaged".
            raise driver_failed("MHS.ADAPTER.SHIM_FAILED", f"{type(self).__name__} declares no @estop method; "
                                "no native stop ran")
        method = getattr(self, estop.attr)
        kwargs = {"reason": reason} if estop.wants_reason else {}
        self._get_native()
        self._call_hook(method, label=f"estop {estop.attr}", timeout_ms=self.estop_timeout_ms, kwargs=kwargs,
                        ctx=BridgeContext.coerce(ctx) if ctx is not None else None)
        return {"estop": "engaged", "native": estop.native}

    def interlocks(self) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for interlock in self._model.interlocks:
            state = "unknown"
            if interlock.attr is not None:
                try:
                    self._get_native()
                    value = self._call_hook(getattr(self, interlock.attr), label=f"interlock {interlock.id}",
                                            timeout_ms=self.interlock_timeout_ms)
                except BaseException:  # noqa: BLE001 - an unreadable interlock is unknown (blocks)
                    value = None
                if value is True:
                    state = "closed"
                elif value is False:
                    state = "open"
                elif value in ("closed", "open", "unknown"):
                    state = str(value)
            out.append({"id": interlock.id, "state": state, "description": interlock.description or ""})
        return out

    def reset(self, ctx: Any = None) -> Any:
        attr = self._model.reset_attr
        if attr is None:
            return {}
        self._get_native()
        self._call_hook(getattr(self, attr), label=f"reset {attr}", timeout_ms=self.reset_timeout_ms,
                        ctx=BridgeContext.coerce(ctx) if ctx is not None else None)
        return {"reset": True}

    def _run_safe_state(self, ctx: Any = None) -> Any:
        """``Bridge.safe_state``: run every ``safe_state=True`` action with an empty input."""
        achieved = True
        for binding in self._model.bindings:
            if not binding.safe_state:
                continue
            try:
                self.call(binding.capability_id, {}, ctx)
            except BaseException:  # noqa: BLE001 - every action is attempted
                achieved = False
        self._safe_state_achieved = achieved if self._model.achieved_by else None
        return {"achieved": achieved} if self._model.achieved_by else {}

    def safety_status(self) -> dict[str, Any]:
        status: dict[str, Any] = {"estop": {"native": self.estop_native}}
        if (self._model.mode in ("hardware", "hybrid") and self._model.risk != "R0"
                and self._model.estop is None
                and not self._model.achieved_by
                and (self._model.writable or self._model.reset_attr is not None
                     or any(binding.effective.verb != "read" for binding in self._model.bindings))):
            # Serving a physical-control contract on a fake/sim backend does not
            # create a stop that it lacks. R0 measurement commands may mutate
            # acquisition state without physical actuation (SAFE-007); their
            # protocol verb alone does not imply a required native stop.
            # The server's software latch only
            # fences future admissions; already sent native work may continue.
            status["safe_state"] = {
                "description": "No acknowledged stop is declared for the hardware control surface",
                "achieved": False,
            }
        return status

    # -- lifecycle ----------------------------------------------------------------
    def close(self) -> None:
        if self.closed:
            return
        teardown = getattr(self, "teardown", None)
        if callable(teardown) and self._native_ready:
            try:
                self._call_hook(teardown, label="teardown", timeout_ms=self.read_timeout_ms)
            except Exception:  # noqa: BLE001 - closing never fails
                pass
        super().close()

    def describe(self) -> dict[str, Any]:
        out = super().describe()
        out.update({"driver": type(self).__qualname__, "backend": self.backend, "mode": self._model.mode,
                    "native": type(self)._native_symbol})
        return out


def _has_role(cls: type, role_name: str) -> bool:
    """True when a member of ``cls`` carries ``role_name``, resolved as ``driver_model()`` resolves members:
    the most derived definition of each name wins (an undecorated override hides the decorated base method)."""
    seen: set[str] = set()
    for klass in cls.__mro__:
        if klass in (Driver, Bridge, object):
            continue
        for name, value in vars(klass).items():
            if name in seen:
                continue
            seen.add(name)
            roles = getattr(value, _model.ROLE_ATTR, None) if callable(value) else None
            if roles and any(type(role).__name__ == role_name for role in roles):
                return True
    return False


def _is_status(value: Any) -> bool:
    from ..bridge.base import is_status_like

    return is_status_like(value)


def _convert(value: Any, src: str, dst: str, delta: bool, what: str, *, direction: str = "input") -> Any:
    def one(item: Any) -> Any:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise TypeError(item)
        return _units.convert(item, src, dst, delta=delta)

    try:
        if isinstance(value, (list, tuple)):
            return [one(item) for item in value]
        return one(value)
    except (TypeError, _units.UnitError) as exc:
        code = "MHS.CAPABILITY.INPUT_INVALID" if direction == "input" else "MHS.CAPABILITY.OUTPUT_INVALID"
        if direction == "input":
            raise make_mhs_error(code, f"{what}: cannot convert {value!r} from {src} to {dst}",
                                 {"retryable": False}) from exc
        raise driver_failed(code, f"{what}: cannot convert the native value from {src} to {dst}") from exc


def _as_mhs_error(exc: BaseException, what: str) -> MHSError:
    """A typed error for a failure outside a capability call (reads have no receipt to carry a signal)."""
    if isinstance(exc, _signals.Cancelled):
        return make_mhs_error("MHS.OUTCOME.ABORTED", f"{what} was cancelled", {"retryable": True})
    if isinstance(exc, _signals.DriverFailed):
        return driver_failed(exc.code, exc.message or what)
    if isinstance(exc, _signals.Busy):
        return make_mhs_error("MHS.DEVICE.BUSY", f"{what}: the device is busy", {"retryable": True})
    if isinstance(exc, _signals.OutcomeUnknown):
        return make_mhs_error("MHS.OUTCOME.UNKNOWN", f"{what} did not answer in time", {"retryable": False})
    return driver_failed("MHS.ADAPTER.SHIM_FAILED", f"{what} failed ({type(exc).__name__})")


#: Names a decorated method may not take (every attribute of the Driver base class).
_RESERVED = frozenset(name for name in dir(Driver) if not name.startswith("__")) | {"setup", "teardown"}

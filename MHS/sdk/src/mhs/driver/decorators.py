"""The Driver decorators: ``read``, ``write``, ``action``, ``estop``, ``interlock``, ``reset``.

Each decorator records a *role* on the method (``fn.__mhs_roles__``) and
returns the method unchanged, so it stays an ordinary method the driver can
call itself.  :class:`mhs.driver.Driver` collects the roles of a class when it
is built; one method has exactly one role.

* ``@read(name, unit=...)`` -- a read-only parameter: the method returns its
  current value (``self``-only signature).  Served by ``mhs.resource.read``.
* ``@write(name, unit=..., limit=...)`` -- a writable parameter: the method
  receives the new value (``def set_x(self, value)``).  Served by
  ``mhs.resource.write`` through ``cap.device.configure.v1``.  A parameter with
  both a ``@read`` and a ``@write`` method is read back from the native; one
  with only ``@write`` reports the last value written.
* ``@action(cap=...)`` or ``@action(name="x-cap.<owner>.<name>.v1", ...)`` -- a
  capability: the method's parameters are the input fields (for a catalogue
  class they must be class fields; for an extension each needs a
  :class:`~mhs.driver.Field` in ``input``).
* ``@estop`` -- the native emergency stop (``def stop(self)`` or
  ``def stop(self, reason)``); the runtime latches first and calls it after.
* ``@interlock(id, blocks=[...])`` -- returns ``True`` when the interlock is
  closed (safe), ``False`` when open; anything else (or an exception) is
  ``unknown``, which blocks like open.
* ``@reset`` -- optional native recovery run by an accepted
  ``mhs.safety.reset`` (for example clearing a controller's error latch).

Methods may be ``def`` or ``async def``.  A method may also take a keyword
parameter named ``ctx`` (the :class:`mhs.bridge.base.BridgeContext` of the
call); it is never an input field.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from .spec import Action, DriverDefinitionError, Field, json_type, limits_of

__all__ = ["action", "estop", "interlock", "read", "reset", "write"]

ROLE_ATTR = "__mhs_roles__"
_RISKS = ("R0", "R1", "R2", "R3")


@dataclass
class ParamRole:
    """``@read`` / ``@write``."""

    kind: str                     # "read" | "write"
    name: str | None
    field: Field
    risk: str | None = None


@dataclass
class ActionRole:
    """``@action``."""

    capability_id: str
    declared: Action
    name: str | None = None


@dataclass
class EstopRole:
    native: str | None = None
    latency_ms: int | None = None


@dataclass
class InterlockRole:
    id: str
    description: str | None = None
    blocks: tuple[str, ...] | None = None
    source: str = "hardware"
    reset_exempt: bool = False


@dataclass
class ResetRole:
    pass


@dataclass
class Signature:
    """What a decorated method accepts (``self`` and ``ctx`` excluded from ``params``)."""

    params: tuple[tuple[str, bool], ...] = ()   # (name, has a default)
    var_kwargs: bool = False
    var_args: bool = False
    wants_ctx: bool = False
    is_async: bool = False
    positional_only: tuple[str, ...] = field(default_factory=tuple)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(name for name, _default in self.params)

    @property
    def required(self) -> tuple[str, ...]:
        return tuple(name for name, has_default in self.params if not has_default)


def signature_of(fn: Callable[..., Any]) -> Signature:
    """The input parameters of ``fn`` (``self`` and ``ctx`` excluded)."""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):  # pragma: no cover - builtins
        return Signature()
    params: list[tuple[str, bool]] = []
    var_kwargs = var_args = wants_ctx = False
    positional_only: list[str] = []
    for index, (name, param) in enumerate(sig.parameters.items()):
        if index == 0 and name == "self":
            continue
        if param.kind is inspect.Parameter.VAR_KEYWORD:
            var_kwargs = True
            continue
        if param.kind is inspect.Parameter.VAR_POSITIONAL:
            var_args = True
            continue
        if name == "ctx":
            wants_ctx = True
            continue
        if param.kind is inspect.Parameter.POSITIONAL_ONLY:
            positional_only.append(name)
        params.append((name, param.default is not inspect.Parameter.empty))
    return Signature(params=tuple(params), var_kwargs=var_kwargs, var_args=var_args, wants_ctx=wants_ctx,
                     is_async=inspect.iscoroutinefunction(fn), positional_only=tuple(positional_only))


def _attach(fn: Any, role: Any, decorator: str) -> Any:
    if isinstance(fn, (staticmethod, classmethod, property)):
        raise DriverDefinitionError(f"@{decorator} decorates a plain instance method, not a "
                                    f"{type(fn).__name__}")
    if not callable(fn):
        raise DriverDefinitionError(f"@{decorator} decorates a method, got {fn!r}")
    roles = list(getattr(fn, ROLE_ATTR, ()))
    roles.append(role)
    try:
        setattr(fn, ROLE_ATTR, tuple(roles))
    except AttributeError as exc:  # pragma: no cover - builtins
        raise DriverDefinitionError(f"@{decorator} cannot decorate {fn!r}") from exc
    return fn


def _check_risk(risk: Any, what: str) -> None:
    if risk is not None and risk not in _RISKS:
        raise DriverDefinitionError(f"{what}: risk must be one of {list(_RISKS)}, got {risk!r}")


def _param_field(what: str, *, unit: Any, native_unit: Any, description: Any, type: Any, items: Any,
                 length: Any, enum: Any, properties: Any, limit: Any = None, delta: bool = False) -> Field:
    if isinstance(type, Field):
        if any(value is not None for value in (unit, native_unit, items, length, enum, properties)):
            raise DriverDefinitionError(f"{what}: give either type=Field(...) or the unit/items/... keywords")
        base = type
        extra = limits_of(limit, what)
        if extra:
            base = Field(base.type, unit=base.unit, native_unit=base.native_unit, description=description or base.description,
                         limit=list(base.limits) + list(extra), items=base.items, length=base.length,
                         min_items=base.min_items, max_items=base.max_items, enum=base.enum,
                         properties=base.properties, max_length=base.max_length, pattern=base.pattern,
                         delta=base.delta or delta)
        return base
    return Field(json_type(type, what), unit=unit, native_unit=native_unit, description=description, limit=limit,
                 items=items, length=length, enum=enum, properties=properties, delta=delta)


def read(name: str | None = None, *, unit: str | None = None, description: str | None = None,
         type: Any = "number", items: Any = None, length: int | None = None, enum: Sequence[Any] | None = None,
         properties: Mapping[str, Field] | None = None, native_unit: str | None = None,
         delta: bool = False) -> Callable[[Any], Any]:
    """Declare a read-only parameter served by the decorated getter (``def get(self)``).

    ``name`` defaults to the method name; ``type`` is a JSON type (default
    ``"number"``) or a :class:`Field`; ``unit`` a UCUM code; ``native_unit``
    converts the getter's value into ``unit``.
    """
    if callable(name) and not isinstance(name, str):
        raise DriverDefinitionError("use @read(...) with parentheses: @read('name', unit=...)")

    def decorate(fn: Any) -> Any:
        what = f"@read({name or getattr(fn, '__name__', '?')!r})"
        role = ParamRole("read", name, _param_field(what, unit=unit, native_unit=native_unit, description=description,
                                                     type=type, items=items, length=length, enum=enum,
                                                     properties=properties, delta=delta))
        return _attach(fn, role, "read")

    return decorate


def write(name: str | None = None, *, unit: str | None = None, limit: Any = None, description: str | None = None,
          risk: str | None = None, type: Any = "number", items: Any = None, length: int | None = None,
          enum: Sequence[Any] | None = None, properties: Mapping[str, Field] | None = None,
          native_unit: str | None = None, delta: bool = False) -> Callable[[Any], Any]:
    """Declare a writable parameter whose setter is the decorated method (``def set_x(self, value)``).

    ``limit`` is a :class:`Limit` (or a list of them, each with a relative
    ``path`` for array elements or object members) or
    ``Limit.operator_required(reason)``; ``risk`` raises the device risk
    class; ``native_unit`` converts the value into the native's unit before
    the setter runs.  The setter may return the value actually applied
    (device rounding); ``None`` means the value was applied as given.
    """
    if callable(name) and not isinstance(name, str):
        raise DriverDefinitionError("use @write(...) with parentheses: @write('name', unit=..., limit=...)")
    _check_risk(risk, f"@write({name!r})")

    def decorate(fn: Any) -> Any:
        what = f"@write({name or getattr(fn, '__name__', '?')!r})"
        role = ParamRole("write", name, _param_field(what, unit=unit, native_unit=native_unit, description=description,
                                                      type=type, items=items, length=length, enum=enum,
                                                      properties=properties, limit=limit, delta=delta), risk)
        return _attach(fn, role, "write")

    return decorate


def action(cap: str | None = None, *, name: str | None = None, input: Mapping[str, Any] | None = None,
           output: Mapping[str, Any] | None = None, limits: Any = None, long_running: bool = False,
           cancellable: bool | None = None, max_duration_ms: int | None = None, risk: str | None = None,
           examples: Sequence[Mapping[str, Any]] | None = None, description: str | None = None,
           verb: str | None = None, safe_state: bool = False, exclusive: bool | None = None,
           requires_permit: bool = False, action_name: str | None = None,
           resource: str | None = None, reenable: bool = False) -> Callable[[Any], Any]:
    """Declare a capability served by the decorated method.

    ``cap`` is a catalogue class id (``cap.thermal.setpoint.v1``; the
    method's parameters must be class fields, every required class field
    must be a parameter, and ``input`` may refine fields with units, limits
    and descriptions) or an extension id ``x-cap.<owner>.<name>.v1`` (also
    accepted as ``name=``), whose ``input``/``output`` fields are the inline
    schema.  ``limits`` maps absolute limit paths (``position.x``) to
    :class:`Limit` objects.  ``long_running=True`` needs ``max_duration_ms``
    unless the class declares one.  ``safe_state=True`` adds the action to
    ``safe_state.achieved_by`` (it must accept an empty input).
    ``reenable=True`` declares the action as the device's explicit re-enable
    after a safety reset (``safety.estop.reenable``, SAFE-042's new start
    command, CORE-086): the reset never runs it, it is refused while the
    device is latched, and it must accept an empty input.
    ``action_name`` overrides the reference-file name (default: the method
    name).  ``resource`` binds the action to one of the class's
    ``extra_resources`` (default: the main resource).  The method returns a
    dict, a scalar (wrapped into the single output field) or ``None``.
    """
    if callable(cap) and not isinstance(cap, str):
        raise DriverDefinitionError("use @action(...) with a capability id: @action(cap='cap.x.y.v1')")
    capability_id = cap
    if name is not None:
        if capability_id is not None and capability_id != name:
            raise DriverDefinitionError(f"@action: give the capability id once (cap={cap!r}, name={name!r})")
        capability_id = name
    if not isinstance(capability_id, str) or not capability_id:
        raise DriverDefinitionError("@action needs cap='cap.<domain>.<name>.vN' or name='x-cap.<owner>.<name>.vN'")
    _check_risk(risk, f"@action({capability_id!r})")
    declared = Action(name=action_name, input=input, output=output, limits=limits, long_running=long_running,
                      cancellable=cancellable, max_duration_ms=max_duration_ms, risk=risk, examples=examples,
                      description=description, verb=verb, safe_state=safe_state, exclusive=exclusive,
                      requires_permit=requires_permit, resource=resource, reenable=reenable)

    def decorate(fn: Any) -> Any:
        return _attach(fn, ActionRole(capability_id, declared, action_name), "action")

    return decorate


def estop(fn: Any = None, *, native: str | None = None, latency_ms: int | None = None) -> Any:
    """Declare the native emergency stop: ``@estop`` or ``@estop(native="emergency_stop", latency_ms=200)``.

    ``native`` names the upstream stop call for the reference file (default:
    the method name); ``latency_ms`` is the declared stop latency, which is
    also the runtime's budget before it runs the safe-state actions.
    """
    if latency_ms is not None and (not isinstance(latency_ms, int) or isinstance(latency_ms, bool) or latency_ms < 0):
        raise DriverDefinitionError(f"@estop latency_ms must be a non-negative integer, got {latency_ms!r}")
    if native is not None and (not isinstance(native, str) or not native.strip() or len(native) > 128):
        raise DriverDefinitionError("@estop native must name the native stop (at most 128 characters)")
    role = EstopRole(native, latency_ms)
    if fn is not None:
        return _attach(fn, role, "estop")

    def decorate(method: Any) -> Any:
        return _attach(method, role, "estop")

    return decorate


def interlock(id: str, *, description: str | None = None, blocks: Sequence[str] | None = None,
              source: str = "hardware", reset_exempt: bool = False) -> Callable[[Any], Any]:
    """Declare an interlock read by the decorated method (``True`` = closed / safe).

    ``blocks`` lists the capability ids (or ``cap.<domain>.*`` patterns) the
    interlock gates -- ``cap.device.configure.v1`` for parameter writes;
    omit it for a purely informative interlock.  ``reset_exempt=True`` lets
    ``mhs.safety.reset`` proceed while this interlock is open.
    """
    if not isinstance(id, str) or not id.strip() or len(id) > 64:
        raise DriverDefinitionError(f"@interlock id must be a short non-empty string, got {id!r}")
    if source not in ("hardware", "software", "operator", "simulated"):
        raise DriverDefinitionError(f"@interlock source must be hardware, software, operator or simulated, got {source!r}")
    if blocks is not None:
        if isinstance(blocks, str) or not blocks or not all(isinstance(item, str) and item for item in blocks):
            raise DriverDefinitionError("@interlock blocks must be a non-empty list of capability ids or patterns")
    role = InterlockRole(id, description, tuple(blocks) if blocks is not None else None, source, bool(reset_exempt))

    def decorate(fn: Any) -> Any:
        return _attach(fn, role, "interlock")

    return decorate


def reset(fn: Any = None) -> Any:
    """Declare the native recovery an accepted ``mhs.safety.reset`` runs (``@reset``)."""
    if fn is not None:
        return _attach(fn, ResetRole(), "reset")

    def decorate(method: Any) -> Any:
        return _attach(method, ResetRole(), "reset")

    return decorate


"""OpenMHS bridge runtime base: the Bridge contract and the declarative map engine.

A bridge adapts one equipment family (a Python object, a Gymnasium environment,
a MuJoCo model, a serial or SCPI instrument, a recorded evidence bundle) to the
contract plane.  Adapters supply a *declarative* map; the bridge applies field
mapping, unit conversion, enumeration mapping, constant injection, limit
checks and error-code mapping at the boundary.  Anything the map does not
declare is refused rather than guessed: an endpoint never invents a native
call.

The Bridge contract (what the server relies on)
-----------------------------------------------

* ``call(capability_id, args, ctx)`` returns the capability **output** as a
  JSON-able ``dict``.  It never returns an ``{"output": ..., "state": ...}``
  wrapper: whatever ``call`` returns *is* the receipt output.
* State is exposed only through ``read(resource_id, fields, ctx)`` (the server
  hashes and revisions it; a bridge never advances a revision or makes a
  receipt).
* Outcomes other than success are signalled by raising, never by an output
  field: :class:`mhs.signals.Cancelled` (the call stopped because
  ``ctx.cancel_event`` was set), :class:`mhs.signals.DriverFailed` (a failure
  the bridge understands, with a registered code), :class:`mhs.signals.Busy`
  (refused, nothing actuated) and :class:`mhs.signals.OutcomeUnknown` (for
  example a native timeout: the effect may have happened).  Refusals before
  the native call (input mapping, limits) raise ``MHSError``; any other
  exception -- including a native exception no error rule maps -- becomes
  ``MHS.ADAPTER.SHIM_FAILED`` with a redacted message.  The helpers
  :func:`driver_failed`, :func:`busy` and :func:`outcome_unknown` build
  signals that are also ``MHSError`` instances, so every server revision
  classifies them identically.
* ``estop(reason, ctx)`` may be called concurrently from another thread while
  a call is running and must not take a lock held by a running call; it
  brings the device to its stop state and returns promptly.  Every ``estop``
  advances :attr:`Bridge.estop_epoch` before it touches the device: an
  effectful call that was already waiting for the bridge lock (or a
  serial/SCPI transaction lock) when the e-stop fired is refused with
  ``MHS.SAFETY.ESTOP_ENGAGED`` once it gets the lock, so no queued actuation
  follows an e-stop.  Line-protocol bridges re-check the epoch under the
  short wire lock they share with the e-stop command, so a request that had
  already passed the lock is either on the wire before the e-stop command or
  refused.  (The python-object bridge cannot order a native call it has just
  released against the e-stop native: the native API must tolerate an e-stop
  arriving while, or just before, a call starts.)  Calls made after
  ``estop`` returned run normally: the server owns the latch (and runs the
  safe-state actions, which are exempt from it).  ``reset``, ``interlocks``
  (``[{id, state: closed|open|unknown, description}]``; anything not
  recognised is ``unknown``, and ``reset`` is refused unless every interlock
  is ``closed``) and ``safety_status`` are optional hooks; the server owns
  enforcement.
* Long or awaitable natives are bounded by ``min(timeout_ms,
  ctx.remaining_ms())`` and observe ``ctx.cancel_event``.  ``remaining_ms``
  reads ``ctx.extra["deadline_at"]`` (monotonic seconds) when the server sets
  it, else ``ctx.deadline_ms``.  When the bound expires the native is
  abandoned -- a coroutine is cancelled, a sync native is left on its daemon
  thread -- and the call raises an unknown outcome.  A server running a
  ``long_running`` capability must therefore pass the execution bound
  (``max_duration_ms``), not the response deadline, as the context deadline.
  :class:`AsyncRunner` gives each bridge one persistent event-loop thread for
  coroutines, and :meth:`Bridge.resolve_native` awaits awaitables,
  ``concurrent.futures.Future`` objects and Status-like objects
  (``wait(timeout)`` or ``done``/``success``) with the same bound.

Units come from :mod:`mhs.units` (``%`` is a ratio of 0.01, compound UCUM codes
are derived and checked) and every clamp goes through :mod:`mhs.limits`: an
input outside a declared clamp or envelope is rejected with
``MHS.SAFETY.ENVELOPE_VIOLATION`` and is never silently truncated.  A clamp is
checked after the rule's unit conversion, so a clamp/envelope ``unit`` must be
the conversion's ``to`` unit (a mismatch is a load error, never an implicit
conversion).  Input values -- typed or not -- may not be NaN or infinite (they
never reach a native or a command template); parse kind ``bool`` is strict
(``1``/``ON``/``TRUE`` or the declared ``true`` token, ``0``/``OFF``/``FALSE``
or the declared ``false`` token; any other reply is a parse error).

Field paths: a path that is exactly ``input``, ``output``, ``args``, ``result``
or ``$`` is the whole value; one ``input.``/``output.``/``args.`` prefix is
stripped, after which only ``$`` is the whole value again (``output.$``).
``input.output`` and ``output.result`` are ordinary fields.

Bridge modules are libraries, not launchers: ``python -m mhs.bridge.<x>``
prints ``use: mhs serve <driver-dir|mhs-adapter.json>`` and exits 2.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import importlib
import inspect
import math
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, MutableMapping, Sequence

from mhs import errors as _errors
from mhs import limits as _limits
from mhs import signals
from mhs import units as _units

__all__ = [
    "AsyncRunner",
    "Bridge",
    "BridgeBusy",
    "BridgeContext",
    "BridgeError",
    "BridgeFailed",
    "BridgeOutcomeUnknown",
    "ErrorMap",
    "FieldMapping",
    "MappingError",
    "USAGE",
    "UnitError",
    "busy",
    "call_bounded",
    "convert_unit",
    "driver_failed",
    "format_command",
    "get_path",
    "is_awaitable",
    "is_status_like",
    "jsonable",
    "main",
    "make_mhs_error",
    "outcome_unknown",
    "parse_text",
    "resolve_native",
    "unsupported",
    "wait_future",
    "wait_status",
]

_MISSING = object()

#: What every ``python -m mhs.bridge.<x>`` prints before exiting 2.
USAGE = "use: mhs serve <driver-dir|mhs-adapter.json>"


class _Wildcard:
    """Marker token for ``[*]`` in a field path."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "[*]"


_WILDCARD = _Wildcard()


class _Fanout(list):
    """List produced by a ``[*]`` read, so transforms apply per element."""


# ---------------------------------------------------------------------------
# errors and signals
# ---------------------------------------------------------------------------


class BridgeError(Exception):
    """Fallback error type used only when ``mhs.errors`` cannot be imported.

    It mirrors the documented MHSError surface (``code``, ``message``,
    ``data``).
    """

    def __init__(self, code: str, message: str = "", data: Mapping[str, Any] | None = None):
        self.code = code
        self.message = message or code
        self.data = dict(data or {})
        super().__init__(f"{self.code}: {self.message}")


def make_mhs_error(
    code: str,
    message: str = "",
    data: Mapping[str, Any] | None = None,
) -> Exception:
    """Construct the SDK's canonical error object (``MHSError``)."""

    payload = dict(data or {})
    try:
        return _errors.MHSError(code, message or None, payload)
    except Exception:  # pragma: no cover - defensive
        return BridgeError(code, message, payload)


def unsupported(capability_or_resource: str, kind: str = "capability") -> Exception:
    """The error raised when an adapter did not declare a native call."""

    return make_mhs_error(
        "MHS.CAPABILITY.NOT_BOUND",
        f"bridge does not expose the requested {kind} {capability_or_resource!r}",
        {
            "retryable": False,
            "remediation": "Use a capability/resource declared by this bridge or update the adapter map.",
        },
    )


class MappingError(ValueError):
    """A declarative mapping spec is malformed or cannot be applied."""


#: Re-exported from :mod:`mhs.units` (compatibility name of the bridge layer).
UnitError = _units.UnitError


def _signal_details(exc: Any) -> dict[str, Any]:
    out = dict((exc.data or {}).get("details") or {}) if isinstance(getattr(exc, "data", None), Mapping) else {}
    native = getattr(exc, "native_code", None)
    if native is not None:
        out["native_code"] = native if isinstance(native, (str, int, float, bool)) else str(native)
    return out


class BridgeFailed(signals.DriverFailed, _errors.MHSError):
    """:class:`mhs.signals.DriverFailed` that is also an ``MHSError``."""

    def __init__(self, code: str, message: str = "", data: Mapping[str, Any] | None = None, *,
                 native_code: Any = None):
        _errors.MHSError.__init__(self, code, message or None, data)
        if not _errors.is_normative_code(self.code):
            raise ValueError(f"DriverFailed code {code!r} is not a registered MHS error code")
        self.native_code = native_code
        self.retryable = bool(self.data.get("retryable", _errors.retryable(self.code)))

    def details(self) -> dict[str, Any]:
        return _signal_details(self)


class BridgeBusy(signals.Busy, _errors.MHSError):
    """:class:`mhs.signals.Busy` that is also an ``MHSError`` (``MHS.DEVICE.BUSY``)."""

    def __init__(self, message: str = "", data: Mapping[str, Any] | None = None, *,
                 retry_after_ms: int | None = None, native_code: Any = None):
        payload = dict(data or {})
        payload.setdefault("retryable", True)
        _errors.MHSError.__init__(self, "MHS.DEVICE.BUSY", message or "device is busy", payload)
        self.retry_after_ms = retry_after_ms
        self.native_code = native_code
        self.retryable = True

    def details(self) -> dict[str, Any]:
        out = _signal_details(self)
        if self.retry_after_ms is not None:
            out["retry_after_ms"] = int(self.retry_after_ms)
        return out


class BridgeOutcomeUnknown(signals.OutcomeUnknown, _errors.MHSError):
    """:class:`mhs.signals.OutcomeUnknown` that is also an ``MHSError`` (not retryable)."""

    def __init__(self, message: str = "", data: Mapping[str, Any] | None = None, *, native_code: Any = None):
        payload = dict(data or {})
        payload["retryable"] = False
        _errors.MHSError.__init__(self, "MHS.OUTCOME.UNKNOWN", message or "native outcome is unknown", payload)
        self.native_code = native_code
        self.retryable = False

    def details(self) -> dict[str, Any]:
        return _signal_details(self)


def driver_failed(code: str, message: str = "", *, details: Mapping[str, Any] | None = None,
                  retryable: bool | None = None, native_code: Any = None) -> Exception:
    """A failure signal for ``code``: Busy for ``MHS.DEVICE.BUSY``, otherwise DriverFailed.

    Unregistered codes (which ``DriverFailed`` refuses) fall back to a plain
    ``MHSError`` so a legacy map can never turn a failure into a crash.
    """

    normalized = _errors.normalize_code(str(code))
    data: dict[str, Any] = {}
    if details:
        data["details"] = dict(details)
    if retryable is not None:
        data["retryable"] = bool(retryable)
    if normalized == "MHS.DEVICE.BUSY":
        return BridgeBusy(message, data, native_code=native_code)
    if normalized == "MHS.OUTCOME.UNKNOWN":
        return BridgeOutcomeUnknown(message, data, native_code=native_code)
    if _errors.is_normative_code(normalized):
        return BridgeFailed(normalized, message, data, native_code=native_code)
    return make_mhs_error(str(code), message, data)


def busy(message: str = "", *, retry_after_ms: int | None = None, details: Mapping[str, Any] | None = None) -> Exception:
    return BridgeBusy(message, {"details": dict(details)} if details else None, retry_after_ms=retry_after_ms)


def outcome_unknown(message: str = "", *, details: Mapping[str, Any] | None = None) -> Exception:
    return BridgeOutcomeUnknown(message, {"details": dict(details)} if details else None)


# ---------------------------------------------------------------------------
# unit conversion (mhs.units; CAP-022)
# ---------------------------------------------------------------------------


def convert_unit(value: float, from_unit: str, to_unit: str, *, delta: bool = False) -> float:
    """Convert ``value`` between two UCUM codes (re-export of :mod:`mhs.units`).

    ``%`` is a ratio of 0.01; compound codes (``m/s``, ``N.m``, ``uL/s``) are
    derived; ``delta=True`` converts a temperature difference (no offset).
    Unknown codes and dimension mismatches raise :class:`UnitError`.
    """

    if from_unit == to_unit:
        return value
    return _units.convert(value, from_unit, to_unit, delta=delta)


#: The codes of the former local bridge table (kept for compatibility; the
#: factors below are derived from :mod:`mhs.units`, not a second table).
_LEGACY_UNIT_CODES = (
    "m", "mm", "cm", "um", "nm", "s", "ms", "us", "min", "h", "rad", "mrad", "deg",
    "L", "dL", "mL", "uL", "nL", "kg", "g", "mg", "K", "Cel", "Pa", "kPa", "MPa", "bar",
    "V", "mV", "A", "mA", "Hz", "kHz", "N", "mN", "%", "1",
)


def _legacy_unit_view() -> dict[str, tuple[str, float]]:
    view: dict[str, tuple[str, float]] = {}
    for code in _LEGACY_UNIT_CODES:
        parsed = _units.parse(code)
        view[code] = (parsed.dimension, float(parsed.factor))
    return view


#: Deprecated read-only view ``{code: (dimension, factor to SI)}`` derived from
#: :mod:`mhs.units`; use ``mhs.units`` directly.
_UNITS: dict[str, tuple[str, float]] = _legacy_unit_view()


def _unit_pair(spec: Any) -> tuple[str, str]:
    if isinstance(spec, Mapping):
        try:
            return str(spec["from"]), str(spec["to"])
        except KeyError as exc:
            raise MappingError("unit mapping requires {'from': unit, 'to': unit}") from exc
    if isinstance(spec, (list, tuple)) and len(spec) == 2:
        return str(spec[0]), str(spec[1])
    raise MappingError("unit mapping requires [from_unit, to_unit]")


def _unit_spec(spec: Any) -> dict[str, Any]:
    """Compile the canonical unit form ``{"from","to","factor"|"offset"}``.

    ``from`` and ``to`` are always required (ADPT-023).  The conversion is
    derived by :mod:`mhs.units`; an explicit factor or offset must agree with
    it (relative tolerance 1e-9), so a binding can never declare a wrong
    conversion.  An explicit ``offset: 0`` between two absolute temperature
    scales declares a temperature *difference* (no Kelvin offset).  Codes
    outside the UCUM subset keep the ADPT-021 fallback: they convert only with
    an explicit factor and/or offset.
    """

    if not isinstance(spec, Mapping):
        raise MappingError("unit transform must be an object with 'from' and 'to'")
    unknown = set(spec) - {"from", "to", "factor", "offset"}
    if unknown:
        raise MappingError(f"unknown unit transform keys: {sorted(unknown)}")
    if "from" not in spec or "to" not in spec:
        raise MappingError("unit transform requires explicit 'from' and 'to' UCUM codes")
    from_unit, to_unit = str(spec["from"]), str(spec["to"])
    if not from_unit or not to_unit:
        raise MappingError("unit transform requires non-empty 'from' and 'to' UCUM codes")
    factor = spec.get("factor")
    offset = spec.get("offset")
    for label, value in (("factor", factor), ("offset", offset)):
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise MappingError(f"unit {label} must be a number")
        if isinstance(value, float) and not math.isfinite(value):
            raise MappingError(f"unit {label} must be finite")
    try:
        derived_factor, derived_offset = _units.conversion(from_unit, to_unit)
        if offset is not None and float(offset) == 0.0 and derived_offset != 0.0:
            # an explicit zero offset between absolute scales: a difference
            derived_factor, derived_offset = _units.conversion(from_unit, to_unit, delta=True)
    except _units.UnknownUnitError as exc:
        if from_unit == to_unit:
            derived_factor, derived_offset = 1.0, 0.0
        elif factor is None and offset is None:
            raise MappingError(
                f"cannot derive a conversion for {from_unit!r}->{to_unit!r}; "
                "an explicit factor or offset is required (ADPT-021)"
            ) from exc
        else:
            # A custom code outside the UCUM subset: the binding declares the
            # conversion explicitly, which is the contract ADPT-021 asks for.
            compiled: dict[str, Any] = {"from": from_unit, "to": to_unit,
                                        "factor": 1.0 if factor is None else float(factor)}
            if offset is not None:
                compiled["offset"] = float(offset)
            return compiled
    except _units.UnitError as exc:
        raise MappingError(f"invalid unit transform: {exc}") from exc
    for label, declared, derived in (("factor", factor, derived_factor), ("offset", offset, derived_offset)):
        if declared is None:
            continue
        tolerance = 1e-12 if derived == 0 else 0.0
        if not math.isclose(float(declared), float(derived), rel_tol=1e-9, abs_tol=tolerance):
            raise MappingError(
                f"unit {label} {float(declared)!r} contradicts {from_unit!r}->{to_unit!r} "
                f"(expected {float(derived)!r})"
            )
    result: dict[str, Any] = {"from": from_unit, "to": to_unit, "factor": float(derived_factor)}
    if derived_offset:
        result["offset"] = float(derived_offset)
    return result


def _convert_value(value: Any, unit: Mapping[str, Any]) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MappingError(f"unit conversion requires a number, got {type(value).__name__}")
    return float(value) * float(unit["factor"]) + float(unit.get("offset", 0.0))


# ---------------------------------------------------------------------------
# JSON-safe conversion
# ---------------------------------------------------------------------------


def jsonable(value: Any, *, depth: int = 0) -> Any:
    """Convert a native value into a JSON-serialisable one, strictly.

    ``numpy`` arrays and scalars are converted through ``tolist()``/``item()``
    when available (they are never imported here).  Anything else that is not
    JSON data is refused rather than silently stringified.
    """

    if depth > 12:
        raise MappingError("value nesting is too deep to serialise")
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise MappingError("NaN/Infinity is not valid MHS JSON")
        return value
    if isinstance(value, (list, tuple)):
        return [jsonable(item, depth=depth + 1) for item in value]
    if isinstance(value, Mapping):
        return {str(key): jsonable(item, depth=depth + 1) for key, item in value.items()}
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        try:
            return jsonable(tolist(), depth=depth + 1)
        except MappingError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise MappingError(f"cannot serialise array-like value: {exc}") from exc
    raise MappingError(f"cannot serialise native value of type {type(value).__name__}")


# ---------------------------------------------------------------------------
# field paths
# ---------------------------------------------------------------------------


def _tokenize(path: str) -> list[Any]:
    tokens: list[Any] = []
    buf = ""
    i = 0
    while i < len(path):
        char = path[i]
        if char == ".":
            if buf:
                tokens.append(buf)
                buf = ""
            i += 1
        elif char == "[":
            if buf:
                tokens.append(buf)
                buf = ""
            end = path.find("]", i)
            if end < 0:
                raise MappingError(f"unterminated index in field path {path!r}")
            index = path[i + 1 : end].strip()
            if index == "*":
                tokens.append(_WILDCARD)
            else:
                try:
                    tokens.append(int(index))
                except ValueError as exc:
                    raise MappingError(f"non-integer index in field path {path!r}") from exc
            i = end + 1
        else:
            buf += char
            i += 1
    if buf:
        tokens.append(buf)
    return tokens


def _read_tokens(current: Any, tokens: Sequence[Any]) -> Any:
    if not tokens:
        return current
    token, rest = tokens[0], tokens[1:]
    if token is _WILDCARD:
        if isinstance(current, (str, bytes, Mapping)) or not isinstance(current, (list, tuple)):
            raise MappingError("wildcard [*] can only fan out over an array")
        return _Fanout([_read_tokens(item, rest) for item in current])
    if isinstance(token, int):
        current = current[token]
    elif isinstance(current, Mapping):
        current = current[token]
    else:
        current = getattr(current, token)
    return _read_tokens(current, rest)


#: Root words: a path that is exactly one of these names the whole value
#: (``output`` is the raw native return of a call).
_ROOT_WORDS = ("", "$", "input", "output", "args", "result")
#: Root prefixes, stripped once.  After a prefix only ``$`` (or nothing) names
#: the whole value again (``output.$``); every other word -- ``output``,
#: ``result``, ``args`` and ``input`` included -- is an ordinary field name, so
#: ``input.output`` is ``input["output"]``.  ``result.`` and ``$.`` are not
#: prefixes: ``result.x`` reads ``obj["result"]["x"]`` (as in 0.8).
_ROOT_PREFIXES = ("input.", "output.", "args.")
_ROOT_AFTER_PREFIX = ("", "$")


def get_path(obj: Any, path: str, default: Any = _MISSING) -> Any:
    """Read ``a.b[0].c`` from nested dicts/objects, with an optional default.

    ``[*]`` fans out over every element of an array (returning a list, one entry
    per element), so ``input.joints[*]`` maps a whole joint vector.  A ``[n]``
    index selects one element.  A path that is exactly ``input``, ``output``,
    ``result``, ``args`` or ``$`` names the value itself; one leading
    ``input.``/``output.``/``args.`` prefix is stripped, after which only ``$``
    names the value again -- ``output.$`` maps a scalar native return, while
    ``input.output`` and ``output.result`` are ordinary fields.
    """

    if path in _ROOT_WORDS:
        return obj
    for prefix in _ROOT_PREFIXES:
        if path.startswith(prefix):
            path = path[len(prefix) :]
            if path in _ROOT_AFTER_PREFIX:
                return obj
            break
    try:
        return _read_tokens(obj, _tokenize(path))
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        if default is not _MISSING:
            return default
        raise MappingError(f"field path {path!r} is absent") from exc


def _write_tokens(current: Any, tokens: Sequence[Any], value: Any) -> None:
    if not tokens:
        raise MappingError("cannot write to an empty field path")
    token, rest = tokens[0], tokens[1:]
    if token is _WILDCARD:
        if isinstance(current, (str, bytes, Mapping)) or not isinstance(current, (list, tuple)):
            raise MappingError("wildcard [*] can only fan out over an array")
        for item in current:
            _write_tokens(item, rest, value)
        return
    if not rest:
        current[token] = value
        return
    if isinstance(token, int):
        _write_tokens(current[token], rest, value)
    else:
        _write_tokens(current.setdefault(token, {}), rest, value)


def set_path(obj: MutableMapping[str, Any], path: str, value: Any) -> None:
    _write_tokens(obj, _tokenize(path), value)


# ---------------------------------------------------------------------------
# declarative field mapping
# ---------------------------------------------------------------------------

_RULE_KEYS = {
    "from",
    "value",
    "const",
    "default",
    "required",
    "unit",
    "units",
    "enum",
    "enum_map",
    "map",
    "clamp",
    "type",
    "scale",
    "offset",
    "description",
    "unsupported",
    "reason",
    "enforce_clamp",
    "envelope",
}

_ENUM_KEYS = ("enum", "enum_map", "map")
_TYPE_ALIASES = {
    "int": "integer",
    "integer": "integer",
    "float": "number",
    "number": "number",
    "str": "string",
    "string": "string",
    "bool": "boolean",
    "boolean": "boolean",
    "list": "array",
    "array": "array",
    "dict": "object",
    "object": "object",
}
_CLAMP_KEYS = {"min", "max", "envelope", "limits", "unit", "reason"}
_ENVELOPE_KEYS = {"min", "max", "unit", "reason"}
#: The one-field schema a clamp is compiled against (mhs.limits).
_CLAMP_SCHEMA = {"type": "object", "properties": {"value": {"type": "number"}}}


def _coerce_type(value: Any, type_name: str, target: str) -> Any:
    """Enforce the binding's declared JSON-ish type (canonical ``type`` key)."""

    if type_name == "integer":
        if isinstance(value, bool):
            raise MappingError(f"value {value!r} for {target!r} is not an integer")
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if not math.isfinite(value) or not value.is_integer():
                raise MappingError(f"value {value!r} for {target!r} is not an integer")
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip(), 10)
            except ValueError as exc:
                raise MappingError(f"value {value!r} for {target!r} is not an integer") from exc
        raise MappingError(f"value {value!r} for {target!r} is not an integer")
    if type_name == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            if isinstance(value, str):
                try:
                    value = float(value)
                except ValueError as exc:
                    raise MappingError(f"value {value!r} for {target!r} is not a number") from exc
            else:
                raise MappingError(f"value {value!r} for {target!r} is not a number")
        if not math.isfinite(float(value)):
            raise MappingError(f"value {value!r} for {target!r} is not finite")
        return value
    if type_name == "string":
        if isinstance(value, (Mapping, list, tuple)):
            raise MappingError(f"value {value!r} for {target!r} is not a string")
        return str(value)
    if type_name == "boolean":
        if not isinstance(value, bool):
            raise MappingError(f"value {value!r} for {target!r} is not a boolean")
        return value
    if type_name == "array":
        if not isinstance(value, (list, tuple)):
            raise MappingError(f"value {value!r} for {target!r} is not an array")
        return list(value)
    if type_name == "object":
        if not isinstance(value, Mapping):
            raise MappingError(f"value {value!r} for {target!r} is not an object")
        return dict(value)
    raise MappingError(f"unknown type {type_name!r} for {target!r}")


def _bound_rule(spec: Mapping[str, Any], label: str, target: str) -> dict[str, Any] | None:
    unknown = set(spec) - _ENVELOPE_KEYS
    if unknown:
        raise MappingError(f"unknown {label} keys for {target!r}: {sorted(unknown)}")
    rule = {key: spec[key] for key in ("min", "max", "unit", "reason") if spec.get(key) is not None}
    if "min" not in rule and "max" not in rule:
        return None
    return rule


def compile_clamp(target: str, clamp: Mapping[str, Any] | None,
                  envelope: Mapping[str, Any] | None = None, *,
                  unit: str | None = None) -> _limits.EffectiveLimits:
    """Compile a binding clamp (and an optional envelope) with :mod:`mhs.limits`.

    The effective bound is the intersection of both; a value outside it is a
    rejection, never a clamp (plan 3.5, ADPT-024).  ``unit`` is the unit the
    value has when it is checked -- the ``to`` unit of the rule's conversion,
    because a clamp is checked after the unit conversion.  A clamp or envelope
    ``unit`` must equal it (conversions are never implicit), and two declared
    units must agree.  Malformed bounds (unknown keys such as ``maxx``,
    non-numbers, ``min > max``, disjoint sources, a unit mismatch) raise
    :class:`MappingError`.
    """

    sources: list[_limits.LimitSource] = []
    for label, spec in (("clamp", clamp), ("envelope", envelope)):
        if spec is None:
            continue
        if not isinstance(spec, Mapping):
            raise MappingError(f"{label} for {target!r} must be an object")
        for key in ("min", "max"):
            value = spec.get(key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                      or not math.isfinite(float(value))):
                raise MappingError(f"{label} {key} for {target!r} must be a finite number")
        declared = spec.get("unit")
        if declared is not None and (not isinstance(declared, str) or not declared.strip()):
            raise MappingError(f"{label} unit for {target!r} must be a non-empty UCUM code")
        if declared is not None and unit is not None and declared != unit:
            raise MappingError(
                f"{label} unit {declared!r} for {target!r} differs from {unit!r}, the unit the value "
                "has when the clamp is checked (after the unit conversion); state the bound in "
                f"{unit!r} -- conversions are never implicit (plan 3.5)"
            )
        rule = _bound_rule(spec, label, target)
        if rule is not None:
            sources.append(_limits.LimitSource(f"binding.{label}", {"value": rule}))
    schema: Mapping[str, Any] = _CLAMP_SCHEMA
    if unit is not None:
        schema = {"type": "object", "properties": {"value": {"type": "number", "x-mhs-unit": unit}}}
    try:
        return _limits.compile_limits(schema, sources)
    except _limits.LimitConfigError as exc:
        raise MappingError(f"invalid clamp for {target!r}: {exc}") from exc


def check_clamp(target: str, value: Any, effective: _limits.EffectiveLimits) -> Any:
    """Return ``value`` when it is inside ``effective``; otherwise raise ENVELOPE_VIOLATION."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MappingError(f"clamp for {target!r} requires a number, got {type(value).__name__}")
    violations = _limits.check({"value": value}, effective)
    if not violations:
        return value
    violation = violations[0]
    rule = effective.rule("value")
    envelope = {}
    if rule is not None:
        for kind in ("min", "max"):
            bound = rule.bound_at(kind, None)
            if bound is not None:
                envelope[kind] = bound.value
    details: dict[str, Any] = {
        "target": target,
        "path": target,
        "kind": violation.kind,
        "bound": violation.bound,
        "value": value,
        "source": violation.source,
        "envelope": envelope,
    }
    if violation.unit is not None:
        details["unit"] = violation.unit
    unit = f" {violation.unit}" if violation.unit else ""
    raise make_mhs_error(
        "MHS.SAFETY.ENVELOPE_VIOLATION",
        f"value {value!r}{unit} for {target!r} is outside the declared limit "
        f"({violation.kind} {violation.bound!r}{unit}); it is rejected, never clamped",
        {"retryable": False, "details": details},
    )


class _Rule:
    """One compiled field rule of a declarative capability map.

    The rule accepts both the canonical MHS-006 §7.2 forms (``from``,
    ``value``, ``type``, ``enum_map``/``map``, ``unit{from,to,factor|offset}``,
    ``clamp``) and the deprecated legacy shapes (``const``, ``enum``,
    ``scale``, ``offset``, ``unit[from,to]``).  Every clamp -- canonical or
    legacy, with or without a wider envelope -- is compiled by
    :mod:`mhs.limits` and an input outside it raises
    ``MHS.SAFETY.ENVELOPE_VIOLATION``; nothing is silently clamped.
    """

    __slots__ = (
        "target",
        "source",
        "const",
        "default",
        "required",
        "unsupported",
        "unit",
        "enum",
        "clamp",
        "limits",
        "enforce_clamp",
        "scale",
        "offset",
        "type_name",
        "direction",
    )

    def __init__(self, target: str, spec: Mapping[str, Any], *, direction: str):
        if not isinstance(spec, Mapping):
            raise MappingError(f"mapping rule for {target!r} must be an object")
        unknown = set(spec) - _RULE_KEYS
        if unknown:
            raise MappingError(f"unknown mapping keys for {target!r}: {sorted(unknown)}")
        self.target = target
        self.direction = direction
        self.source = spec.get("from")
        if self.source is not None and not isinstance(self.source, str):
            raise MappingError(f"'from' for {target!r} must be a field path string")
        if "value" in spec and "const" in spec:
            raise MappingError(f"{target!r} cannot combine 'value' and 'const'")
        self.const = spec["value"] if "value" in spec else spec.get("const", _MISSING)
        self.default = spec.get("default", _MISSING)
        self.required = bool(spec.get("required", False))
        self.unsupported = bool(spec.get("unsupported", False))
        if self.unsupported and (
            self.source is not None or self.const is not _MISSING or self.default is not _MISSING
        ):
            raise MappingError(
                f"{target!r} cannot be 'unsupported' and also mapped/injected"
            )
        self.type_name = None
        if "type" in spec:
            declared = str(spec["type"])
            if declared not in _TYPE_ALIASES:
                raise MappingError(f"unknown type {declared!r} for {target!r}")
            self.type_name = _TYPE_ALIASES[declared]
        enum_keys = [key for key in _ENUM_KEYS if key in spec]
        if len(enum_keys) > 1:
            raise MappingError(
                f"{target!r} declares more than one enum form: {sorted(enum_keys)}"
            )
        self.enum = None
        if enum_keys:
            mapping = spec[enum_keys[0]]
            if not isinstance(mapping, Mapping) or not mapping:
                raise MappingError(f"enum map for {target!r} must be a non-empty object")
            self.enum = dict(mapping)
        if "unit" in spec and "units" in spec:
            raise MappingError(f"{target!r} cannot combine 'unit' and 'units'")
        self.unit = None
        if "unit" in spec or "units" in spec:
            raw_unit = spec["unit"] if "unit" in spec else spec["units"]
            self.unit = _unit_spec(raw_unit) if isinstance(raw_unit, Mapping) else _unit_spec(
                {"from": _unit_pair(raw_unit)[0], "to": _unit_pair(raw_unit)[1]}
            )
        self.scale = 1.0
        self.offset = 0.0
        try:
            self.scale = float(spec.get("scale", 1.0))
            self.offset = float(spec.get("offset", 0.0))
        except (TypeError, ValueError) as exc:
            raise MappingError(f"scale/offset for {target!r} must be numbers") from exc
        self.clamp = None
        self.limits = None
        # Kept for introspection only: every clamp is a hard check (ADPT-024).
        self.enforce_clamp = True
        clamp_spec: Mapping[str, Any] | None = None
        envelope_spec: Mapping[str, Any] | None = None
        if "clamp" in spec:
            clamp = spec["clamp"]
            if not isinstance(clamp, Mapping):
                raise MappingError(f"clamp for {target!r} must be an object")
            unknown_clamp = set(clamp) - _CLAMP_KEYS
            if unknown_clamp:
                raise MappingError(
                    f"unknown clamp keys for {target!r}: {sorted(unknown_clamp)}"
                )
            if "envelope" in clamp and "limits" in clamp:
                raise MappingError(f"{target!r} declares the envelope twice")
            clamp_spec = {key: clamp[key] for key in ("min", "max", "unit", "reason") if key in clamp}
            envelope_spec = clamp.get("envelope", clamp.get("limits"))
        if spec.get("envelope") is not None:
            if envelope_spec is not None:
                raise MappingError(f"{target!r} declares the envelope twice")
            envelope_spec = spec["envelope"]
        if clamp_spec is not None or envelope_spec is not None:
            declares_unit = any(
                isinstance(part, Mapping) and part.get("unit") is not None
                for part in (clamp_spec, envelope_spec)
            )
            if declares_unit and (self.scale != 1.0 or self.offset != 0.0):
                raise MappingError(
                    f"a clamp unit for {target!r} cannot be checked after a legacy scale/offset; "
                    "declare the conversion as 'unit' {from, to}"
                )
            # The clamp is checked after the conversion, so its unit is the 'to' unit.
            value_unit = str(self.unit["to"]) if self.unit is not None else None
            self.limits = compile_clamp(target, clamp_spec, envelope_spec, unit=value_unit)
            self.clamp = {**(clamp_spec or {}), **({"envelope": dict(envelope_spec)} if envelope_spec else {})}
        if self.const is not _MISSING and self.source is not None:
            raise MappingError(f"{target!r} cannot combine 'from' and 'value'/'const'")
        if (
            not self.unsupported
            and self.source is None
            and self.const is _MISSING
            and self.default is _MISSING
        ):
            raise MappingError(f"{target!r} needs one of 'from', 'value', 'const' or 'default'")

    def apply(self, source: Any) -> Any:
        if self.unsupported:
            return _MISSING
        if self.const is not _MISSING:
            return self.const
        if self.source is None:
            value = self.default
        else:
            try:
                value = get_path(source, self.source)
            except MappingError:
                if self.default is not _MISSING:
                    value = self.default
                elif self.required:
                    raise
                else:
                    return _MISSING
        if value is _MISSING:
            return _MISSING
        if self.direction == "input" and _non_finite(value):
            # also without a declared type: NaN/inf never reach a native or a template
            raise MappingError(f"value for {self.target!r} is not a finite number")
        if isinstance(value, _Fanout):
            # A [*] wildcard fans out: apply the scalar transforms per element.
            return [self._transform_one(item) for item in value]
        return self._transform_one(value)

    def _transform_one(self, value: Any) -> Any:
        if self.enum is not None:
            try:
                value = self.enum[value]
            except (KeyError, TypeError) as exc:
                raise MappingError(
                    f"value {value!r} for {self.target!r} is outside the declared enum "
                    f"{sorted(self.enum, key=str)}"
                ) from exc
        if self.unit is not None:
            value = _convert_value(value, self.unit)
        if self.scale != 1.0 or self.offset != 0.0:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise MappingError(
                    f"scale/offset for {self.target!r} requires a number, "
                    f"got {type(value).__name__}"
                )
            value = float(value) * self.scale + self.offset
        if self.type_name is not None:
            value = _coerce_type(value, self.type_name, self.target)
        if self.limits is not None:
            value = check_clamp(self.target, value, self.limits)
        return value


def _inverted_target(target: str) -> bool:
    """True for an output field name that is really a native path (``$``, ``output.x``)."""

    return target.startswith("$") or target.startswith(("output.", "input.", "args."))


class FieldMapping:
    """Compiled declarative map from an MHS payload to/from a native payload.

    ``direction="input"`` maps MHS capability input -> native arguments.
    ``direction="output"`` maps a native result -> capability output fields.

    Besides the internal ``{target: rule}`` shape, an output mapping may be the
    normative wrapper ``{"map": {output_field: native_path}}`` (MHS-006 §4.1);
    its values may be path strings or transform objects.  With
    ``required_by_default=True`` (the canonical grammar) a result path that is
    absent in the native value is an error unless the target is listed in
    ``optional``: a misspelled path never yields a silently empty output.
    """

    def __init__(self, spec: Mapping[str, Any] | None, *, direction: str, strict: bool = True,
                 required_by_default: bool = False, optional: Sequence[str] = ()):
        if spec is None:
            spec = {}
        if not isinstance(spec, Mapping):
            raise MappingError(f"{direction} mapping must be an object")
        if direction == "output" and set(spec) == {"map"}:
            wrapped = spec["map"]
            if not isinstance(wrapped, Mapping) or not wrapped:
                raise MappingError("result.map must be a non-empty object")
            unwrapped: dict[str, Any] = {}
            for target, value in wrapped.items():
                if isinstance(value, str):
                    unwrapped[str(target)] = {"from": value}
                elif isinstance(value, Mapping):
                    rule = dict(value)
                    rule.setdefault("from", rule.pop("path", None))
                    if not rule.get("from"):
                        raise MappingError(
                            f"result.map entry {target!r} needs a native path string or 'from'"
                        )
                    unwrapped[str(target)] = rule
                else:
                    raise MappingError(
                        f"result.map entry {target!r} must be a path string or transform object"
                    )
            spec = unwrapped
        self.direction = direction
        optional_set = {str(name) for name in optional}
        rules: list[_Rule] = []
        for target, rule_spec in spec.items():
            if direction == "output" and _inverted_target(str(target)):
                raise MappingError(
                    f"result target {str(target)!r} is a native path, not an output field name "
                    "(result.map keys are output fields, its values native paths)"
                )
            rule = _Rule(str(target), rule_spec, direction=direction)
            if required_by_default and str(target) not in optional_set and rule.default is _MISSING:
                rule.required = True
            rules.append(rule)
        self.rules = rules

    @property
    def targets(self) -> list[str]:
        return [rule.target for rule in self.rules]

    def map(self, source: Any) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for rule in self.rules:
            value = rule.apply(source)
            if value is _MISSING:
                continue
            result[rule.target] = value
        return result

    def __bool__(self) -> bool:
        return bool(self.rules)


class ErrorMap:
    """Map native exception classes/messages onto stable MHS error codes.

    Two shapes are accepted:

    * mapping (deprecated legacy shape): ``{"ValueError": "MHS...",
      "RuntimeError:busy": "MHS...", "*": "MHS..."}``;
    * ordered array (normative MHS-006 §7.2): ``[{"native": regex, "mhs_code":
      "MHS...", "retryable": false}, ...]``.  Rules are evaluated in order and
      the first regex match wins.

    An exception no rule matches -- in either shape, and with no map at all --
    is ``MHS.ADAPTER.SHIM_FAILED`` (ADPT-022, plan 3.7); bridges redact its
    native message.  Only an explicit legacy ``"*"`` entry changes that default.

    With ``strict=True`` every code must belong to the driver subset of the
    error registry (``errors.json`` ``driver_subset``).
    """

    def __init__(self, spec: Mapping[str, str] | Sequence[Mapping[str, Any]] | None = None, *,
                 strict: bool = False):
        self._exact: dict[str, str] = {}
        self._contains: list[tuple[str, str, str]] = []
        self._ordered: list[tuple[re.Pattern[str], str, bool]] = []
        self._canonical = False
        self._default = "MHS.ADAPTER.SHIM_FAILED"
        self.strict = bool(strict)
        if spec is None:
            return
        if isinstance(spec, Mapping):
            for key, code in spec.items():
                self._check_code(str(code), f"errors[{key!r}]")
                if key == "*":
                    self._default = str(code)
                elif ":" in str(key):
                    # ``"RuntimeError:busy"`` matches a RuntimeError whose message
                    # contains ``busy``; the mapped code is the dict value.
                    class_name, _, needle = str(key).partition(":")
                    self._contains.append((class_name.strip(), needle.strip(), str(code)))
                else:
                    self._exact[str(key)] = str(code)
            return
        if isinstance(spec, (list, tuple)):
            self._canonical = True
            self._default = "MHS.ADAPTER.SHIM_FAILED"
            for index, item in enumerate(spec):
                if not isinstance(item, Mapping):
                    raise MappingError(f"errors[{index}] must be an object")
                unknown = set(item) - {"native", "mhs_code", "retryable", "description"}
                if unknown:
                    raise MappingError(f"unknown errors[{index}] keys: {sorted(unknown)}")
                pattern = item.get("native")
                code = item.get("mhs_code")
                if not isinstance(pattern, str) or not pattern:
                    raise MappingError(f"errors[{index}].native must be a non-empty regex")
                if not isinstance(code, str) or not code.startswith("MHS."):
                    raise MappingError(f"errors[{index}].mhs_code must be an MHS.* code")
                self._check_code(code, f"errors[{index}].mhs_code")
                retryable = item.get("retryable", False)
                if not isinstance(retryable, bool):
                    raise MappingError(f"errors[{index}].retryable must be a boolean")
                try:
                    compiled = re.compile(pattern)
                except re.error as exc:
                    raise MappingError(f"errors[{index}].native is not a regex: {exc}") from exc
                self._ordered.append((compiled, code, retryable))
            return
        raise MappingError("errors must be an object (legacy) or an ordered array (MHS-006 §7.2)")

    def _check_code(self, code: str, label: str) -> None:
        if self.strict and not _errors.is_driver_code(code):
            raise MappingError(
                f"{label} {code!r} is not in the driver subset of the error registry "
                f"(strict mode; allowed: {sorted(_errors.DRIVER_SUBSET)})"
            )

    def translate_exception(self, exc: BaseException) -> tuple[str, str, bool]:
        """Return ``(mhs_code, message, retryable)`` for a native exception."""

        name = type(exc).__name__
        message = str(exc) or name
        if self._canonical:
            candidates = (name, message, f"{name}: {message}")
            for pattern, code, retryable in self._ordered:
                if any(pattern.search(candidate) for candidate in candidates):
                    return code, message, retryable
            return self._default, message, False
        code = self._exact.get(name)
        if code is None:
            for base in type(exc).__mro__:
                if base.__name__ in self._exact:
                    code = self._exact[base.__name__]
                    break
        if code is None:
            mro_names = {base.__name__ for base in type(exc).__mro__}
            for class_name, needle, candidate in self._contains:
                if class_name and class_name not in mro_names:
                    continue
                if needle in message:
                    code = candidate
                    break
        return code or self._default, message, False

    def translate(self, exc: BaseException) -> tuple[str, str]:
        code, message, _retryable = self.translate_exception(exc)
        return code, message


# ---------------------------------------------------------------------------
# bounded native calls, awaitables and Status-like objects
# ---------------------------------------------------------------------------

_POLL_S = 0.005


def _event_set(event: Any) -> bool:
    if event is None:
        return False
    is_set = getattr(event, "is_set", None)
    if callable(is_set):
        try:
            return bool(is_set())
        except Exception:  # noqa: BLE001
            return False
    try:
        return bool(event)
    except Exception:  # noqa: BLE001
        return False


def is_awaitable(value: Any) -> bool:
    """True for coroutines, asyncio futures/tasks and objects with ``__await__``."""

    return inspect.isawaitable(value)


def is_status_like(value: Any) -> bool:
    """True for Status-like objects: ``wait(timeout)``, or both ``done`` and ``success``.

    JSON data (``None``, numbers, strings, mappings, sequences) and awaitables
    are never Status-like.
    """

    if value is None or isinstance(value, (bool, int, float, str, bytes, Mapping, list, tuple)):
        return False
    if inspect.isawaitable(value) or isinstance(value, concurrent.futures.Future):
        return False
    if callable(getattr(value, "wait", None)):
        return True
    return hasattr(value, "done") and hasattr(value, "success")


def _deadline(timeout_ms: float | None) -> float | None:
    if timeout_ms is None:
        return None
    return time.monotonic() + max(0.0, float(timeout_ms)) / 1000.0


def _remaining(deadline: float | None) -> float | None:
    return None if deadline is None else deadline - time.monotonic()


def wait_future(future: concurrent.futures.Future, *, timeout_ms: float | None = None,
                cancel_event: Any = None, label: str = "native call") -> Any:
    """Wait for ``future`` within ``timeout_ms``, cancelling it on ``cancel_event``.

    Raises :class:`mhs.signals.Cancelled` when the event is set (or the future
    was cancelled) and an :func:`outcome_unknown` signal when the bound
    expires; the future is cancelled in both cases.  The future's own
    exception propagates unchanged.
    """

    deadline = _deadline(timeout_ms)
    while True:
        remaining = _remaining(deadline)
        if remaining is not None and remaining <= 0:
            break
        step = 0.1 if remaining is None else remaining
        if cancel_event is not None:
            step = min(step, 0.01)
        done, _pending = concurrent.futures.wait([future], timeout=max(0.0, step))
        if done:
            try:
                return future.result()
            except (concurrent.futures.CancelledError, asyncio.CancelledError) as exc:
                raise signals.Cancelled(f"{label} was cancelled") from exc
        if _event_set(cancel_event):
            future.cancel()
            raise signals.Cancelled(f"{label} was cancelled by the operation's cancel request")
    future.cancel()
    raise outcome_unknown(
        f"{label} did not finish within {int(timeout_ms or 0)} ms; its effect is unknown "
        "(observe the device state before retrying)",
        details={"timeout_ms": int(timeout_ms or 0), "cancelled_native": True},
    )


def _status_flag(status: Any, name: str) -> Any:
    value = getattr(status, name, None)
    if callable(value):
        try:
            value = value()
        except Exception:  # noqa: BLE001
            return None
    return value


def wait_status(status: Any, *, timeout_ms: float | None = None, cancel_event: Any = None,
                label: str = "native call") -> dict[str, Any]:
    """Wait for a Status-like object; returns ``{"done": True, "success": True}``.

    Calls ``wait(timeout)`` in short slices when the object has it (a
    ``TimeoutError`` from a slice, a ``False`` return or a ``done`` flag that
    is still false means "not yet"; some Status objects only complete inside
    ``wait``), otherwise polls ``done``.  ``success`` False is a
    :func:`driver_failed` ``MHS.DEVICE.FAULTED``; an exception raised by
    ``wait`` propagates (the caller maps it).  When ``cancel_event`` is set the
    status is stopped through its ``cancel()``/``stop()`` method if it has one
    (then :class:`mhs.signals.Cancelled`); a status that cannot be stopped is
    waited for, because its effect continues anyway.  The bound expiring raises
    an :func:`outcome_unknown` signal.
    """

    deadline = _deadline(timeout_ms)
    has_done = hasattr(status, "done")
    wait = getattr(status, "wait", None)
    while True:
        if has_done and _status_flag(status, "done") is True:
            break
        if _event_set(cancel_event):
            stopper = getattr(status, "cancel", None) or getattr(status, "stop", None)
            if callable(stopper):
                try:
                    stopper()
                except Exception:  # noqa: BLE001 - the cancellation is reported either way
                    pass
                raise signals.Cancelled(f"{label} was cancelled by the operation's cancel request")
        remaining = _remaining(deadline)
        if remaining is not None and remaining <= 0:
            raise outcome_unknown(
                f"{label}: the Status object did not finish within {int(timeout_ms or 0)} ms; "
                "its effect is unknown",
                details={"timeout_ms": int(timeout_ms or 0)},
            )
        step = 0.01 if remaining is None else max(0.0, min(0.01, remaining))
        if not callable(wait):
            time.sleep(step)
            continue
        try:
            result = wait(step)
        except TimeoutError:
            continue
        except Exception as exc:  # noqa: BLE001 - "...TimeoutError" classes of other libraries
            if "timeout" in type(exc).__name__.lower():
                continue
            raise
        if result is False or (has_done and _status_flag(status, "done") is False):
            continue
        break
    success = _status_flag(status, "success")
    if success is False:
        raise driver_failed("MHS.DEVICE.FAULTED", f"{label}: the Status object reported failure")
    return {"done": True, "success": True}


def call_bounded(fn: Callable[..., Any], args: Sequence[Any] = (), kwargs: Mapping[str, Any] | None = None,
                 *, timeout_ms: float | None = None, label: str = "native call") -> Any:
    """Call a synchronous native, bounded by ``timeout_ms`` (ADPT-025).

    On expiry an :func:`outcome_unknown` signal is raised (the native may still
    be running on its daemon thread; its effect is unknown, so the call is not
    retryable).  ``timeout_ms=None`` calls inline.
    """

    kwargs = dict(kwargs or {})
    if timeout_ms is None:
        return fn(*args, **kwargs)
    if timeout_ms <= 0:
        raise outcome_unknown(f"no time budget remains for {label}", details={"timeout_ms": 0})
    box: dict[str, Any] = {}

    def runner() -> None:
        try:
            box["value"] = fn(*args, **kwargs)
        except BaseException as exc:  # noqa: BLE001 - re-raised on the caller thread
            box["error"] = exc

    thread = threading.Thread(target=runner, name=f"mhs-native-{label}"[:60], daemon=True)
    thread.start()
    thread.join(float(timeout_ms) / 1000.0)
    if thread.is_alive():
        raise outcome_unknown(
            f"{label} exceeded its {int(timeout_ms)} ms bound; its effect is unknown "
            "(observe the device state before retrying)",
            details={"timeout_ms": int(timeout_ms)},
        )
    if "error" in box:
        raise box["error"]
    return box.get("value")


class AsyncRunner:
    """One persistent asyncio event loop on a daemon thread, owned by one bridge.

    Every coroutine of a bridge runs on the same loop (libraries such as
    PyLabRobot bind transports to the loop that ran ``setup()``).
    :meth:`run` schedules an awaitable with ``asyncio.run_coroutine_threadsafe``
    and waits for it from the calling thread, bounded by ``timeout_ms``; when
    ``cancel_event`` is set the task is cancelled (``future.cancel()``) and
    :class:`mhs.signals.Cancelled` is raised; when the bound expires the task
    is cancelled and an unknown outcome is raised.  The loop starts lazily.
    """

    def __init__(self, name: str = "mhs-bridge-loop"):
        self.name = name
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._closed = False

    @property
    def started(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def closed(self) -> bool:
        return self._closed

    def loop(self) -> asyncio.AbstractEventLoop:
        return self._ensure_loop()

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._closed:
                raise make_mhs_error("MHS.DEVICE.NOT_READY", "the bridge's event loop is closed",
                                     {"retryable": False})
            if self._loop is not None:
                return self._loop
            loop = asyncio.new_event_loop()
            ready = threading.Event()

            def run() -> None:
                asyncio.set_event_loop(loop)
                loop.call_soon(ready.set)
                try:
                    loop.run_forever()
                finally:
                    try:
                        pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
                        for task in pending:
                            task.cancel()
                        if pending:
                            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                        loop.run_until_complete(loop.shutdown_asyncgens())
                    except Exception:  # noqa: BLE001 - best-effort teardown
                        pass
                    finally:
                        loop.close()

            thread = threading.Thread(target=run, name=self.name, daemon=True)
            thread.start()
            if not ready.wait(5.0):  # pragma: no cover - defensive
                raise make_mhs_error("MHS.DEVICE.NOT_READY", "the bridge's event loop did not start",
                                     {"retryable": True})
            self._loop, self._thread = loop, thread
            return loop

    def run(self, awaitable: Any, *, timeout_ms: float | None = None, cancel_event: Any = None,
            label: str = "native call") -> Any:
        if self._thread is not None and threading.current_thread() is self._thread:
            _close_coroutine(awaitable)
            raise RuntimeError("AsyncRunner.run() was called from its own event-loop thread")
        try:
            loop = self._ensure_loop()
        except BaseException:
            _close_coroutine(awaitable)
            raise
        future = asyncio.run_coroutine_threadsafe(_as_coroutine(awaitable), loop)
        return wait_future(future, timeout_ms=timeout_ms, cancel_event=cancel_event, label=label)

    def close(self, timeout_s: float = 2.0) -> None:
        with self._lock:
            self._closed = True
            loop, thread = self._loop, self._thread
            self._loop = self._thread = None
        if loop is None or thread is None:
            return
        try:
            loop.call_soon_threadsafe(loop.stop)
        except RuntimeError:  # pragma: no cover - already closed
            return
        if thread is not threading.current_thread():
            thread.join(timeout_s)


def _as_coroutine(awaitable: Any) -> Any:
    if asyncio.iscoroutine(awaitable):
        return awaitable

    async def _await() -> Any:
        return await awaitable

    return _await()


def _close_coroutine(value: Any) -> None:
    if asyncio.iscoroutine(value):
        value.close()


def resolve_native(value: Any, *, runner: AsyncRunner | None, timeout_ms: float | None = None,
                   cancel_event: Any = None, label: str = "native call") -> Any:
    """Turn a native return into its final value.

    Awaitables run on ``runner``; ``concurrent.futures.Future`` objects and
    Status-like objects are waited for; every wait is bounded by
    ``timeout_ms`` and observes ``cancel_event``.  Other values pass through.
    """

    if isinstance(value, concurrent.futures.Future):
        return wait_future(value, timeout_ms=timeout_ms, cancel_event=cancel_event, label=label)
    if inspect.isawaitable(value):
        if runner is None:
            _close_coroutine(value)
            raise driver_failed("MHS.ADAPTER.SHIM_FAILED", f"{label} returned an awaitable but no event loop is available")
        return runner.run(value, timeout_ms=timeout_ms, cancel_event=cancel_event, label=label)
    if is_status_like(value):
        return wait_status(value, timeout_ms=timeout_ms, cancel_event=cancel_event, label=label)
    return value


# ---------------------------------------------------------------------------
# line-protocol helpers (command templates and response parsing)
# ---------------------------------------------------------------------------

_PARSE_KINDS = ("raw", "str", "float", "int", "bool", "regex")
_FLOAT_PATTERN = r"[-+]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][-+]?[0-9]+)?"
_INT_PATTERN = r"[-+]?[0-9]+"
#: Tokens parse kind ``bool`` always recognises (``true``/``false`` add one each).
BOOL_TRUE_TOKENS = ("1", "ON", "TRUE")
BOOL_FALSE_TOKENS = ("0", "OFF", "FALSE")


def bool_tokens(spec: Mapping[str, Any] | None) -> tuple[frozenset[str], frozenset[str]]:
    """The (upper-case) true and false tokens of a ``bool`` parse spec.

    ``true`` (default ``"1"``) and ``false`` (default ``"0"``) each add one
    token to ``ON``/``TRUE`` and ``OFF``/``FALSE``.  Without a declared
    ``false`` a token the true set claims is not also read as false.
    """

    spec = spec or {}
    true = str(spec.get("true", "1")).strip().upper()
    true_set = frozenset({true, "ON", "TRUE"})
    if spec.get("false") is not None:
        false_set = frozenset({str(spec["false"]).strip().upper(), "OFF", "FALSE"})
    else:
        false_set = frozenset(BOOL_FALSE_TOKENS) - true_set
    return true_set, false_set


def _non_finite(value: Any, depth: int = 0) -> bool:
    """True when ``value`` is (or contains) a NaN or infinite float."""

    if isinstance(value, float):
        return not math.isfinite(value)
    if depth > 32:
        return False
    if isinstance(value, Mapping):
        return any(_non_finite(item, depth + 1) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_non_finite(item, depth + 1) for item in value)
    return False


def format_command(template: str, values: Mapping[str, Any], *, separators: str = "") -> str:
    """Fill a one-line command template; string values may not inject commands.

    A string value containing a line break, a control character or one of
    ``separators`` (``";"`` for SCPI) is refused with ``MHS.CAPABILITY.INPUT_INVALID``
    -- an input can never smuggle a second command onto the wire -- and so is
    a NaN or infinite number (``VOLT nan`` never reaches an instrument).
    """

    for name, value in values.items():
        if _non_finite(value):
            raise make_mhs_error(
                "MHS.CAPABILITY.INPUT_INVALID",
                f"argument {name!r} is not a finite number",
                {"retryable": False, "details": {"argument": name}},
            )
        if isinstance(value, str):
            bad = [char for char in value if ord(char) < 32 or ord(char) == 127 or char in separators]
            if bad:
                raise make_mhs_error(
                    "MHS.CAPABILITY.INPUT_INVALID",
                    f"argument {name!r} contains a character that could inject a command",
                    {"retryable": False, "details": {"argument": name}},
                )
    try:
        return str(template).format(**dict(values))
    except (KeyError, IndexError, ValueError, AttributeError) as exc:
        raise MappingError(f"cannot format command template {template!r}: {exc}") from exc


def parse_text(text: Any, spec: Mapping[str, Any] | None, *, whole: bool = False) -> Any:
    """Parse one response line by ``spec`` (``{kind, pattern?, group?, true?, false?}``).

    ``raw`` keeps the text, ``str`` strips it, ``float``/``int`` take the first
    number (or ``pattern``), ``bool`` is strict: ``true`` (default ``"1"``,
    also ``ON``/``TRUE``) is ``True``, ``false`` (default ``"0"``, also
    ``OFF``/``FALSE``) is ``False`` and any other reply -- an error string, an
    empty line, garbage -- raises (it must never read as ``False``: an
    inverted interlock would read it as *closed*).  ``regex`` returns the named
    groups (or ``group``, or the whole match).  A response that does not parse
    raises :class:`MappingError`.

    ``whole=True`` (every interlock reading) anchors ``float``/``int``/``regex``
    at both ends: the stripped reply must *be* the number (or match the whole
    declared pattern), so an error reply such as ``'ERR 0'`` or ``'E1 bad'``
    raises instead of reading the first number in it -- an interlock with
    ``closed_when: 0`` would read that as *closed*.
    """

    if isinstance(text, (bytes, bytearray)):
        text = bytes(text).decode("utf-8", "replace")
    if not isinstance(text, str):
        raise MappingError(f"cannot parse a {type(text).__name__} response as text")
    spec = dict(spec or {})
    kind = spec.get("kind", "raw")
    stripped = text.strip()
    if kind == "raw":
        return text.rstrip("\r\n")
    if kind == "str":
        return stripped
    if kind in ("float", "int"):
        pattern = spec.get("pattern") or (_FLOAT_PATTERN if kind == "float" else _INT_PATTERN)
        match = re.fullmatch(pattern, stripped) if whole else re.search(pattern, stripped)
        if not match:
            if whole:
                raise MappingError(f"response {stripped[:80]!r} is not exactly a {kind}"
                                   + (f" matching {pattern!r}" if spec.get("pattern") else ""))
            raise MappingError(f"no {kind} in response {stripped[:80]!r}")
        group = spec.get("group")
        token = match.group(group) if group is not None else match.group(0)
        try:
            value = float(token) if kind == "float" else int(token)
        except (TypeError, ValueError) as exc:
            raise MappingError(f"response {stripped[:80]!r} is not a {kind}") from exc
        if isinstance(value, float) and not math.isfinite(value):
            raise MappingError(f"response {stripped[:80]!r} is not a finite number")
        return value
    if kind == "bool":
        true_set, false_set = bool_tokens(spec)
        token = stripped.upper()
        if token in true_set and token not in false_set:
            return True
        if token in false_set and token not in true_set:
            return False
        raise MappingError(f"response {stripped[:80]!r} is not a recognised boolean "
                           f"(true: {sorted(true_set)}, false: {sorted(false_set)})")
    if kind == "regex":
        pattern = str(spec.get("pattern", ""))
        match = re.fullmatch(pattern, stripped) if whole else re.search(pattern, stripped)
        if not match:
            raise MappingError(f"response {stripped[:80]!r} does not {'fully ' if whole else ''}match {pattern!r}")
        group = spec.get("group")
        if group is not None:
            return match.group(group)
        groups = match.groupdict()
        return dict(groups) if groups else match.group(0)
    raise MappingError(f"unknown response parser {kind!r}")


# ---------------------------------------------------------------------------
# bridge context and lifecycle
# ---------------------------------------------------------------------------


@dataclass
class BridgeContext:
    """Everything a bridge is allowed to know about the request (duck-typed)."""

    command_id: str | None = None
    session_id: str | None = None
    device_id: str | None = None
    resource: str | None = None
    operation_id: str | None = None
    deadline_ms: int | None = 30000
    expected_revision: int | None = None
    permit_id: str | None = None
    revision: int = 0
    mode: str | None = None
    cancel_event: Any = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def coerce(cls, ctx: Any) -> "BridgeContext":
        if ctx is None:
            return cls()
        if isinstance(ctx, BridgeContext):
            return ctx
        if isinstance(ctx, Mapping):
            return cls(**{key: value for key, value in ctx.items() if key in cls.__dataclass_fields__})
        # server._Context is a different class with the same attributes
        kwargs = {
            key: getattr(ctx, key)
            for key in cls.__dataclass_fields__
            if hasattr(ctx, key)
        }
        if kwargs.get("extra") is None:
            kwargs["extra"] = {}
        return cls(**kwargs)

    def cancelled(self) -> bool:
        return _event_set(self.cancel_event)

    def remaining_ms(self) -> int:
        """Milliseconds left: ``extra['deadline_at']`` (monotonic) or ``deadline_ms``."""

        deadline_at = (self.extra or {}).get("deadline_at")
        if deadline_at is None:
            deadline = self.deadline_ms
            return max(0, int(deadline)) if deadline is not None else 30000
        return max(0, int((float(deadline_at) - time.monotonic()) * 1000.0))


class Bridge:
    """Base class for every bridge family (see the module docstring for the contract).

    Bridges are deliberately thin: they translate one declared native surface
    into capability calls and expose the device state document.  The server owns
    sessions, safety enforcement, revisions, idempotency and evidence; a bridge
    must never advance a revision or make a receipt.
    """

    bridge_kind: str = "abstract"
    bridge_id: str = "mhs.bridge.base"

    def __init__(self, *, device_id: str | None = None):
        self.device_id = device_id
        self._closed = False
        #: Serialises native calls of exclusive bindings.  ``estop`` never takes it.
        self._lock = threading.RLock()
        self._async_runner: AsyncRunner | None = None
        self._runner_lock = threading.Lock()
        self._estop_count = 0

    # -- capability / resource surface -------------------------------------
    def capabilities(self) -> list[dict[str, Any]]:
        """Capability bindings this bridge can execute (adapter metadata)."""

        return []

    def resources(self) -> list[dict[str, Any]]:
        return []

    # -- lifecycle ---------------------------------------------------------
    @property
    def closed(self) -> bool:
        return self._closed

    def ensure_open(self) -> None:
        if self._closed:
            raise make_mhs_error(
                "MHS.DEVICE.NOT_READY",
                f"bridge {self.bridge_id!r} is closed",
                {"retryable": False},
            )

    @property
    def async_runner(self) -> AsyncRunner:
        """The bridge's persistent event loop (created on first use)."""

        lock = getattr(self, "_runner_lock", None)
        if lock is None:  # a subclass that skipped Bridge.__init__
            self._runner_lock = lock = threading.Lock()
        with lock:
            runner = getattr(self, "_async_runner", None)
            if runner is None:
                runner = AsyncRunner(name=f"mhs-loop-{self.bridge_kind}")
                self._async_runner = runner
            return runner

    def resolve_native(self, value: Any, ctx: Any = None, *, timeout_ms: float | None = None,
                       label: str = "native call") -> Any:
        """Await/wait ``value`` (see :func:`resolve_native`) bounded by ``ctx`` and ``timeout_ms``."""

        context = BridgeContext.coerce(ctx) if ctx is not None else None
        budget = timeout_ms
        cancel_event = None
        if context is not None:
            remaining = context.remaining_ms()
            budget = remaining if budget is None else min(float(budget), float(remaining))
            cancel_event = context.cancel_event
        needs_loop = inspect.isawaitable(value) and not isinstance(value, concurrent.futures.Future)
        return resolve_native(value, runner=self.async_runner if needs_loop else None, timeout_ms=budget,
                              cancel_event=cancel_event, label=label)

    def close(self) -> None:
        self._closed = True
        runner = getattr(self, "_async_runner", None)
        if runner is not None:
            runner.close()

    def __enter__(self) -> "Bridge":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    # -- contract-plane operations (server calls these) --------------------
    def call(self, capability_id: str, args: Mapping[str, Any], ctx: Any = None) -> Any:
        """Execute one capability and return its output dict (never a wrapper)."""

        raise unsupported(capability_id)

    def read(self, resource_id: str, fields: Sequence[str] | None = None, ctx: Any = None) -> Any:
        """Return the resource state document (the only way state leaves a bridge)."""

        raise unsupported(resource_id, kind="resource")

    def write(self, resource_id: str, patch: Mapping[str, Any], ctx: Any = None) -> Any:
        """Apply a parameter patch; returns ``{"applied": {...}}``."""

        raise unsupported(resource_id, kind="resource")

    def snapshot(self, device_id: str | None = None) -> dict[str, Any]:
        raise unsupported("snapshot", kind="snapshot")

    def restore(self, snapshot: Any) -> dict[str, Any]:
        raise unsupported("restore", kind="restore")

    # -- e-stop epoch -------------------------------------------------------
    @property
    def estop_epoch(self) -> int:
        """Number of ``estop`` calls so far; a call captures it before waiting for a lock."""

        return int(getattr(self, "_estop_count", 0))

    def _engage_estop(self) -> None:
        """Advance the epoch first thing in ``estop`` (queued calls are then refused)."""

        self._estop_count = self.estop_epoch + 1

    def _refuse_if_estopped(self, epoch: int, label: str) -> None:
        """Raise ``MHS.SAFETY.ESTOP_ENGAGED`` when an e-stop fired since ``epoch`` was taken."""

        if self.estop_epoch != epoch:
            raise make_mhs_error(
                "MHS.SAFETY.ESTOP_ENGAGED",
                f"{label} was not executed: an e-stop was engaged while it waited for the device",
                {"retryable": False, "details": {"preempted_by_estop": True}},
            )

    # -- safety hooks (optional; the server owns enforcement) --------------
    @property
    def estop_native(self) -> str | None:
        """The native symbol or command the e-stop reaches (``None``: software-only)."""

        return None

    def interlocks(self) -> list[dict[str, str]]:
        return []

    def safety_status(self) -> dict[str, Any]:
        return {}

    def estop(self, reason: str = "", ctx: Any = None) -> Any:
        """Stop the device; may run concurrently with ``call`` (never take ``self._lock``)."""

        self._engage_estop()
        return {}

    def safe_state(self, ctx: Any = None) -> Any:
        """Bring the device to its declared safe state (no-op unless bound)."""

        return {}

    def reset(self, ctx: Any = None) -> Any:
        return {}

    # -- diagnostics -------------------------------------------------------
    def describe(self) -> dict[str, Any]:
        return {
            "bridge_id": self.bridge_id,
            "bridge_kind": self.bridge_kind,
            "device_id": self.device_id,
            "capabilities": [item.get("capability_id") for item in self.capabilities()],
            "resources": [item.get("resource_id") for item in self.resources()],
            "estop_native": self.estop_native,
        }


def _resolve_callable(target: Any, dotted: str) -> Callable[..., Any]:
    current = target
    for part in dotted.split("."):
        if not part:
            continue
        try:
            current = getattr(current, part)
        except AttributeError as exc:
            raise make_mhs_error(
                "MHS.CAPABILITY.NOT_BOUND",
                f"native symbol {dotted!r} is absent on {type(target).__name__}",
                {"retryable": False, "remediation": "Fix the adapter map or pin the upstream version."},
            ) from exc
    return current


def load_object(target: str, factory: Mapping[str, Any] | None = None) -> Any:
    """Import ``module:attr`` and materialise the bridge target object.

    ``factory`` is the declarative lifecycle: ``{"kind": "class"|"factory"|"none",
    "args": [...], "kwargs": {...}}``.  When ``kind`` is omitted a class is
    constructed and a plain object is used as-is; functions are only called
    when the adapter explicitly says ``"kind": "factory"``.  A factory may
    return an awaitable; the caller awaits it (see ``PythonObjectBridge``).
    """

    if ":" not in target:
        raise make_mhs_error(
            "MHS.ADAPTER.MANIFEST_INVALID",
            f"adapter target {target!r} must be 'module:attr'",
            {"retryable": False},
        )
    module_name, attr_path = target.split(":", 1)
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise make_mhs_error(
            "MHS.DEVICE.NOT_READY",
            f"cannot import adapter target module {module_name!r}: {exc}",
            {"retryable": False, "remediation": "Install the upstream package or fix the adapter entry point."},
        ) from exc
    obj: Any = module
    for part in attr_path.split("."):
        try:
            obj = getattr(obj, part)
        except AttributeError as exc:
            raise make_mhs_error(
                "MHS.ADAPTER.MANIFEST_INVALID",
                f"adapter target {target!r} does not exist",
                {"retryable": False},
            ) from exc
    spec = dict(factory or {})
    kind = spec.get("kind", "auto")
    args = list(spec.get("args", []))
    kwargs = dict(spec.get("kwargs", {}))
    if kind in ("class", "call", "factory") or (kind == "auto" and isinstance(obj, type)):
        if not callable(obj):
            raise make_mhs_error(
                "MHS.ADAPTER.MANIFEST_INVALID",
                f"adapter target {target!r} is not callable",
                {"retryable": False},
            )
        try:
            return obj(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - lifecycle failure is a bridge error
            raise make_mhs_error(
                "MHS.DEVICE.NOT_READY",
                f"adapter target {target!r} failed to initialise ({type(exc).__name__})",
                {"retryable": False},
            ) from exc
    return obj


def import_optional(module_name: str) -> Any:
    """Import an optional equipment library without making it a hard dependency."""

    return importlib.import_module(module_name)


def main(argv: Sequence[str] | None = None) -> int:
    """Bridge modules are not launchers: print the usage line and return 2."""

    print(USAGE, file=sys.stderr)
    print("(bridge modules are libraries; serve a driver directory or an adapter manifest)",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

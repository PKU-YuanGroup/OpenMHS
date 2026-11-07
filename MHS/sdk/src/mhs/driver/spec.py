"""Declarations a Driver is made of: :class:`Field`, :class:`Limit`, :class:`Fact`, :class:`Action`.

These are plain data objects.  They never touch a device and never import the
server; :mod:`mhs.driver.build` turns them into the manifest, the limits and
the reference file of a device.

* :class:`Field` describes one value (a parameter, an action input or output):
  its JSON type, unit (``x-mhs-unit``, a UCUM code), element type and fixed
  length for arrays, members for objects, and the :class:`Limit` objects that
  bound it.  For a catalogue class a ``Field`` refines a class field: leave
  ``type`` out and it is taken from the class.
* :class:`Limit` is one closed limit rule (``min``, ``max``, ``allowed``,
  ``names``, ``unit``, ``source``, ``ref``, ``reason``) with an optional
  ``path`` relative to the field it is attached to (``"[*]"``, ``"x"``,
  ``"[2]"``) or absolute in ``action(limits=...)``.  A scalar ``min``/``max``
  on a numeric array bounds every element; a list bounds element by element
  (the array needs a fixed ``length``).  ``Limit.operator_required(reason)``
  is the legal answer when no source states the bound: the runtime then
  refuses the call with ``MHS.SAFETY.LIMITS_UNSET`` until an operator overlay
  (``site-limits.json``) supplies one.
* :class:`Fact` is one statement for the reference file, with its provenance
  (``vendor_doc`` or ``upstream_code`` facts cite ``ref`` as ``file:line``).
* :class:`Action` declares a capability binding without a method body (the
  config-only family drivers use it; a decorated method uses
  :func:`mhs.driver.action` instead).

Every constructor validates what it can check without the catalogue and
raises :class:`DriverDefinitionError` (a ``ValueError``); everything that
needs the catalogue is checked when the driver is built.
"""

from __future__ import annotations

import math
import re
from typing import Any, Iterable, Mapping, Sequence

from .. import limits as _limits
from ..catalog import RISK_ORDER as _RISKS

__all__ = [
    "Action",
    "DriverDefinitionError",
    "FACT_SOURCES",
    "Fact",
    "Field",
    "JSON_TYPES",
    "Limit",
    "LIMIT_SOURCES",
    "json_type",
]

#: JSON types a :class:`Field` may declare.
JSON_TYPES = ("number", "integer", "boolean", "string", "array", "object")
#: Python types accepted as shorthands for the JSON types.
_PY_TYPES: dict[Any, str] = {float: "number", int: "integer", bool: "boolean", str: "string",
                             list: "array", tuple: "array", dict: "object"}
#: ``Limit.source`` values (``class_default`` is reserved for catalogue limits).
LIMIT_SOURCES = ("vendor_doc", "upstream_code", "operator")
#: ``Fact.source`` values; a driver author writes only the first two.
FACT_SOURCES = ("vendor_doc", "upstream_code", "operator", "interview")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_UNSET: Any = object()


class DriverDefinitionError(ValueError):
    """A Driver class (or one of its declarations) cannot be built; ``problems`` lists every reason."""

    def __init__(self, problems: str | Iterable[str], *, driver: str | None = None,
                 findings: Sequence[Any] = ()):
        items = [problems] if isinstance(problems, str) else [str(item) for item in problems]
        self.problems: tuple[str, ...] = tuple(items) or ("the driver definition is invalid",)
        self.driver = driver
        #: Strict-mode findings (:class:`mhs._server.strict.Finding`) behind the problems, if any.
        self.findings = tuple(findings)
        head = f"{driver}: " if driver else ""
        if len(self.problems) == 1:
            message = head + self.problems[0]
        else:
            message = head + f"{len(self.problems)} problems:\n  " + "\n  ".join(self.problems)
        super().__init__(message)


def json_type(value: Any, what: str) -> str:
    """The JSON type name of ``value`` (a JSON type name or a Python type such as ``float``)."""
    if isinstance(value, str) and value in JSON_TYPES:
        return value
    try:
        found = _PY_TYPES.get(value)
    except TypeError:  # unhashable
        found = None
    if found is not None:
        return found
    raise DriverDefinitionError(f"{what}: type must be one of {list(JSON_TYPES)} (or float/int/bool/str/"
                                f"list/dict), got {value!r}")


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _join_path(base: str, relative: str | None) -> str:
    """``base`` + a relative limit path (``"[*]"``, ``"x"``, ``"[2].y"``)."""
    if not relative:
        return base
    return base + relative if relative.startswith("[") else f"{base}.{relative}"


# ---------------------------------------------------------------------------
# Limit
# ---------------------------------------------------------------------------


class Limit:
    """One closed limit rule (plan 3.5).

    ``source`` is ``vendor_doc`` or ``upstream_code`` with ``ref`` (the
    acceptance gate requires one of them, or :meth:`operator_required`);
    ``unit`` must equal the field's unit when given; ``names`` names the
    elements of a per-element bound; ``path`` is relative to the field the
    limit is attached to, or absolute in ``action(limits=...)``.
    """

    __slots__ = ("min", "max", "allowed", "names", "path", "unit", "source", "ref", "reason", "_operator")

    def __init__(self, min: Any = None, max: Any = None, *, allowed: Sequence[Any] | None = None,
                 names: Sequence[str] | None = None, path: str | None = None, unit: str | None = None,
                 source: str | None = None, ref: str | None = None, reason: str | None = None):
        self.min = list(min) if isinstance(min, (list, tuple)) else min
        self.max = list(max) if isinstance(max, (list, tuple)) else max
        self.allowed = list(allowed) if allowed is not None else None
        self.names = list(names) if names is not None else None
        self.path = path
        self.unit = unit
        self.source = source
        self.ref = ref
        self.reason = reason
        self._operator = False
        if path is not None and (not isinstance(path, str) or not path):
            raise DriverDefinitionError(f"Limit.path must be a non-empty limit path, got {path!r}")
        if source is not None and source not in LIMIT_SOURCES:
            raise DriverDefinitionError(f"Limit.source must be one of {list(LIMIT_SOURCES)}, got {source!r}")
        if self.min is None and self.max is None and self.allowed is None:
            raise DriverDefinitionError(
                "a Limit needs min, max or allowed; when no source states the bound use "
                "Limit.operator_required(reason)")
        try:
            _limits.LimitRule.parse(self._rule_json())
        except _limits.LimitConfigError as exc:
            raise DriverDefinitionError(f"invalid Limit {self!r}: {exc}") from exc

    @classmethod
    def operator_required(cls, reason: str, *, path: str | None = None) -> "Limit":
        """No source states this bound: the operator overlay must supply it before use.

        Without an overlay the runtime refuses every call that sets the field
        with ``MHS.SAFETY.LIMITS_UNSET``; ``reason`` says why the bound is
        missing and is published in the reference file.
        """
        if not isinstance(reason, str) or not reason.strip():
            raise DriverDefinitionError("Limit.operator_required(reason) needs a non-empty reason")
        if len(reason) > 500:
            raise DriverDefinitionError("Limit.operator_required reason must be at most 500 characters")
        if path is not None and (not isinstance(path, str) or not path):
            raise DriverDefinitionError(f"Limit.path must be a non-empty limit path, got {path!r}")
        limit = cls.__new__(cls)
        for slot in cls.__slots__:
            setattr(limit, slot, None)
        limit.path = path
        limit.reason = reason
        limit._operator = True
        return limit

    @property
    def is_operator_required(self) -> bool:
        return bool(self._operator)

    def _rule_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key in ("min", "max", "allowed", "unit", "names", "reason", "source", "ref"):
            value = getattr(self, key)
            if value is not None:
                out[key] = list(value) if isinstance(value, tuple) else value
        return out

    def to_json(self) -> dict[str, Any] | str:
        """The manifest form: a closed rule, or the string ``"operator_required"``."""
        if self._operator:
            return _limits.OPERATOR_REQUIRED
        return self._rule_json()

    def rule(self) -> _limits.LimitRule | None:
        """The :class:`mhs.limits.LimitRule` (``None`` for :meth:`operator_required`)."""
        return None if self._operator else _limits.LimitRule.parse(self._rule_json())

    def key(self, field_path: str) -> str:
        """The limit path of this limit when attached to the field at ``field_path``."""
        return _join_path(field_path, self.path)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Limit):
            return NotImplemented
        return all(getattr(self, slot) == getattr(other, slot) for slot in self.__slots__)

    def __hash__(self) -> int:  # pragma: no cover - limits are not dict keys
        return id(self)

    def __repr__(self) -> str:
        if self._operator:
            return f"Limit.operator_required({self.reason!r})"
        parts = [f"{key}={getattr(self, key)!r}" for key in
                 ("min", "max", "allowed", "names", "path", "unit", "source", "ref", "reason")
                 if getattr(self, key) is not None]
        return "Limit(" + ", ".join(parts) + ")"


def limits_of(value: Any, what: str) -> tuple[Limit, ...]:
    """``limit=`` as a tuple: ``None``, one :class:`Limit` or a sequence of them."""
    if value is None:
        return ()
    if isinstance(value, Limit):
        return (value,)
    if isinstance(value, (list, tuple)) and all(isinstance(item, Limit) for item in value):
        return tuple(value)
    raise DriverDefinitionError(f"{what}: limit must be a Limit or a list of Limit objects, got {value!r}")


# ---------------------------------------------------------------------------
# Field
# ---------------------------------------------------------------------------


class Field:
    """One value of a parameter, action input or action output.

    ``type`` is a JSON type (``"number"``, ``"integer"``, ``"boolean"``,
    ``"string"``, ``"array"``, ``"object"``) or ``None`` to take it from the
    catalogue class field being refined.  ``unit`` is a UCUM code
    (``x-mhs-unit``); on an array it is the unit of its numeric elements.
    ``native_unit`` (top-level numeric inputs and parameters only) makes the
    driver convert values to that unit before the native call and native
    reads back.  ``length`` fixes an array's length (per-element limits need
    it).  ``properties`` maps member names to fields of an object; ``required``
    is the member's requiredness inside its object (top-level inputs follow
    the method signature).  ``writable`` is used by config-only family
    parameters.  ``limit`` is a :class:`Limit` or a list of them.
    """

    __slots__ = ("type", "unit", "native_unit", "description", "limits", "items", "length", "min_items",
                 "max_items", "enum", "properties", "required", "max_length", "pattern", "delta", "nullable",
                 "writable")

    def __init__(self, type: Any = None, *, unit: str | None = None, native_unit: str | None = None,
                 description: str | None = None, limit: Any = None, items: Any = None,
                 length: int | None = None, min_items: int | None = None, max_items: int | None = None,
                 enum: Sequence[Any] | None = None, properties: Mapping[str, "Field"] | None = None,
                 required: bool | None = None, max_length: int | None = None, pattern: str | None = None,
                 delta: bool = False, nullable: bool = False, writable: bool = False):
        self.type = json_type(type, "Field") if type is not None else None
        self.unit = unit
        self.native_unit = native_unit
        self.description = description
        self.limits = limits_of(limit, "Field")
        self.items = items if isinstance(items, Field) or items is None else Field(items)
        self.length = length
        self.min_items = min_items
        self.max_items = max_items
        self.enum = list(enum) if enum is not None else None
        self.properties = dict(properties) if properties is not None else None
        self.required = required
        self.max_length = max_length
        self.pattern = pattern
        self.delta = bool(delta)
        self.nullable = bool(nullable)
        self.writable = bool(writable)
        self._check()

    def _check(self) -> None:
        kind = self.type
        if self.unit is not None and (not isinstance(self.unit, str) or not self.unit):
            raise DriverDefinitionError(f"Field unit must be a UCUM code string, got {self.unit!r}")
        if self.unit is not None and kind not in (None, "number", "integer", "array"):
            raise DriverDefinitionError(f"a {kind} Field cannot carry a unit ({self.unit!r})")
        if self.native_unit is not None and self.unit is None:
            raise DriverDefinitionError("Field native_unit needs unit (the unit the value is published in)")
        if self.description is not None and (not isinstance(self.description, str) or len(self.description) > 2000):
            raise DriverDefinitionError("Field description must be a string of at most 2000 characters")
        if (self.items is not None or self.length is not None or self.min_items is not None
                or self.max_items is not None) and kind not in (None, "array"):
            raise DriverDefinitionError(f"items/length/min_items/max_items need an array Field, not {kind}")
        if self.length is not None:
            if not isinstance(self.length, int) or isinstance(self.length, bool) or self.length < 1:
                raise DriverDefinitionError(f"Field length must be a positive integer, got {self.length!r}")
            if self.min_items is not None or self.max_items is not None:
                raise DriverDefinitionError("give an array Field either length or min_items/max_items")
        for name in ("min_items", "max_items", "max_length"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
                raise DriverDefinitionError(f"Field {name} must be a non-negative integer, got {value!r}")
        if self.properties is not None:
            if kind not in (None, "object"):
                raise DriverDefinitionError(f"properties need an object Field, not {kind}")
            for name, sub in self.properties.items():
                if not isinstance(name, str) or not _IDENT.match(name):
                    raise DriverDefinitionError(f"object member name {name!r} must be an identifier")
                if not isinstance(sub, Field):
                    raise DriverDefinitionError(f"object member {name!r} must be a Field, got {sub!r}")
        if self.enum is not None:
            if not self.enum or not all(isinstance(item, (str, bool)) or _finite(item) for item in self.enum):
                raise DriverDefinitionError("Field enum must be a non-empty list of strings, booleans or numbers")
        if (self.max_length is not None or self.pattern is not None) and kind not in (None, "string"):
            raise DriverDefinitionError("max_length/pattern need a string Field")
        if self.pattern is not None:
            try:
                re.compile(self.pattern)
            except (re.error, TypeError) as exc:
                raise DriverDefinitionError(f"Field pattern {self.pattern!r} is not a regular expression") from exc

    # -- schema --------------------------------------------------------------
    def element_unit(self) -> str | None:
        """The unit of a numeric value or of the numeric elements of an array."""
        if self.type == "array" or self.items is not None:
            if self.items is not None and self.items.unit is not None:
                return self.items.unit
            return self.unit
        return self.unit

    def to_schema(self, *, what: str = "field") -> dict[str, Any]:
        """The JSON Schema of this field (bounds are never written here: limits carry them)."""
        schema: dict[str, Any] = {}
        if self.type is not None:
            schema["type"] = [self.type, "null"] if self.nullable else self.type
        kind = self.type
        if kind in ("number", "integer") or (kind is None and self.unit is not None and self.items is None
                                               and self.length is None):
            if self.unit is not None:
                schema["x-mhs-unit"] = self.unit
            if self.delta:
                schema["x-mhs-delta"] = True
        if kind == "array" or self.items is not None or self.length is not None:
            if self.items is not None:
                items = self.items.to_schema(what=f"{what}[*]")
                if self.unit is not None:
                    if self.items.unit is not None and self.items.unit != self.unit:
                        raise DriverDefinitionError(f"{what}: array unit {self.unit!r} differs from its "
                                                    f"element unit {self.items.unit!r}")
                    items["x-mhs-unit"] = self.unit
                    if self.delta:
                        items["x-mhs-delta"] = True
                schema["items"] = items
            elif self.unit is not None:
                schema["items"] = {"type": "number", "x-mhs-unit": self.unit}
            if self.length is not None:
                schema["minItems"] = self.length
                schema["maxItems"] = self.length
            if self.min_items is not None:
                schema["minItems"] = self.min_items
            if self.max_items is not None:
                schema["maxItems"] = self.max_items
        if self.properties is not None:
            schema["properties"] = {name: sub.to_schema(what=f"{what}.{name}")
                                    for name, sub in self.properties.items()}
            if kind == "object":
                # An inline object is closed; a refinement (type None) of a class object only adds
                # units, descriptions and limits, and inherits the class's required members.
                required = [name for name, sub in self.properties.items() if sub.required is not False]
                if required:
                    schema["required"] = required
                schema["additionalProperties"] = False
        if self.enum is not None:
            schema["enum"] = list(self.enum)
        if self.max_length is not None:
            schema["maxLength"] = self.max_length
        if self.pattern is not None:
            schema["pattern"] = self.pattern
        if self.description:
            schema["description"] = self.description
        return schema

    def limit_entries(self, path: str) -> list[tuple[str, Limit]]:
        """``(limit path, Limit)`` for this field at ``path`` and every nested member and element."""
        out = [(limit.key(path), limit) for limit in self.limits]
        if self.properties is not None:
            for name, sub in self.properties.items():
                out.extend(sub.limit_entries(f"{path}.{name}"))
        if self.items is not None:
            out.extend(self.items.limit_entries(f"{path}[*]"))
        return out

    def __repr__(self) -> str:
        parts = [repr(self.type)] if self.type is not None else []
        for key in ("unit", "native_unit", "length", "writable"):
            value = getattr(self, key)
            if value not in (None, False):
                parts.append(f"{key}={value!r}")
        return "Field(" + ", ".join(parts) + ")"


def fields_of(value: Any, what: str) -> dict[str, Field] | None:
    """``input=``/``output=``: ``{name: Field}`` (a :class:`Limit` value is shorthand for ``Field(limit=...)``)."""
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise DriverDefinitionError(f"{what} must be a mapping of field names to Field objects")
    out: dict[str, Field] = {}
    for name, item in value.items():
        if not isinstance(name, str) or not _IDENT.match(name):
            raise DriverDefinitionError(f"{what}: field name {name!r} must be an identifier")
        if isinstance(item, Limit):
            item = Field(limit=item)
        if not isinstance(item, Field):
            raise DriverDefinitionError(f"{what}[{name!r}] must be a Field (or a Limit), got {item!r}")
        out[name] = item
    return out


def absolute_limits(value: Any, what: str) -> dict[str, Limit]:
    """``limits=``: ``{path: Limit}`` or a list of limits that carry an absolute ``path``."""
    if value is None:
        return {}
    out: dict[str, Limit] = {}
    if isinstance(value, Mapping):
        for path, limit in value.items():
            if not isinstance(limit, Limit):
                raise DriverDefinitionError(f"{what}[{path!r}] must be a Limit, got {limit!r}")
            if limit.path is not None and limit.path != path:
                raise DriverDefinitionError(f"{what}[{path!r}]: the Limit's own path {limit.path!r} differs")
            out[str(path)] = limit
        return out
    for limit in limits_of(value, what):
        if not limit.path:
            raise DriverDefinitionError(f"{what}: a Limit in a list needs an absolute path (Limit(path='a.b', ...))")
        out[limit.path] = limit
    return out


# ---------------------------------------------------------------------------
# Fact
# ---------------------------------------------------------------------------


class Fact:
    """One statement about the device for the reference file, with provenance.

    ``source`` is ``vendor_doc`` or ``upstream_code`` (both need ``ref``,
    ``path/in/clone:LINE`` or a manual page); ``operator`` and ``interview``
    facts are written by people, never by a driver author.
    """

    __slots__ = ("text", "source", "ref", "reviewed_by")

    def __init__(self, text: str, source: str, ref: str | None = None, *, reviewed_by: str | None = None):
        if not isinstance(text, str) or not text.strip() or len(text) > 1000:
            raise DriverDefinitionError("Fact text must be a non-empty string of at most 1000 characters")
        if source not in FACT_SOURCES:
            raise DriverDefinitionError(f"Fact source must be one of {list(FACT_SOURCES)}, got {source!r}")
        if source in ("vendor_doc", "upstream_code") and (not isinstance(ref, str) or not ref.strip()):
            raise DriverDefinitionError(f"a {source} Fact must cite ref (path/in/clone:LINE or a manual page)")
        if ref is not None and (not isinstance(ref, str) or not ref or len(ref) > 500):
            raise DriverDefinitionError("Fact ref must be a non-empty string of at most 500 characters")
        if reviewed_by is not None and not isinstance(reviewed_by, str):
            raise DriverDefinitionError("Fact reviewed_by must be a string or None")
        self.text = text
        self.source = source
        self.ref = ref
        self.reviewed_by = reviewed_by

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"text": self.text, "source": self.source}
        if self.ref is not None:
            out["ref"] = self.ref
        out["reviewed_by"] = self.reviewed_by
        return out

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Fact) and self.to_json() == other.to_json()

    def __hash__(self) -> int:
        return hash((self.text, self.source, self.ref, self.reviewed_by))

    def __repr__(self) -> str:
        return f"Fact({self.text!r}, source={self.source!r}, ref={self.ref!r})"


# ---------------------------------------------------------------------------
# Action (config-only form of @action)
# ---------------------------------------------------------------------------


class Action:
    """A capability binding declared without a method body (config-only family drivers).

    The capability id is the key of the family's ``actions`` mapping.  For a
    catalogue class ``input`` refines class fields (units, limits,
    descriptions) and ``output`` is not given; for an ``x-cap.*`` id
    ``input``/``output`` are the inline schema.  ``name`` is the action's
    name in the reference file (``x-mhs-name``).  ``resource`` binds the
    action to one of the driver's ``extra_resources`` instead of its main
    resource (package composition: a class that only accepts another
    resource kind, such as a point cloud on ``sensor.depth`` beside images on
    ``sensor.camera``); ``None`` is the main resource.  ``reenable=True``
    declares the action as the device's explicit re-enable after a safety
    reset (``safety.estop.reenable``, CORE-086): the reset never runs it, the
    latch refuses it like any command, and it must accept an empty input.
    """

    __slots__ = ("name", "input", "output", "limits", "long_running", "cancellable", "max_duration_ms",
                 "risk", "examples", "description", "verb", "safe_state", "exclusive", "requires_permit",
                 "resource", "reenable")

    def __init__(self, *, name: str | None = None, input: Mapping[str, Any] | None = None,
                 output: Mapping[str, Any] | None = None, limits: Any = None, long_running: bool = False,
                 cancellable: bool | None = None, max_duration_ms: int | None = None, risk: str | None = None,
                 examples: Sequence[Mapping[str, Any]] | None = None, description: str | None = None,
                 verb: str | None = None, safe_state: bool = False, exclusive: bool | None = None,
                 requires_permit: bool = False, resource: str | None = None, reenable: bool = False):
        self.name = name
        self.input = fields_of(input, "Action input")
        self.output = fields_of(output, "Action output")
        self.limits = absolute_limits(limits, "Action limits")
        self.long_running = bool(long_running)
        self.cancellable = cancellable
        self.max_duration_ms = max_duration_ms
        if risk is not None and risk not in _RISKS:
            # A typo must not lower the device risk below the author's intent (the R2+ review gate, SAFE-045).
            raise DriverDefinitionError(f"Action risk must be one of {list(_RISKS)} or None, got {risk!r}")
        self.risk = risk
        self.examples = [dict(item) for item in examples or []]
        self.description = description
        self.verb = verb
        self.safe_state = bool(safe_state)
        self.exclusive = exclusive
        self.requires_permit = bool(requires_permit)
        # Validated against the driver's declared resources when the model is built (mhs.driver.model).
        self.resource = resource
        self.reenable = bool(reenable)

    def __repr__(self) -> str:
        return f"Action(name={self.name!r})"

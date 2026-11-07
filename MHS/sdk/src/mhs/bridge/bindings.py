"""Canonical MHS-006 capability-binding loader (``mhs/bindings.json``).

This module is the *single* parser for the normative adapter DSL in
:file:`MHS/spec/06-adapters.md` §4 and §7:

.. code-block:: json

    {
      "mhs_bindings": "1.0",
      "adapter_id": "org.example.robosuite-lift",
      "bindings": [
        {
          "device_id": "mhs://localhost:7401/robosuite/Lift",
          "capability_id": "cap.world.step.v1",
          "resource": "world",
          "binding": {
            "bridge": "gymnasium",
            "kind": "declarative",
            "native": "gymnasium.Env.step",
            "args": {"action": {"from": "input.action", "type": "integer",
                                "enum_map": {"left": 0, "right": 1}}},
            "result": {"map": {"observation": "output.observation"}},
            "constants": {"expected_revision": "ignore"},
            "units": {"input.action": {"from": "1", "to": "1", "factor": 1}},
            "clamp": {"input.action": {"min": 0, "max": 1}},
            "errors": [{"native": "^AssertionError$",
                        "mhs_code": "MHS.DEVICE.PRECONDITION_UNMET",
                        "retryable": false}],
            "concurrency": "exclusive",
            "timeout_ms": 5000
          }
        }
      ]
    }

``load_bindings`` validates the whole document against the normative
``MHS/schema/bindings.schema.json`` and returns a :class:`BindingDocument` whose
entries are already normalised to the internal capability shape consumed by
:class:`mhs.bridge.python.PythonObjectBridge`
(``args``/``result`` specs accepted by :class:`~mhs.bridge.base.FieldMapping`,
``errors`` accepted by :class:`~mhs.bridge.base.ErrorMap`).  File paths, JSON
strings and plain dicts all take that same canonical validation + normalization
path; the internal normalized shape is not an external format.  ``normalize_binding``
does the same for one entry; ``validate_binding`` returns a list of human-
readable errors without raising (pass it a capability dictionary to also check
ADPT-025 against the class ``constraints``).

Every clamp is a hard limit (compiled by :mod:`mhs.limits`): a value outside the
clamp, or outside a wider ``envelope``, raises ``MHS.SAFETY.ENVELOPE_VIOLATION``
before the native call and is never silently clamped (ADPT-024, plan 3.5).
Normalised entries still carry ``enforce_clamp: true`` for introspection.

Besides the MHS-006 keys a binding may state its native invocation form
(MHS-006 §7.3): ``invoke`` is one of :data:`INVOKE_FORMS` (``call`` by
default; ``get``/``set`` for properties, ``await``, ``status``, and
``query``/``write`` with a one-line ``command`` template whose fields are
declared arguments), and ``parse`` turns a text response into a value
(:data:`PARSE_KINDS`).  ``native`` stays a precise symbol; protocol command
text lives in ``command``.  (``bindings.schema.json`` does not list these keys
yet, so they are accepted in in-process bridge configs; documents need the
schema update.)

``strict=True`` (``load_bindings``, ``normalize_binding``,
``validate_binding``) restricts ``errors[].mhs_code`` to the driver subset of
the error registry (``errors.json`` ``driver_subset``).
"""

from __future__ import annotations

import copy
import json
import math
import os
import re
import string
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from mhs import errors as _errors
from mhs.bridge.base import BOOL_TRUE_TOKENS, MappingError, _tokenize, _unit_spec, bool_tokens, make_mhs_error
from mhs.bridge.base import main as _bridge_main

__all__ = [
    "BINDINGS_VERSION",
    "BRIDGE_FAMILIES",
    "CONCURRENCY_LEVELS",
    "INVOKE_FORMS",
    "PARSE_KINDS",
    "BindingDocument",
    "load_bindings",
    "normalize_binding",
    "validate_binding",
]

#: Version of the bindings document shape (``mhs_bindings``).
BINDINGS_VERSION = "1.0"

#: Normative bridge family enum (mirrors ``MHS/schema/adapter.schema.json``).
BRIDGE_FAMILIES = (
    "python-object",
    "gymnasium",
    "dm-env",
    "mujoco",
    "pybullet",
    "isaac-sim",
    "isaac-lab",
    "isaac-gym",
    "gazebo",
    "ros2",
    "ros1",
    "webots",
    "unity",
    "sapien",
    "drake",
    "brax-mjx",
    "habitat",
    "airsim",
    "lerobot-real",
    "http-api",
    "mcp-proxy",
    "scpi-visa",
    "serial",
    "sila2",
    "opentrons",
    "micromanager",
    "flowchem",
    "madsci",
    "pylabrobot",
    "bluesky-ophyd",
    "qcodes",
    "cli-process",
    "docker",
    "replay",
    "other",
)

#: ``concurrency`` vocabulary, strictest last.
CONCURRENCY_LEVELS = ("shared", "serialized", "exclusive")

#: Native invocation forms (MHS-006 §7.3): ``call`` a method (awaitables and
#: Status-like returns are awaited), ``get``/``set`` a property, ``await`` a
#: coroutine, wait for a ``status`` object, or send a ``query``/``write``
#: command template through the target's request/response method.
INVOKE_FORMS = ("call", "get", "set", "await", "status", "query", "write")

#: ``parse`` kinds for string responses (``query`` and SCPI/serial commands).
PARSE_KINDS = ("raw", "str", "float", "int", "bool", "regex")
_PARSE_KEYS = {"kind", "pattern", "group", "field", "true", "false", "description"}
_CONCURRENCY_RANK = {name: index for index, name in enumerate(CONCURRENCY_LEVELS)}

_ENTRY_KEYS = {"device_id", "capability_id", "resource", "binding"}
_INNER_KEYS = {
    "bridge",
    "kind",
    "native",
    "args",
    "result",
    "constants",
    "units",
    "clamp",
    "errors",
    "concurrency",
    "timeout_ms",
    "positional",
    "inputs",
    "required_inputs",
    "unsupported",
    "shim",
    "description",
    "invoke",
    "command",
    "parse",
}
_ARG_KEYS = {
    "from",
    "value",
    "type",
    "enum_map",
    "map",
    "unit",
    "units",
    "clamp",
    "required",
    "default",
    "unsupported",
    "reason",
    "description",
}
_RESULT_KEYS = {"map"}
_RESULT_TRANSFORM_KEYS = {
    "from",
    "path",
    "type",
    "enum_map",
    "map",
    "unit",
    "units",
    "clamp",
    "required",
    "description",
}
_INPUT_DECL_KEYS = {"required", "unsupported", "reason", "type", "description", "unit"}
_ERROR_RULE_KEYS = {"native", "mhs_code", "retryable", "description"}
_CLAMP_KEYS = {"min", "max", "envelope", "limits", "unit", "reason"}
_ENVELOPE_KEYS = {"min", "max", "unit", "reason"}
_UNIT_KEYS = {"from", "to", "factor", "offset"}
_JSON_TYPES = ("integer", "number", "string", "boolean", "array", "object")
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
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DOTTED_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")
_CAPABILITY_ID = re.compile(r"^(cap|x-cap)\.[a-z0-9_.-]+\.v[0-9]+$")
_DEVICE_ID = re.compile(r"^mhs://[^\s/]+(/[^\s]+)+$")
_RESOURCE_ID = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_ADAPTER_ID = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,127}$")
_MHS_CODE = re.compile(r"^MHS\.[A-Z0-9_]+\.[A-Z0-9_]+$")
_MHS_VERSION = re.compile(r"^1\.[0-9]+$")

#: Private construction token.  ``BindingDocument`` is a *validated internal*
#: type, not an external input format: only :func:`load_bindings` (and the
#: loader's own normalization path) may create one.  A caller-controlled dict
#: can therefore never select the internal fast path.
_DOCUMENT_TOKEN = object()


def _normalized_entry_errors(entry: Any, index: int) -> list[str]:
    """Invariants every normalized binding entry must satisfy (ADPT-024/025).

    These checks are deliberately repeated at bridge compilation time; a
    document that was valid when loaded must not become an unbounded or
    silently-clamping binding through later mutation.
    """
    label = f"bindings[{index}]"
    if not isinstance(entry, Mapping):
        return [f"{label}: normalized entry must be an object"]
    errors: list[str] = []
    timeout = entry.get("timeout_ms")
    if isinstance(timeout, bool) or not isinstance(timeout, int):
        errors.append(f"{label}: timeout_ms must be an integer")
    elif timeout <= 0:
        errors.append(f"{label}: timeout_ms must be positive (ADPT-025)")
    elif timeout > 86_400_000:
        errors.append(f"{label}: timeout_ms exceeds the 24 h sanity bound")
    if entry.get("concurrency") not in _CONCURRENCY_RANK:
        errors.append(f"{label}: concurrency is missing or invalid")
    if entry.get("kind") not in ("declarative", "shim"):
        errors.append(f"{label}: kind is missing or invalid")
    native = entry.get("native")
    if not isinstance(native, str) or not native:
        errors.append(f"{label}: native must be a non-empty symbol")
    for section in ("args", "result"):
        rules = entry.get(section)
        if rules is None:
            continue
        if not isinstance(rules, Mapping):
            errors.append(f"{label}.{section} must be an object")
            continue
        for target, rule in rules.items():
            if isinstance(rule, Mapping) and "clamp" in rule and rule.get("enforce_clamp") is not True:
                errors.append(
                    f"{label}.{section}[{target!r}]: clamp lacks canonical "
                    "enforce_clamp semantics (ADPT-024)"
                )
    return errors


def _harden_normalized_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Copy one normalized entry and force canonical hard-envelope clamps."""

    item = copy.deepcopy(dict(entry))
    item["enforce_clamp"] = True
    for section in ("args", "result"):
        rules = item.get(section)
        if not isinstance(rules, Mapping):
            continue
        for target, rule in rules.items():
            if isinstance(rule, Mapping) and "clamp" in rule:
                rule["enforce_clamp"] = True
    return item


class BindingDocument(dict):
    """A validated, normalised ``mhs/bindings.json`` document.

    It is a plain ``dict`` (JSON-serialisable apart from the fact that its
    entries carry plain rule specifications) plus convenience accessors.

    Construction is controlled: :func:`load_bindings` is the only public
    factory.  The token guard keeps a caller-built ``dict`` from masquerading as
    a validated document and selecting the internal fast path.
    """

    def __init__(
        self,
        *,
        mhs_bindings: str,
        adapter_id: str,
        bindings: Sequence[Mapping[str, Any]],
        title: str | None = None,
        _token: object | None = None,
    ):
        if _token is not _DOCUMENT_TOKEN:
            raise TypeError(
                "BindingDocument is a validated internal type; "
                "use mhs.bridge.bindings.load_bindings() to load a document"
            )
        if not isinstance(bindings, (list, tuple)) or not bindings:
            raise _manifest_error(
                "invalid normalized BindingDocument invariants",
                ["bindings must be a non-empty array"],
            )
        errors: list[str] = []
        if not isinstance(mhs_bindings, str) or not _MHS_VERSION.match(mhs_bindings):
            errors.append("mhs_bindings does not match ^1\\.[0-9]+$")
        if not isinstance(adapter_id, str) or not _ADAPTER_ID.match(adapter_id):
            errors.append("adapter_id is not a valid adapter id")
        for index, entry in enumerate(bindings):
            errors.extend(_normalized_entry_errors(entry, index))
        if errors:
            raise _manifest_error("invalid normalized BindingDocument invariants", errors)
        payload: dict[str, Any] = {
            "mhs_bindings": str(mhs_bindings),
            "adapter_id": str(adapter_id),
            "bindings": [_harden_normalized_entry(item) for item in bindings],
        }
        if title is not None:
            payload["title"] = str(title)
        super().__init__(payload)

    @property
    def mhs_bindings(self) -> str:
        return str(self.get("mhs_bindings", ""))

    @property
    def adapter_id(self) -> str:
        return str(self.get("adapter_id", ""))

    @property
    def bindings(self) -> list[dict[str, Any]]:
        return list(self.get("bindings") or [])

    def by_capability(self) -> dict[str, dict[str, Any]]:
        """Capability id -> normalised binding entry (duplicates collapse)."""

        return {
            str(entry["capability_id"]): entry
            for entry in self.bindings
            if entry.get("capability_id")
        }

    def for_device(self, device_id: str) -> list[dict[str, Any]]:
        return [entry for entry in self.bindings if entry.get("device_id") == device_id]

    def get_binding(self, capability_id: str) -> dict[str, Any] | None:
        for entry in self.bindings:
            if entry.get("capability_id") == capability_id:
                return entry
        return None

    def __iter__(self) -> Iterator[str]:  # pragma: no cover - dict contract
        return super().__iter__()


# ---------------------------------------------------------------------------
# small validation helpers
# ---------------------------------------------------------------------------


def _manifest_error(message: str, errors: Sequence[str], **extra: Any) -> Exception:
    details: dict[str, Any] = {"errors": list(errors)}
    details.update(extra)
    return make_mhs_error(
        "MHS.ADAPTER.MANIFEST_INVALID",
        message,
        {"retryable": False, "details": details},
    )


def _path_root(path: str) -> str:
    head = path.strip()
    for prefix in ("input.", "output.", "args.", "$."):
        if head.startswith(prefix):
            return prefix[:-1]
    if head in ("input", "output", "args", "$", "result"):
        return head
    return ""


def _check_path(path: str, root: str, label: str) -> str | None:
    if not isinstance(path, str) or not path.strip():
        return f"{label} must be a non-empty field path"
    try:
        _tokenize(path)
    except MappingError as exc:
        return f"{label} {path!r} is malformed: {exc}"
    actual = _path_root(path)
    if actual and actual != root:
        return f"{label} {path!r} must be rooted at {root!r} (MHS-006 §7.1)"
    return None


def _is_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def _unit_errors(spec: Any, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(spec, Mapping):
        return [f"{label} must be an object with explicit 'from' and 'to' (ADPT-021/023)"]
    unknown = set(spec) - _UNIT_KEYS
    if unknown:
        errors.append(f"{label} has unknown keys {sorted(unknown)}")
    for required in ("from", "to"):
        value = spec.get(required)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label} requires an explicit non-empty {required!r} UCUM code (ADPT-023)")
    if errors:
        return errors
    try:
        _unit_spec(spec)
    except MappingError as exc:
        errors.append(f"{label} is not a valid unit conversion: {exc}")
    return errors


def _clamp_errors(spec: Any, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(spec, Mapping):
        return [f"{label} must be an object with 'min'/'max'"]
    unknown = set(spec) - _CLAMP_KEYS
    if unknown:
        errors.append(f"{label} has unknown keys {sorted(unknown)}")
    low, high = spec.get("min"), spec.get("max")
    if low is None and high is None:
        errors.append(f"{label} requires 'min' and/or 'max'")
    for name, value in (("min", low), ("max", high)):
        if value is not None and not _is_number(value):
            errors.append(f"{label}.{name} must be a number")
    if _is_number(low) and _is_number(high) and float(low) > float(high):
        errors.append(f"{label} min is greater than max")
    envelope = spec.get("envelope", spec.get("limits"))
    if envelope is not None and "envelope" in spec and "limits" in spec:
        errors.append(f"{label} declares both 'envelope' and 'limits'")
    if envelope is not None and not isinstance(envelope, Mapping):
        errors.append(f"{label}.envelope must be an object")
    elif isinstance(envelope, Mapping):
        unknown_env = set(envelope) - _ENVELOPE_KEYS
        if unknown_env:
            errors.append(f"{label}.envelope has unknown keys {sorted(unknown_env)}")
        env_low, env_high = envelope.get("min"), envelope.get("max")
        for name, value in (("min", env_low), ("max", env_high)):
            if value is not None and not _is_number(value):
                errors.append(f"{label}.envelope.{name} must be a number")
        if _is_number(env_low) and _is_number(env_high) and float(env_low) > float(env_high):
            errors.append(f"{label}.envelope min is greater than max")
    return errors


def _unit_to(spec: Any) -> str | None:
    """The unit a value has after a ``unit``/``units`` conversion (``None``: no conversion)."""

    if isinstance(spec, Mapping):
        to = spec.get("to")
    elif isinstance(spec, (list, tuple)) and len(spec) == 2:
        to = spec[1]
    else:
        return None
    return to if isinstance(to, str) and to.strip() else None


def _clamp_unit_errors(spec: Any, value_unit: str | None, label: str) -> list[str]:
    """A clamp is checked after the conversion: its (and its envelope's) unit is ``value_unit``."""

    if not isinstance(spec, Mapping):
        return []
    declared: list[tuple[str, Any]] = [(label, spec.get("unit"))]
    envelope = spec.get("envelope", spec.get("limits"))
    if isinstance(envelope, Mapping):
        declared.append((f"{label}.envelope", envelope.get("unit")))
    errors: list[str] = []
    seen: str | None = None
    for where, unit in declared:
        if unit is None:
            continue
        if not isinstance(unit, str) or not unit.strip():
            errors.append(f"{where}.unit must be a non-empty UCUM code")
            continue
        if value_unit is not None and unit != value_unit:
            errors.append(
                f"{where}.unit {unit!r} differs from {value_unit!r}, the unit the value has when the "
                "clamp is checked (after the unit conversion); conversions are never implicit (plan 3.5)"
            )
        elif seen is not None and unit != seen:
            errors.append(f"{where}.unit {unit!r} disagrees with {seen!r}")
        seen = unit
    return errors


def _error_rule_errors(rule: Any, index: int, *, strict: bool = False) -> list[str]:
    label = f"errors[{index}]"
    errors: list[str] = []
    if not isinstance(rule, Mapping):
        return [f"{label} must be an object"]
    unknown = set(rule) - _ERROR_RULE_KEYS
    if unknown:
        errors.append(f"{label} has unknown keys {sorted(unknown)}")
    pattern = rule.get("native")
    if not isinstance(pattern, str) or not pattern:
        errors.append(f"{label}.native must be a non-empty regex")
    elif len(pattern) > 512:
        errors.append(f"{label}.native regex is longer than 512 characters")
    else:
        try:
            re.compile(pattern)
        except re.error as exc:
            errors.append(f"{label}.native is not a valid regex: {exc}")
    code = rule.get("mhs_code")
    if not isinstance(code, str) or not _MHS_CODE.match(code):
        errors.append(f"{label}.mhs_code must be an 'MHS.<AREA>.<DETAIL>' code")
    elif strict and not _errors.is_driver_code(code):
        errors.append(
            f"{label}.mhs_code {code!r} is not in the driver subset of the error registry "
            f"(strict mode; allowed: {sorted(_errors.DRIVER_SUBSET)})"
        )
    if "retryable" in rule and not isinstance(rule["retryable"], bool):
        errors.append(f"{label}.retryable must be a boolean")
    return errors


def _enum_errors(spec: Mapping[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    forms = [key for key in ("enum_map", "map") if key in spec]
    if len(forms) > 1:
        errors.append(f"{label} declares both 'enum_map' and 'map' (use one)")
    if forms:
        mapping = spec[forms[0]]
        if not isinstance(mapping, Mapping) or not mapping:
            errors.append(f"{label}.{forms[0]} must be a non-empty object")
    return errors


def _type_errors(spec: Mapping[str, Any], label: str) -> list[str]:
    if "type" not in spec:
        return []
    declared = spec["type"]
    if not isinstance(declared, str) or declared not in _TYPE_ALIASES:
        return [f"{label}.type {declared!r} is not one of {sorted(_JSON_TYPES)}"]
    return []


def _arg_errors(target: str, spec: Any, *, bridge: str | None) -> list[str]:
    label = f"args[{target!r}]"
    if not isinstance(spec, Mapping):
        return [f"{label} must be an object"]
    errors: list[str] = []
    unknown = set(spec) - _ARG_KEYS
    if unknown:
        errors.append(f"{label} has non-canonical keys {sorted(unknown)}")
    if bridge == "python-object" and not _IDENTIFIER.match(str(target)):
        errors.append(f"{label} is not a valid Python keyword argument name")
    if not str(target).strip():
        errors.append(f"{label} has an empty native argument name")
    unsupported = spec.get("unsupported", False)
    if not isinstance(unsupported, bool):
        errors.append(f"{label}.unsupported must be a boolean")
    reason = spec.get("reason")
    if reason is not None and (not isinstance(reason, str) or not reason.strip()):
        errors.append(f"{label}.reason must be a non-empty string")
    mapped_keys = [key for key in ("from", "value", "default") if key in spec]
    if unsupported:
        if mapped_keys:
            errors.append(f"{label} cannot be 'unsupported' and also declare {mapped_keys}")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(
                f"{label} declares \"unsupported\": true but needs a non-empty 'reason' (ADPT-040)"
            )
    else:
        if "from" in spec and "value" in spec:
            errors.append(f"{label} cannot combine 'from' and 'value'")
        if "from" not in spec and "value" not in spec and "default" not in spec:
            errors.append(f"{label} needs 'from', 'value', 'default' or \"unsupported\": true")
        if "from" in spec:
            problem = _check_path(spec["from"], "input", f"{label}.from")
            if problem:
                errors.append(problem)
    errors.extend(_type_errors(spec, label))
    errors.extend(_enum_errors(spec, label))
    if "unit" in spec and "units" in spec:
        errors.append(f"{label} cannot combine 'unit' and 'units'")
    if "unit" in spec:
        errors.extend(_unit_errors(spec["unit"], f"{label}.unit"))
    if "units" in spec:
        errors.extend(_unit_errors(spec["units"], f"{label}.units"))
    if "clamp" in spec:
        errors.extend(_clamp_errors(spec["clamp"], f"{label}.clamp"))
        errors.extend(_clamp_unit_errors(spec["clamp"], _unit_to(spec.get("unit", spec.get("units"))),
                                         f"{label}.clamp"))
    return errors


def _inverted_result_target(target: str) -> bool:
    """A result.map key that is a native path (``$``, ``output.x``): the map is inverted."""

    return target.startswith("$") or target.startswith(("output.", "input.", "args."))


def _result_errors(result: Any, *, kind: str) -> list[str]:
    if result is None:
        return [] if kind == "shim" else [
            "binding requires 'result.map' (ADPT-022: how the native result becomes "
            "the capability output)"
        ]
    if not isinstance(result, Mapping):
        return ["binding.result must be an object with a 'map' member"]
    unknown = set(result) - _RESULT_KEYS
    if unknown:
        return [f"binding.result has unknown keys {sorted(unknown)} (use 'map')"]
    mapping = result.get("map")
    if not isinstance(mapping, Mapping) or not mapping:
        return ["binding.result.map must be a non-empty object"]
    errors: list[str] = []
    for target, source in mapping.items():
        label = f"result.map[{target!r}]"
        if not str(target).strip():
            errors.append("result.map has an empty output field name")
        elif _inverted_result_target(str(target)):
            errors.append(
                f"result.map key {str(target)!r} is a native path, not an output field name "
                "(keys are output fields, values native paths; is the map inverted?)"
            )
        if isinstance(source, str):
            problem = _check_path(source, "output", label)
            if problem:
                errors.append(problem)
        elif isinstance(source, Mapping):
            unknown_transform = set(source) - _RESULT_TRANSFORM_KEYS
            if unknown_transform:
                errors.append(f"{label} has unknown keys {sorted(unknown_transform)}")
            path = source.get("from", source.get("path"))
            if not isinstance(path, str):
                errors.append(f"{label} needs a native path string or a transform with 'from'")
            else:
                problem = _check_path(path, "output", label)
                if problem:
                    errors.append(problem)
            errors.extend(_type_errors(source, label))
            errors.extend(_enum_errors(source, label))
            if "unit" in source:
                errors.extend(_unit_errors(source["unit"], f"{label}.unit"))
            if "clamp" in source:
                errors.extend(_clamp_errors(source["clamp"], f"{label}.clamp"))
                errors.extend(_clamp_unit_errors(source["clamp"], _unit_to(source.get("unit")),
                                                 f"{label}.clamp"))
        else:
            errors.append(f"{label} must be a native path string or a transform object")
    return errors


def _constant_errors(constants: Any, args: Any) -> list[str]:
    if constants is None:
        return []
    if not isinstance(constants, Mapping):
        return ["binding.constants must be an object"]
    errors: list[str] = []
    if not isinstance(args, Mapping):
        return errors
    for key in constants:
        if not str(key).strip():
            errors.append("binding.constants has an empty argument name")
        if key in args:
            spec = args[key]
            if isinstance(spec, Mapping) and ("from" in spec or "value" in spec):
                errors.append(
                    f"binding.constants[{key!r}] conflicts with an explicit args mapping"
                )
    return errors


def _target_lookup(key: str, specs: Mapping[str, Any]) -> str | None:
    """Resolve a units/clamp key to an args/result target name."""

    stripped = key
    for prefix in ("input.", "output."):
        if stripped.startswith(prefix):
            stripped = stripped[len(prefix) :]
            break
    if key in specs:
        return key
    if stripped in specs:
        return stripped
    for target, spec in specs.items():
        if isinstance(spec, Mapping):
            source = spec.get("from", spec.get("path"))
            if source == key or source == stripped:
                return str(target)
    return None


def parse_spec_errors(parse: Any, label: str = "binding.parse") -> list[str]:
    """Errors of a ``parse`` spec ``{kind, pattern?, group?, field?, true?, false?}`` (empty: valid).

    Kind ``bool`` is strict (an unrecognised reply is an error, never
    ``False``), so a ``true`` token other than ``1``/``ON``/``TRUE`` needs its
    ``false`` token, and the two token sets may not overlap.
    """

    if not isinstance(parse, Mapping):
        return [f"{label} must be an object with a 'kind'"]
    errors: list[str] = []
    unknown = set(parse) - _PARSE_KEYS
    if unknown:
        errors.append(f"{label} has unknown keys {sorted(unknown)}")
    kind = parse.get("kind", "raw")
    if kind not in PARSE_KINDS:
        errors.append(f"{label}.kind {kind!r} must be one of {list(PARSE_KINDS)}")
    pattern = parse.get("pattern")
    if pattern is not None:
        if not isinstance(pattern, str) or not pattern or len(pattern) > 512:
            errors.append(f"{label}.pattern must be a non-empty regex of at most 512 characters")
        else:
            try:
                re.compile(pattern)
            except re.error as exc:
                errors.append(f"{label}.pattern is not a valid regex: {exc}")
    if kind == "regex" and pattern is None:
        errors.append(f"{label} of kind 'regex' needs a 'pattern'")
    group = parse.get("group")
    if group is not None and (isinstance(group, bool) or not isinstance(group, (int, str))):
        errors.append(f"{label}.group must be a group number or name")
    for key in ("field", "true", "false"):
        value = parse.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            errors.append(f"{label}.{key} must be a non-empty string")
    if kind == "bool" and not errors:
        true = parse.get("true")
        if true is not None and parse.get("false") is None and true.strip().upper() not in BOOL_TRUE_TOKENS:
            errors.append(f"{label}: a 'true' token {true!r} needs its 'false' token (any other reply "
                          "is unparseable, never false)")
        true_set, false_set = bool_tokens(parse)
        if true_set & false_set:
            errors.append(f"{label}: the true and false tokens overlap ({sorted(true_set & false_set)})")
    return errors


def template_fields(template: str) -> list[str]:
    """The replacement field names of a ``str.format`` command template."""

    names: list[str] = []
    for _literal, name, _spec, _conversion in string.Formatter().parse(template):
        if name is None:
            continue
        names.append(name)
    return names


def command_template_errors(template: Any, available: Sequence[str], label: str) -> list[str]:
    """Errors of a command template: one line, plain named fields from ``available``."""

    if not isinstance(template, str) or not template.strip():
        return [f"{label} must be a non-empty command template"]
    if any(char in template for char in "\r\n") or any(ord(char) < 32 for char in template):
        return [f"{label} must be one line without control characters"]
    try:
        names = template_fields(template)
    except ValueError as exc:
        return [f"{label} {template!r} is not a valid template: {exc}"]
    errors: list[str] = []
    for name in names:
        if not _IDENTIFIER.match(name):
            errors.append(f"{label} field {{{name}}} must be a plain argument name (no attribute or index access)")
        elif name not in available:
            errors.append(f"{label} field {{{name}}} is not a declared argument")
    return errors


def _invoke_errors(binding: Mapping[str, Any], args: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    invoke = binding.get("invoke", "call")
    if invoke not in INVOKE_FORMS:
        return [f"binding.invoke {invoke!r} must be one of {list(INVOKE_FORMS)}"]
    constants = binding.get("constants") if isinstance(binding.get("constants"), Mapping) else {}
    declared = [name for name, spec in args.items()
                if not (isinstance(spec, Mapping) and spec.get("unsupported") is True)]
    declared += [name for name in constants if name not in args]
    command = binding.get("command")
    if invoke in ("query", "write"):
        errors.extend(command_template_errors(command, declared, "binding.command"))
        if binding.get("positional"):
            errors.append(f"invoke {invoke!r} formats 'command'; 'positional' is not allowed")
    elif command is not None:
        errors.append(f"binding.command is only used by invoke 'query' or 'write', not {invoke!r}")
    if invoke == "get" and declared:
        errors.append("invoke 'get' reads a property and takes no arguments")
    if invoke == "set":
        if len(declared) != 1:
            errors.append(f"invoke 'set' assigns one value; declare exactly one argument (found {len(declared)})")
        if binding.get("positional"):
            errors.append("invoke 'set' does not take 'positional'")
    if "parse" in binding:
        errors.extend(parse_spec_errors(binding.get("parse")))
    return errors


def _binding_errors(binding: Mapping[str, Any], *, capability: Mapping[str, Any] | None,
                    strict: bool = False) -> list[str]:
    errors: list[str] = []
    unknown = set(binding) - _INNER_KEYS
    if unknown:
        errors.append(f"binding has unknown keys {sorted(unknown)}")
    bridge = binding.get("bridge")
    if not isinstance(bridge, str) or not bridge:
        errors.append("binding requires 'bridge' (ADPT-020)")
    elif bridge not in BRIDGE_FAMILIES:
        errors.append(f"binding.bridge {bridge!r} is not a normative bridge family")
    # ADPT-020 lists device/capability/resource/bridge/native as required;
    # declarative is the default kind, shims MUST say so (ADPT-041).
    kind = binding.get("kind", "declarative")
    if kind not in ("declarative", "shim"):
        errors.append("binding.kind must be 'declarative' or 'shim'")
    native = binding.get("native")
    if not isinstance(native, str) or not native.strip():
        errors.append("binding requires a precise 'native' symbol (ADPT-020)")
    elif re.search(r"\s", native):
        errors.append(
            f"binding.native {native!r} is not a precise symbol (no whitespace; "
            "module/class/function or protocol command)"
        )
    if kind == "declarative" and bridge == "python-object" and isinstance(native, str):
        if not _DOTTED_SYMBOL.match(native):
            errors.append(
                f"binding.native {native!r} is not a Python attribute path for the "
                "python-object bridge"
            )
    if kind == "shim":
        shim = binding.get("shim")
        if not isinstance(shim, str) or not shim.strip() or ":" not in shim:
            errors.append("kind 'shim' requires binding.shim as a 'path:function' reference")
    args = binding.get("args", {})
    if not isinstance(args, Mapping):
        errors.append("binding.args must be an object")
        args = {}
    else:
        for target, spec in args.items():
            errors.extend(_arg_errors(str(target), spec, bridge=bridge if isinstance(bridge, str) else None))
    errors.extend(_constant_errors(binding.get("constants"), args))
    errors.extend(_result_errors(binding.get("result"), kind=str(kind)))
    # units / clamp: keyed by target and folded into args or result.
    result_map = {}
    if isinstance(binding.get("result"), Mapping) and isinstance(binding["result"].get("map"), Mapping):
        result_map = dict(binding["result"]["map"])
    result_specs = {
        str(target): ({"from": source} if isinstance(source, str) else dict(source))
        for target, source in result_map.items()
        if isinstance(source, (str, Mapping))
    }
    # the unit each target has after its conversion (inline or binding-level)
    converted: dict[tuple[str, str], str] = {}
    for kind, specs in (("args", args), ("result", result_specs)):
        for target, spec in specs.items():
            if isinstance(spec, Mapping):
                to = _unit_to(spec.get("unit", spec.get("units")))
                if to is not None:
                    converted[(kind, str(target))] = to
    if isinstance(binding.get("units"), Mapping):
        for key, value in binding["units"].items():
            to = _unit_to(value)
            arg_target = _target_lookup(str(key), args)
            result_target = _target_lookup(str(key), result_specs)
            if to is not None and (arg_target is None) != (result_target is None):
                kind, target = ("args", arg_target) if arg_target is not None else ("result", result_target)
                converted[(kind, str(target))] = to
    for section in ("units", "clamp"):
        raw = binding.get(section)
        if raw is None:
            continue
        if not isinstance(raw, Mapping):
            errors.append(f"binding.{section} must be an object keyed by target")
            continue
        seen: set[str] = set()
        for key, value in raw.items():
            label = f"binding.{section}[{key!r}]"
            if section == "units":
                errors.extend(_unit_errors(value, label))
            else:
                errors.extend(_clamp_errors(value, label))
            arg_target = _target_lookup(str(key), args)
            result_target = _target_lookup(str(key), result_specs)
            if arg_target is None and result_target is None:
                errors.append(
                    f"{label} does not match any declared args/result target "
                    "(mapping to an undeclared field is a manifest error; MHS-006 §7.1)"
                )
                continue
            if arg_target is not None and result_target is not None:
                errors.append(f"{label} is ambiguous between an input and an output target")
                continue
            resolved = arg_target if arg_target is not None else result_target
            if resolved in seen:
                errors.append(f"{label} is declared more than once")
            seen.add(str(resolved))
            if section == "clamp":
                kind = "args" if arg_target is not None else "result"
                errors.extend(_clamp_unit_errors(value, converted.get((kind, str(resolved))), label))
            source_spec = args.get(resolved) if arg_target is not None else result_specs.get(resolved)
            if isinstance(source_spec, Mapping):
                inline = "unit" if section == "units" else "clamp"
                if inline in source_spec:
                    errors.append(f"{label} duplicates the inline {inline!r} transform")
    # errors[]
    errors_spec = binding.get("errors")
    if errors_spec is not None:
        if isinstance(errors_spec, Mapping):
            errors.append(
                "binding.errors must be an ordered array of "
                "{native, mhs_code, retryable} rules (MHS-006 §4.1/§7.2), not an object"
            )
        elif not isinstance(errors_spec, (list, tuple)):
            errors.append("binding.errors must be an ordered array")
        else:
            for index, rule in enumerate(errors_spec):
                errors.extend(_error_rule_errors(rule, index, strict=strict))
    # ADPT-025: concurrency and timeout are mandatory.
    concurrency = binding.get("concurrency")
    if concurrency is None:
        errors.append("binding requires 'concurrency' (ADPT-025)")
    elif concurrency not in _CONCURRENCY_RANK:
        errors.append(
            f"binding.concurrency {concurrency!r} must be one of {list(CONCURRENCY_LEVELS)}"
        )
    timeout = binding.get("timeout_ms")
    if timeout is None:
        errors.append("binding requires 'timeout_ms' (ADPT-025); a binding must not block indefinitely")
    elif isinstance(timeout, bool) or not isinstance(timeout, int):
        errors.append("binding.timeout_ms must be an integer")
    elif timeout <= 0:
        errors.append("binding.timeout_ms must be positive")
    elif timeout > 86_400_000:
        errors.append("binding.timeout_ms exceeds the 24 h sanity bound")
    constraints: Mapping[str, Any] = {}
    if isinstance(capability, Mapping):
        raw_constraints = capability.get("constraints")
        if isinstance(raw_constraints, Mapping):
            constraints = raw_constraints
    if constraints:
        class_concurrency = constraints.get("concurrency")
        if (
            isinstance(class_concurrency, str)
            and class_concurrency in _CONCURRENCY_RANK
            and isinstance(concurrency, str)
            and concurrency in _CONCURRENCY_RANK
            and _CONCURRENCY_RANK[concurrency] < _CONCURRENCY_RANK[class_concurrency]
        ):
            errors.append(
                f"binding.concurrency {concurrency!r} is weaker than the class default "
                f"{class_concurrency!r} (ADPT-025)"
            )
        max_duration = constraints.get("max_duration_ms")
        if isinstance(max_duration, int) and not isinstance(max_duration, bool):
            if isinstance(timeout, int) and not isinstance(timeout, bool) and timeout > max_duration:
                errors.append(
                    f"binding.timeout_ms {timeout} exceeds the class max_duration_ms "
                    f"{max_duration} (ADPT-025)"
                )
    # positional invocation names
    positional = binding.get("positional")
    if positional is not None:
        if not isinstance(positional, (list, tuple)) or not all(
            isinstance(name, str) for name in positional
        ):
            errors.append("binding.positional must be an array of argument names")
        else:
            if len(set(positional)) != len(positional):
                errors.append("binding.positional contains duplicate names")
            available = set(args) | set(binding.get("constants") or {})
            for name in positional:
                if name not in available:
                    errors.append(f"binding.positional names undeclared argument {name!r}")
    # required-input declarations
    errors.extend(_input_declaration_errors(binding, args))
    errors.extend(_totality_errors(binding, args))
    errors.extend(_invoke_errors(binding, args))
    return errors


def _input_declaration_errors(binding: Mapping[str, Any], args: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    declared = binding.get("inputs")
    if declared is not None:
        if not isinstance(declared, Mapping):
            errors.append("binding.inputs must be an object keyed by capability input")
        else:
            for name, decl in declared.items():
                label = f"binding.inputs[{name!r}]"
                if not isinstance(decl, Mapping):
                    errors.append(f"{label} must be an object")
                    continue
                unknown = set(decl) - _INPUT_DECL_KEYS
                if unknown:
                    errors.append(f"{label} has unknown keys {sorted(unknown)}")
                if "required" in decl and not isinstance(decl["required"], bool):
                    errors.append(f"{label}.required must be a boolean")
                if "unsupported" in decl and not isinstance(decl["unsupported"], bool):
                    errors.append(f"{label}.unsupported must be a boolean")
                if decl.get("unsupported") and (
                    not isinstance(decl.get("reason"), str) or not decl["reason"].strip()
                ):
                    errors.append(f"{label} declares unsupported but needs a non-empty reason")
    required = binding.get("required_inputs")
    if required is not None:
        if not isinstance(required, (list, tuple)) or not all(
            isinstance(name, str) and name.strip() for name in required
        ):
            errors.append("binding.required_inputs must be an array of non-empty input names")
        elif len(set(required)) != len(required):
            errors.append("binding.required_inputs contains duplicate names")
    raw_unsupported = binding.get("unsupported")
    if raw_unsupported is not None:
        if isinstance(raw_unsupported, Mapping):
            for name, reason in raw_unsupported.items():
                if isinstance(reason, Mapping):
                    if not isinstance(reason.get("reason"), str) or not reason["reason"].strip():
                        errors.append(f"binding.unsupported[{name!r}] needs a non-empty 'reason'")
                elif not isinstance(reason, str) or not reason.strip():
                    errors.append(f"binding.unsupported[{name!r}] needs a non-empty reason string")
        elif isinstance(raw_unsupported, (list, tuple)):
            for index, item in enumerate(raw_unsupported):
                if isinstance(item, str) and item.strip():
                    continue
                if isinstance(item, Mapping):
                    name = item.get("input", item.get("name"))
                    reason = item.get("reason")
                    if not isinstance(name, str) or not name.strip():
                        errors.append(f"binding.unsupported[{index}] needs an 'input' name")
                    if not isinstance(reason, str) or not reason.strip():
                        errors.append(f"binding.unsupported[{index}] needs a non-empty 'reason'")
                    continue
                errors.append(f"binding.unsupported[{index}] must be a name or declaration object")
        else:
            errors.append("binding.unsupported must be an object or an array")
    return errors


def _declared_required_inputs(binding: Mapping[str, Any]) -> list[str]:
    names: list[str] = []
    required = binding.get("required_inputs")
    if isinstance(required, (list, tuple)):
        names.extend(str(name) for name in required)
    inputs = binding.get("inputs")
    if isinstance(inputs, Mapping):
        for name, decl in inputs.items():
            if isinstance(decl, Mapping) and decl.get("required") is True:
                names.append(str(name))
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def _short_input_name(name: str) -> str:
    text = str(name).strip()
    for prefix in ("input.", "output."):
        if text.startswith(prefix):
            return text[len(prefix) :]
    return text


def _unsupported_inputs(binding: Mapping[str, Any], args: Mapping[str, Any]) -> set[str]:
    names: set[str] = set()
    inputs = binding.get("inputs")
    if isinstance(inputs, Mapping):
        for name, decl in inputs.items():
            if isinstance(decl, Mapping) and decl.get("unsupported") is True:
                names.add(_short_input_name(str(name)))
    raw_unsupported = binding.get("unsupported")
    if isinstance(raw_unsupported, Mapping):
        names.update(_short_input_name(str(name)) for name in raw_unsupported)
    elif isinstance(raw_unsupported, (list, tuple)):
        for item in raw_unsupported:
            if isinstance(item, str):
                names.add(_short_input_name(item))
            elif isinstance(item, Mapping):
                name = item.get("input", item.get("name"))
                if isinstance(name, str):
                    names.add(_short_input_name(name))
    for target, spec in args.items():
        if isinstance(spec, Mapping) and spec.get("unsupported") is True:
            names.add(_short_input_name(str(target)))
    return names


def _totality_errors(binding: Mapping[str, Any], args: Mapping[str, Any]) -> list[str]:
    """ADPT-040: every declared required input is mapped/constant/unsupported."""

    required = _declared_required_inputs(binding)
    if not required:
        return []
    consumed: set[str] = set()
    for spec in args.values():
        if not isinstance(spec, Mapping):
            continue
        source = spec.get("from")
        if isinstance(source, str):
            stripped = _short_input_name(source)
            consumed.add(stripped)
            for separator in (".", "["):
                head = stripped.split(separator, 1)[0]
                if head:
                    consumed.add(head)
    constants = binding.get("constants") if isinstance(binding.get("constants"), Mapping) else {}
    constant_names = {_short_input_name(str(name)) for name in constants}
    unsupported = _unsupported_inputs(binding, args)
    errors: list[str] = []
    for name in required:
        short = _short_input_name(name)
        mapped = short in consumed or any(
            candidate.startswith(short + ".") or candidate.startswith(short + "[")
            for candidate in consumed
        )
        if mapped or short in constant_names or short in unsupported:
            continue
        errors.append(
            f"required input {short!r} is not mapped to a native argument, injected as a "
            "constant, or declared \"unsupported\": true with a reason (ADPT-040)"
        )
    return errors


def validate_binding(
    binding: Mapping[str, Any] | None,
    *,
    capability: Mapping[str, Any] | None = None,
    strict: bool = False,
) -> list[str]:
    """Validate one canonical binding (entry or inner ``binding`` object).

    Returns a list of human-readable errors (empty means valid).  It never
    raises for malformed data, so callers can aggregate failures.  Pass a
    capability class/entry as ``capability`` to check ADPT-025 against
    ``constraints.concurrency`` and ``constraints.max_duration_ms`` and to make
    timeout/concurrency errors class-aware.  ``strict=True`` restricts
    ``errors[].mhs_code`` to the driver subset of ``errors.json``.
    """

    if not isinstance(binding, Mapping):
        return ["binding must be an object"]
    errors: list[str] = []
    is_entry = "binding" in binding
    if is_entry:
        unknown = set(binding) - _ENTRY_KEYS
        if unknown:
            errors.append(f"binding entry has unknown keys {sorted(unknown)}")
        device_id = binding.get("device_id")
        if not isinstance(device_id, str) or not device_id:
            errors.append("binding entry requires 'device_id' (ADPT-020)")
        elif not _DEVICE_ID.match(device_id):
            errors.append(f"binding entry device_id {device_id!r} is not an MHS device id")
        capability_id = binding.get("capability_id")
        if not isinstance(capability_id, str) or not capability_id:
            errors.append("binding entry requires 'capability_id' (ADPT-020)")
        elif not _CAPABILITY_ID.match(capability_id):
            errors.append(
                f"binding entry capability_id {capability_id!r} is not a capability id"
            )
        resource = binding.get("resource")
        if not isinstance(resource, str) or not resource:
            errors.append("binding entry requires 'resource' (ADPT-020)")
        elif not _RESOURCE_ID.match(resource):
            errors.append(f"binding entry resource {resource!r} is not a resource id")
        inner = binding.get("binding")
        if not isinstance(inner, Mapping):
            errors.append("binding entry requires a 'binding' object")
            return errors
    else:
        inner = binding
    errors.extend(_binding_errors(inner, capability=capability, strict=strict))
    return errors


# ---------------------------------------------------------------------------
# normalisation
# ---------------------------------------------------------------------------


def _normalize_rule(spec: Mapping[str, Any]) -> dict[str, Any]:
    rule = dict(spec)
    if "map" in rule and "enum_map" not in rule:
        rule["enum_map"] = rule.pop("map")
    if "units" in rule and "unit" not in rule:
        rule["unit"] = rule.pop("units")
    if "clamp" in rule:
        # Canonical clamps are hard envelope checks (ADPT-024).
        rule["enforce_clamp"] = True
    rule.pop("reason", None)
    rule.pop("unsupported", None)
    return rule


def _normalize_result_transform(source: Any) -> dict[str, Any]:
    if isinstance(source, str):
        return {"from": source}
    rule = dict(source)
    if "path" in rule and "from" not in rule:
        rule["from"] = rule.pop("path")
    if "map" in rule and "enum_map" not in rule:
        rule["enum_map"] = rule.pop("map")
    if "clamp" in rule:
        rule["enforce_clamp"] = True
    rule.pop("reason", None)
    return rule


def normalize_binding(binding: Mapping[str, Any], *, strict: bool = False) -> dict[str, Any]:
    """Validate and translate one canonical binding to the internal shape.

    The returned mapping is accepted by ``PythonObjectBridge`` directly:
    ``args``/``result`` are rule specifications for
    :class:`~mhs.bridge.base.FieldMapping` and ``errors`` is the ordered array
    accepted by :class:`~mhs.bridge.base.ErrorMap`.  Raises
    ``MHS.ADAPTER.MANIFEST_INVALID`` when the binding is not loadable.
    """

    errors = validate_binding(binding, strict=strict)
    if errors:
        raise _manifest_error("invalid capability binding", errors)
    entry = binding if "binding" in binding else {}
    inner: Mapping[str, Any] = entry.get("binding", binding)  # type: ignore[assignment]
    capability_id = str(entry["capability_id"]) if entry else None
    result_spec: dict[str, Any] = {}
    raw_result = inner.get("result")
    if isinstance(raw_result, Mapping) and isinstance(raw_result.get("map"), Mapping):
        for target, source in raw_result["map"].items():
            result_spec[str(target)] = _normalize_result_transform(source)
    result_targets = set(result_spec)
    args_spec: dict[str, Any] = {}
    for target, rule in (inner.get("args") or {}).items():
        if not isinstance(rule, Mapping):
            continue
        if rule.get("unsupported") is True:
            continue
        args_spec[str(target)] = _normalize_rule(rule)
    # constants inject fixed native arguments; a per-arg {"value": ...} wins.
    constants = inner.get("constants")
    if isinstance(constants, Mapping):
        for name, value in constants.items():
            if name in args_spec:
                args_spec[str(name)]["value"] = value
            else:
                args_spec[str(name)] = {"value": value}
    # units / clamp are keyed by target (input path or output field).
    units = inner.get("units")
    if isinstance(units, Mapping):
        for key, unit in units.items():
            target = _target_lookup(str(key), args_spec)
            if target is not None:
                args_spec[target]["unit"] = _unit_spec(unit)
            else:
                target = _target_lookup(str(key), result_spec)
                if target is not None:
                    result_spec[target]["unit"] = _unit_spec(unit)
    clamps = inner.get("clamp")
    if isinstance(clamps, Mapping):
        for key, clamp in clamps.items():
            target = _target_lookup(str(key), args_spec)
            source_spec: dict[str, Any] | None = None
            if target is not None:
                source_spec = args_spec[target]
            else:
                target = _target_lookup(str(key), result_spec)
                if target is not None:
                    source_spec = result_spec[target]
            if source_spec is None:
                continue
            source_spec["clamp"] = dict(clamp)
            source_spec["enforce_clamp"] = True
    unsupported = _unsupported_inputs(inner, inner.get("args") or {})
    normalized: dict[str, Any] = {
        "capability_id": capability_id,
        "device_id": entry.get("device_id") if entry else None,
        "resource": (entry.get("resource") if entry else None) or inner.get("resource", "default"),
        "bridge": str(inner["bridge"]),
        "kind": str(inner.get("kind", "declarative")),
        "native": str(inner["native"]),
        "args": args_spec,
        "result": result_spec,
        "errors": list(inner.get("errors") or []),
        "positional": list(inner.get("positional") or []),
        "concurrency": str(inner.get("concurrency", "exclusive")),
        "timeout_ms": int(inner["timeout_ms"]),
        "required_inputs": _declared_required_inputs(inner),
        "unsupported_inputs": sorted(unsupported),
        "inputs": dict(inner.get("inputs") or {}),
        "enforce_clamp": True,
        "invoke": str(inner.get("invoke", "call")),
    }
    if inner.get("command") is not None:
        normalized["command"] = str(inner["command"])
    if inner.get("parse") is not None:
        normalized["parse"] = copy.deepcopy(dict(inner["parse"]))
    if inner.get("description"):
        normalized["description"] = str(inner["description"])
    return normalized


# ---------------------------------------------------------------------------
# document loading
# ---------------------------------------------------------------------------


def _read_json_document(source: str | os.PathLike[str]) -> Any:
    path = Path(source)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise _manifest_error(
            f"cannot read bindings document {str(path)!r}: {exc}", [str(exc)]
        ) from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise _manifest_error(
            f"bindings document {str(path)!r} is not valid JSON: {exc}", [str(exc)]
        ) from exc


_SCHEMA_STORE = None


def _schema_store():
    """Return the cached MHS schema store or fail closed.

    ADPT-022 makes ``bindings.schema.json`` normative for the canonical
    document.  If the schema set cannot be found, refusing to load is safer
    than silently accepting an unvalidated external document.
    """

    global _SCHEMA_STORE
    if _SCHEMA_STORE is None:
        try:
            from mhs.schema import SchemaStore, find_schema_dir
        except Exception as exc:  # pragma: no cover - depends on installation
            raise _manifest_error(
                "cannot import the MHS schema validator; refusing to load an "
                "unvalidated bindings document",
                [str(exc)],
            ) from exc
        root = find_schema_dir()
        if root is None:  # pragma: no cover - depends on installation
            raise _manifest_error(
                "cannot locate MHS/schema; refusing to load an unvalidated "
                "bindings document (ADPT-022)",
                ["MHS schema directory not found"],
            )
        _SCHEMA_STORE = SchemaStore(root)
    return _SCHEMA_STORE


def _canonical_schema_errors(document: Mapping[str, Any]) -> list[str]:
    store = _schema_store()
    try:
        return list(store.validate(document, "bindings.schema.json"))
    except Exception as exc:  # pragma: no cover - malformed schema installation
        raise _manifest_error(
            f"bindings schema validation could not run: {exc}", [str(exc)]
        ) from exc


def load_bindings(document_or_path: Any, *, strict: bool = False) -> BindingDocument:
    """Load, validate and normalise an ``mhs/bindings.json`` document.

    ``document_or_path`` may be a JSON document (``dict``), a filesystem path
    (``str``/``os.PathLike``), a JSON string, or an already-validated
    :class:`BindingDocument`.  Every *external* form goes through the same
    normative ``bindings.schema.json`` validation and :func:`normalize_binding`;
    the internal normalized shape is not an accepted external format.  The only
    fast path is an authentic :class:`BindingDocument`, a type that cannot be
    constructed by callers.

    Every validation failure is raised as ``MHS.ADAPTER.MANIFEST_INVALID`` with
    the individual errors in ``data.details.errors``.  ``strict=True``
    restricts ``errors[].mhs_code`` to the driver subset of ``errors.json``
    (also applied to an already-loaded document).
    """

    if isinstance(document_or_path, BindingDocument):
        if strict:
            problems = [
                f"bindings[{index}]: {error}"
                for index, entry in enumerate(document_or_path.bindings)
                for rule_index, rule in enumerate(entry.get("errors") or [])
                for error in _error_rule_errors(rule, rule_index, strict=True)
            ]
            if problems:
                raise _manifest_error("bindings document failed strict validation", problems)
        return document_or_path
    raw: Any
    if isinstance(document_or_path, str) and document_or_path.lstrip().startswith("{"):
        try:
            raw = json.loads(document_or_path)
        except json.JSONDecodeError as exc:
            raise _manifest_error(
                f"bindings document string is not valid JSON: {exc}", [str(exc)]
            ) from exc
    elif isinstance(document_or_path, (str, os.PathLike)):
        raw = _read_json_document(document_or_path)
    else:
        raw = document_or_path
    if not isinstance(raw, Mapping):
        raise _manifest_error("bindings document must be a JSON object", ["top level is not an object"])
    errors: list[str] = []
    # ADPT-022: the canonical document is validated by bindings.schema.json.
    # This runs before the hand-written checks so both error sets are reported.
    errors.extend(f"schema: {error}" for error in _canonical_schema_errors(raw))
    unknown = set(raw) - {"$schema", "mhs_bindings", "adapter_id", "title", "bindings"}
    if unknown:
        errors.append(f"document has unknown keys {sorted(unknown)}")
    version = raw.get("mhs_bindings")
    if not isinstance(version, str) or not _MHS_VERSION.match(version):
        errors.append("document requires 'mhs_bindings' matching ^1\\.[0-9]+$")
    adapter_id = raw.get("adapter_id")
    if not isinstance(adapter_id, str) or not _ADAPTER_ID.match(adapter_id):
        errors.append("document requires a valid 'adapter_id'")
    entries = raw.get("bindings")
    if not isinstance(entries, (list, tuple)) or not entries:
        errors.append("document requires a non-empty 'bindings' array")
        entries = []
    seen: set[tuple[str, str]] = set()
    for index, entry in enumerate(entries):
        entry_errors = validate_binding(entry, strict=strict)
        errors.extend(f"bindings[{index}]: {error}" for error in entry_errors)
        if isinstance(entry, Mapping):
            key = (str(entry.get("device_id")), str(entry.get("capability_id")))
            if key in seen:
                errors.append(
                    f"bindings[{index}] duplicates capability {key[1]!r} for device {key[0]!r}"
                )
            seen.add(key)
    if errors:
        raise _manifest_error("bindings document failed validation", errors)
    normalized = [normalize_binding(entry, strict=strict) for entry in entries]
    return BindingDocument(
        mhs_bindings=str(version),
        adapter_id=str(adapter_id),
        bindings=normalized,
        title=raw.get("title"),
        _token=_DOCUMENT_TOKEN,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Not a launcher: print the usage line and return 2."""

    return _bridge_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())

"""A small, dependency-free JSON Schema 2020-12 subset validator.

The MHS reference SDK must validate device manifests, receipts, registry
records and capability inputs without pulling in third-party packages, so
this module implements the subset of JSON Schema 2020-12 that the MHS
schemas actually use:

* ``$ref`` - local (``#/$defs/foo``) and relative-file
  (``defs.schema.json#/$defs/foo``); ``$anchor`` is not supported.
* ``type`` (string or list of strings), ``enum``, ``const``
* ``properties``, ``required``, ``additionalProperties`` (bool or schema),
  ``patternProperties``, ``minProperties``, ``maxProperties``, ``propertyNames``
* ``pattern`` (ECMAScript-style regex as understood by :mod:`re`),
  ``minLength``, ``maxLength``
* ``minimum``, ``maximum``, ``exclusiveMinimum``, ``exclusiveMaximum``,
  ``multipleOf``
* ``items`` (single schema), ``prefixItems``, ``minItems``, ``maxItems``,
  ``uniqueItems``, ``contains``, ``minContains``, ``maxContains``
* ``allOf``, ``anyOf``, ``oneOf``, ``not``, ``if``/``then``/``else``
* ``$defs`` / ``definitions`` (both spellings are accepted)
* ``format`` is deliberately ignored (MHS treats formats as documentation);
  pass ``check_format=True`` only if you really want date-time checks.

Unknown keywords are ignored, which matches JSON Schema semantics. Numeric
handling follows the JSON data model (``bool`` is *not* a number), and
``enum``/``const``/``uniqueItems`` compare JSON values structurally, so
``true`` and ``1`` are distinct.

The public entry point is :func:`validate`, which returns a list of
human-readable error strings (empty means valid).  Schemas that are
themselves malformed (unresolvable ``$ref``, non-object subschema, ...) raise
:class:`SchemaError`; a data instance never raises.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, Mapping, MutableMapping

__all__ = [
    "SchemaError",
    "Validator",
    "validate",
    "validate_file",
    "resolve_pointer",
    "DEFAULT_MAX_DEPTH",
]

DEFAULT_MAX_DEPTH = 128

_TYPE_NAMES = frozenset(
    ["object", "array", "string", "number", "integer", "boolean", "null"]
)

#: Matches a JavaScript-style identifier, used only to format error paths.
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class SchemaError(ValueError):
    """Raised when a *schema* is malformed or contains an unresolvable ``$ref``."""


def _type_of(instance: Any) -> str:
    """Return the JSON Schema type name of a Python value."""
    if instance is None:
        return "null"
    if isinstance(instance, bool):
        return "boolean"
    if isinstance(instance, int):
        return "integer"
    if isinstance(instance, float):
        return "number"
    if isinstance(instance, str):
        return "string"
    if isinstance(instance, (list, tuple)):
        return "array"
    if isinstance(instance, Mapping):
        return "object"
    # Non-JSON values (bytes, sets, custom objects) report their Python type
    # so the error message is still useful; they never satisfy a JSON type.
    return type(instance).__name__


def _matches_type(instance: Any, type_name: str) -> bool:
    """Return True when ``instance`` satisfies JSON type ``type_name``."""
    actual = _type_of(instance)
    if type_name == actual:
        return True
    # JSON Schema: an integer is also a number; a float with zero fraction is
    # also an integer.
    if type_name == "number" and actual == "integer":
        return True
    if type_name == "integer" and actual == "number":
        return isinstance(instance, float) and instance.is_integer()
    return False


def _json_equal(left: Any, right: Any) -> bool:
    """Structural JSON equality (``True != 1``, ``1 == 1.0``)."""
    lt, rt = _type_of(left), _type_of(right)
    if lt in ("boolean", "null") or rt in ("boolean", "null"):
        return lt == rt and left == right
    if lt in ("integer", "number") or rt in ("integer", "number"):
        if lt not in ("integer", "number") or rt not in ("integer", "number"):
            return False
        return left == right
    if lt != rt:
        return False
    if lt == "array":
        return len(left) == len(right) and all(
            _json_equal(a, b) for a, b in zip(left, right)
        )
    if lt == "object":
        if set(left.keys()) != set(right.keys()):
            return False
        return all(_json_equal(left[k], right[k]) for k in left)
    return left == right


def _canonical_value(value: Any) -> str:
    """Return a stable string for structural comparison in ``uniqueItems``."""
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError):  # pragma: no cover - non-JSON instance
        return repr(value)


def _join(path: str, key: Any) -> str:
    """Append a property name or array index to an error path string."""
    if isinstance(key, int):
        return f"{path}[{key}]"
    key = str(key)
    if _IDENT_RE.match(key):
        return f"{path}.{key}"
    return f"{path}[{json.dumps(key, ensure_ascii=False)}]"


def resolve_pointer(document: Any, pointer: str) -> Any:
    """Resolve an RFC 6901 JSON Pointer inside ``document``.

    ``pointer`` may be given with or without the leading ``#`` and must be
    empty for the document itself.  Raises :class:`SchemaError` when the
    pointer does not resolve.
    """
    if pointer.startswith("#"):
        pointer = pointer[1:]
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise SchemaError(f"unsupported JSON pointer/anchor: {pointer!r}")
    node = document
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, Mapping):
            if token not in node:
                raise SchemaError(f"JSON pointer {pointer!r} does not resolve")
            node = node[token]
        elif isinstance(node, (list, tuple)):
            try:
                index = int(token)
            except ValueError as exc:
                raise SchemaError(
                    f"JSON pointer {pointer!r} has a non-integer index"
                ) from exc
            if index < 0 or index >= len(node):
                raise SchemaError(f"JSON pointer {pointer!r} index out of range")
            node = node[index]
        else:
            raise SchemaError(f"JSON pointer {pointer!r} does not resolve")
    return node


def _split_ref(ref: str) -> tuple[str, str]:
    """Split a ``$ref`` into ``(document_part, fragment_pointer)``."""
    uri, _, fragment = ref.partition("#")
    if fragment and not fragment.startswith("/"):
        raise SchemaError(
            f"unsupported $ref fragment {ref!r}: only JSON pointers are supported"
        )
    return uri, fragment


class Validator:
    """Validate JSON-like Python values against JSON Schema 2020-12 schemas.

    Parameters
    ----------
    resolver:
        Optional resolver for external ``$ref`` targets.  Accepted forms:

        * :class:`mhs.schema.SchemaStore` (or any object with a ``resolve``
          method taking ``(uri, base)`` and returning a schema dict or a
          ``(schema, base)`` tuple),
        * a callable with the same signature,
        * a filesystem path / URL string used to build a :class:`SchemaStore`.

        When omitted, the default MHS schema store is used lazily.
    max_depth:
        Recursion guard for cyclic ``$ref`` chains.
    check_format:
        When true, ``date-time`` and ``date`` formats are checked.  MHS
        ignores ``format`` by default.
    """

    def __init__(
        self,
        resolver: Any = None,
        *,
        max_depth: int = DEFAULT_MAX_DEPTH,
        check_format: bool = False,
    ) -> None:
        """Create a validator; see the class docstring for argument details."""
        self.max_depth = int(max_depth)
        self.check_format = bool(check_format)
        self._resolver = resolver
        self._store = None

    # -- resolver plumbing -------------------------------------------------

    def _get_store(self):
        """Return a :class:`SchemaStore` for the configured resolver."""
        if self._store is None:
            from .store import SchemaStore, default_store

            resolver = self._resolver
            if resolver is None or isinstance(resolver, (str, bytes)) or hasattr(
                resolver, "__fspath__"
            ):
                self._store = (
                    default_store()
                    if resolver is None
                    else SchemaStore(root=resolver)
                )
            elif hasattr(resolver, "resolve"):
                self._store = resolver
            else:
                raise SchemaError(
                    "resolver must be a SchemaStore, a callable, or a path"
                )
        return self._store

    def _resolve_external(self, uri: str, base: str | None) -> tuple[Any, str | None]:
        """Resolve an external ``$ref`` document part to a schema and base."""
        store = self._get_store()
        try:
            result = store.resolve(uri, base=base)
        except TypeError:
            result = store.resolve(uri)
        except AttributeError as exc:  # pragma: no cover - defensive
            raise SchemaError(f"resolver cannot resolve {uri!r}: {exc}") from exc
        if isinstance(result, tuple) and len(result) == 2:
            return result[0], result[1]
        return result, uri

    # -- public API --------------------------------------------------------

    def validate(
        self,
        instance: Any,
        schema: Any,
        base_uri: str | None = None,
    ) -> list[str]:
        """Validate ``instance`` against ``schema`` and return error strings.

        ``schema`` may be a schema dict, a filesystem path, or a schema name
        understood by the configured :class:`SchemaStore`.  An empty list
        means the instance is valid.
        """
        schema, root, base = self._coerce_schema(schema, base_uri)
        errors: list[str] = []
        self._validate(instance, schema, root, base, "$", errors, 0, set())
        return errors

    def is_valid(self, instance: Any, schema: Any, base_uri: str | None = None) -> bool:
        """Return True when ``instance`` validates against ``schema``."""
        return not self.validate(instance, schema, base_uri)

    # -- internals ---------------------------------------------------------

    def _coerce_schema(
        self, schema: Any, base_uri: str | None
    ) -> tuple[Mapping[str, Any], Mapping[str, Any], str | None]:
        """Return ``(schema, root_document, base_uri)`` for validation."""
        if isinstance(schema, Mapping):
            return schema, schema, base_uri or schema.get("$id")
        if isinstance(schema, (str, bytes)) or hasattr(schema, "__fspath__"):
            store = self._get_store()
            key = schema if isinstance(schema, str) else str(schema)
            # A local caller may name a schema file directly; that goes through
            # the store's developer-only ``load_path``.  Names and ``$id``s go
            # through ``load``, which never leaves the store roots.
            loader = getattr(store, "_load_for_validation", None) or store.load
            loaded = loader(key)
            if isinstance(loaded, tuple):
                doc, base = loaded
            else:  # pragma: no cover - defensive
                doc, base = loaded, key
            if not isinstance(doc, Mapping):
                raise SchemaError(f"schema {key!r} is not a JSON object")
            return doc, doc, base
        raise SchemaError(
            "schema must be a dict, a path, or a schema name, "
            f"got {type(schema).__name__}"
        )

    def _validate(
        self,
        instance: Any,
        schema: Any,
        root: Mapping[str, Any],
        base: str | None,
        path: str,
        errors: list[str],
        depth: int,
        seen: set[tuple[int, int]],
    ) -> None:
        """Recursively validate ``instance``; append human-readable errors."""
        if not isinstance(schema, Mapping):
            raise SchemaError(f"{path}: subschema is not an object: {schema!r}")
        if depth > self.max_depth:
            errors.append(f"{path}: maximum $ref depth exceeded")
            return

        # Guard against a $ref cycle that does not consume the instance.
        marker = (id(schema), id(instance))
        if marker in seen:
            return
        if "$ref" in schema:
            seen = seen | {marker}
            ref = schema["$ref"]
            if not isinstance(ref, str):
                raise SchemaError(f"{path}: $ref must be a string")
            uri, fragment = _split_ref(ref)
            if uri == "":
                target_root, target_base = root, base
            else:
                target_root, target_base = self._resolve_external(uri, base)
                if not isinstance(target_root, Mapping):
                    raise SchemaError(f"{path}: $ref {ref!r} is not an object")
            target = resolve_pointer(target_root, fragment) if fragment else target_root
            self._validate(
                instance,
                target,
                target_root,
                target_base,
                path,
                errors,
                depth + 1,
                seen,
            )
            siblings = {k: v for k, v in schema.items() if k != "$ref"}
            if siblings:
                self._validate(
                    instance, siblings, root, base, path, errors, depth + 1, seen
                )
            return

        self._validate_type(instance, schema, path, errors)
        self._validate_enum(instance, schema, path, errors)
        self._validate_numbers(instance, schema, path, errors)
        self._validate_strings(instance, schema, path, errors)
        self._validate_arrays(instance, schema, root, base, path, errors, depth, seen)
        self._validate_objects(instance, schema, root, base, path, errors, depth, seen)
        self._validate_combinators(
            instance, schema, root, base, path, errors, depth, seen
        )

    # Each helper only fires for the relevant instance type, per the spec.

    def _validate_type(
        self, instance: Any, schema: Mapping[str, Any], path: str, errors: list[str]
    ) -> None:
        """Check the ``type`` keyword."""
        if "type" not in schema:
            return
        declared = schema["type"]
        names: Iterable[str]
        if isinstance(declared, str):
            names = [declared]
        elif isinstance(declared, (list, tuple)):
            names = [str(n) for n in declared]
        else:
            raise SchemaError(f"{path}: schema 'type' must be a string or list")
        for name in names:
            if name not in _TYPE_NAMES:
                raise SchemaError(f"{path}: unknown JSON type {name!r}")
        if not any(_matches_type(instance, name) for name in names):
            expected = " or ".join(names)
            errors.append(
                f"{path}: expected {expected}, got {_type_of(instance)}"
            )

    def _validate_enum(
        self, instance: Any, schema: Mapping[str, Any], path: str, errors: list[str]
    ) -> None:
        """Check the ``enum`` and ``const`` keywords."""
        if "const" in schema and not _json_equal(instance, schema["const"]):
            errors.append(
                f"{path}: expected constant {schema['const']!r}, got {instance!r}"
            )
        if "enum" in schema:
            choices = schema["enum"]
            if not isinstance(choices, (list, tuple)):
                raise SchemaError(f"{path}: schema 'enum' must be an array")
            if not any(_json_equal(instance, choice) for choice in choices):
                errors.append(
                    f"{path}: {instance!r} is not one of "
                    f"{list(choices)!r}"
                )

    def _validate_numbers(
        self, instance: Any, schema: Mapping[str, Any], path: str, errors: list[str]
    ) -> None:
        """Check numeric bounds for numeric instances."""
        if _type_of(instance) not in ("integer", "number"):
            return
        value = instance
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        exclusive_min = schema.get("exclusiveMinimum")
        exclusive_max = schema.get("exclusiveMaximum")
        # Draft-04 compatibility: boolean exclusiveMinimum/Maximum modify the
        # adjacent minimum/maximum keyword.
        if isinstance(exclusive_min, bool):
            if exclusive_min and minimum is not None:
                if not value > minimum:
                    errors.append(
                        f"{path}: {value!r} must be > {minimum!r} (exclusive)"
                    )
                minimum = None
            exclusive_min = None if exclusive_min else exclusive_min
        if isinstance(exclusive_max, bool):
            if exclusive_max and maximum is not None:
                if not value < maximum:
                    errors.append(
                        f"{path}: {value!r} must be < {maximum!r} (exclusive)"
                    )
                maximum = None
            exclusive_max = None if exclusive_max else exclusive_max
        if isinstance(minimum, (int, float)) and not isinstance(minimum, bool):
            if value < minimum:
                errors.append(f"{path}: {value!r} is less than minimum {minimum!r}")
        if isinstance(maximum, (int, float)) and not isinstance(maximum, bool):
            if value > maximum:
                errors.append(f"{path}: {value!r} is greater than maximum {maximum!r}")
        if isinstance(exclusive_min, (int, float)) and not isinstance(
            exclusive_min, bool
        ):
            if not value > exclusive_min:
                errors.append(
                    f"{path}: {value!r} must be > {exclusive_min!r} (exclusive minimum)"
                )
        if isinstance(exclusive_max, (int, float)) and not isinstance(
            exclusive_max, bool
        ):
            if not value < exclusive_max:
                errors.append(
                    f"{path}: {value!r} must be < {exclusive_max!r} (exclusive maximum)"
                )
        multiple = schema.get("multipleOf")
        if isinstance(multiple, (int, float)) and not isinstance(multiple, bool):
            if multiple <= 0:
                raise SchemaError(f"{path}: schema 'multipleOf' must be > 0")
            quotient = value / multiple
            if abs(quotient - round(quotient)) > 1e-9:
                errors.append(
                    f"{path}: {value!r} is not a multiple of {multiple!r}"
                )

    def _validate_strings(
        self, instance: Any, schema: Mapping[str, Any], path: str, errors: list[str]
    ) -> None:
        """Check string length, pattern and (optionally) format keywords."""
        if not isinstance(instance, str):
            return
        min_length = schema.get("minLength")
        max_length = schema.get("maxLength")
        if isinstance(min_length, int) and len(instance) < min_length:
            errors.append(
                f"{path}: string is shorter than minLength {min_length} "
                f"(got {len(instance)})"
            )
        if isinstance(max_length, int) and len(instance) > max_length:
            errors.append(
                f"{path}: string is longer than maxLength {max_length} "
                f"(got {len(instance)})"
            )
        pattern = schema.get("pattern")
        if pattern is not None:
            try:
                regex = re.compile(pattern)
            except re.error as exc:
                raise SchemaError(f"{path}: invalid schema pattern {pattern!r}") from exc
            if regex.search(instance) is None:
                errors.append(
                    f"{path}: string {instance!r} does not match pattern {pattern!r}"
                )
        if self.check_format:
            fmt = schema.get("format")
            if fmt in ("date-time", "date") and not _check_datetime(instance, fmt):
                errors.append(f"{path}: string {instance!r} is not a valid {fmt}")

    def _validate_arrays(
        self,
        instance: Any,
        schema: Mapping[str, Any],
        root: Mapping[str, Any],
        base: str | None,
        path: str,
        errors: list[str],
        depth: int,
        seen: set[tuple[int, int]],
    ) -> None:
        """Check array keywords for array instances."""
        if not isinstance(instance, (list, tuple)):
            return
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(
                f"{path}: array has fewer than minItems {schema['minItems']} "
                f"(got {len(instance)})"
            )
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(
                f"{path}: array has more than maxItems {schema['maxItems']} "
                f"(got {len(instance)})"
            )
        if schema.get("uniqueItems") is True:
            duplicate: tuple[int, int] | None = None
            for index in range(len(instance)):
                for earlier in range(index):
                    if _json_equal(instance[index], instance[earlier]):
                        duplicate = (index, earlier)
                        break
                if duplicate is not None:
                    break
            if duplicate is not None:
                errors.append(
                    f"{path}: array items are not unique "
                    f"(index {duplicate[0]} duplicates index {duplicate[1]})"
                )
        prefix = schema.get("prefixItems")
        tail_start = 0
        if prefix is not None:
            if not isinstance(prefix, (list, tuple)):
                raise SchemaError(f"{path}: schema 'prefixItems' must be an array")
            tail_start = len(prefix)
            for index, subschema in enumerate(prefix):
                if index >= len(instance):
                    break
                self._validate(
                    instance[index],
                    subschema,
                    root,
                    base,
                    _join(path, index),
                    errors,
                    depth + 1,
                    seen,
                )
        items = schema.get("items")
        if items is not None:
            if isinstance(items, (list, tuple)):  # draft-07 tuple form
                for offset, subschema in enumerate(items):
                    index = tail_start + offset
                    if index >= len(instance):
                        break
                    self._validate(
                        instance[index],
                        subschema,
                        root,
                        base,
                        _join(path, index),
                        errors,
                        depth + 1,
                        seen,
                    )
                if "additionalItems" in schema:
                    extra = schema["additionalItems"]
                    for index in range(tail_start + len(items), len(instance)):
                        if extra is False:
                            errors.append(
                                f"{path}[{index}]: additional array items are not allowed"
                            )
                        elif isinstance(extra, Mapping):
                            self._validate(
                                instance[index],
                                extra,
                                root,
                                base,
                                _join(path, index),
                                errors,
                                depth + 1,
                                seen,
                            )
                        elif extra is not True:
                            raise SchemaError(
                                f"{path}: schema 'additionalItems' must be bool or object"
                            )
            elif isinstance(items, Mapping):
                # 2020-12: ``items`` applies only to elements *after*
                # ``prefixItems`` (prefix elements are fully handled above).
                for index in range(tail_start, len(instance)):
                    self._validate(
                        instance[index],
                        items,
                        root,
                        base,
                        _join(path, index),
                        errors,
                        depth + 1,
                        seen,
                    )
            elif items is True:
                pass
            elif items is False:
                for index in range(tail_start, len(instance)):
                    errors.append(
                        f"{path}[{index}]: additional array items are not allowed"
                    )
            else:
                raise SchemaError(f"{path}: schema 'items' must be an object or bool")
        contains = schema.get("contains")
        if contains is not None:
            matches = 0
            for item in instance:
                sub_errors: list[str] = []
                self._validate(
                    item,
                    contains,
                    root,
                    base,
                    path,
                    sub_errors,
                    depth + 1,
                    seen,
                )
                if not sub_errors:
                    matches += 1
            min_contains = schema.get("minContains", 1)
            max_contains = schema.get("maxContains")
            if matches < min_contains:
                errors.append(
                    f"{path}: array contains {matches} matching item(s), "
                    f"needs at least {min_contains}"
                )
            if max_contains is not None and matches > max_contains:
                errors.append(
                    f"{path}: array contains {matches} matching item(s), "
                    f"allowed at most {max_contains}"
                )

    def _validate_objects(
        self,
        instance: Any,
        schema: Mapping[str, Any],
        root: Mapping[str, Any],
        base: str | None,
        path: str,
        errors: list[str],
        depth: int,
        seen: set[tuple[int, int]],
    ) -> None:
        """Check object keywords for mapping instances."""
        if not isinstance(instance, Mapping):
            return
        required = schema.get("required")
        if required is not None:
            if not isinstance(required, (list, tuple)):
                raise SchemaError(f"{path}: schema 'required' must be an array")
            for key in required:
                if key not in instance:
                    errors.append(f"{path}: missing required property {key!r}")
        min_props = schema.get("minProperties")
        max_props = schema.get("maxProperties")
        if isinstance(min_props, int) and len(instance) < min_props:
            errors.append(
                f"{path}: object has fewer than minProperties {min_props}"
            )
        if isinstance(max_props, int) and len(instance) > max_props:
            errors.append(
                f"{path}: object has more than maxProperties {max_props}"
            )
        properties = schema.get("properties")
        if properties is not None and not isinstance(properties, Mapping):
            raise SchemaError(f"{path}: schema 'properties' must be an object")
        properties = properties or {}
        patterns = schema.get("patternProperties")
        if patterns is not None and not isinstance(patterns, Mapping):
            raise SchemaError(f"{path}: schema 'patternProperties' must be an object")
        patterns = patterns or {}
        compiled_patterns = []
        for pattern, subschema in patterns.items():
            try:
                compiled_patterns.append((re.compile(pattern), pattern, subschema))
            except re.error as exc:
                raise SchemaError(
                    f"{path}: invalid patternProperties regex {pattern!r}"
                ) from exc
        for key, value in instance.items():
            child = _join(path, key)
            matched = False
            if key in properties:
                matched = True
                self._validate(
                    value,
                    properties[key],
                    root,
                    base,
                    child,
                    errors,
                    depth + 1,
                    seen,
                )
            for regex, _pattern, subschema in compiled_patterns:
                if regex.search(str(key)):
                    matched = True
                    self._validate(
                        value,
                        subschema,
                        root,
                        base,
                        child,
                        errors,
                        depth + 1,
                        seen,
                    )
            if not matched:
                additional = schema.get("additionalProperties", True)
                if additional is False:
                    allowed = ", ".join(sorted(map(_canonical_value, properties))) or "none"
                    errors.append(
                        f"{child}: additional property {key!r} is not allowed "
                        f"(allowed: {allowed})"
                    )
                elif isinstance(additional, Mapping):
                    self._validate(
                        value,
                        additional,
                        root,
                        base,
                        child,
                        errors,
                        depth + 1,
                        seen,
                    )
                elif additional is not True:
                    raise SchemaError(
                        f"{path}: schema 'additionalProperties' must be bool or object"
                    )
        property_names = schema.get("propertyNames")
        if property_names is not None:
            for key in instance:
                self._validate(
                    key,
                    property_names,
                    root,
                    base,
                    _join(path, key) + " (property name)",
                    errors,
                    depth + 1,
                    seen,
                )

    def _validate_combinators(
        self,
        instance: Any,
        schema: Mapping[str, Any],
        root: Mapping[str, Any],
        base: str | None,
        path: str,
        errors: list[str],
        depth: int,
        seen: set[tuple[int, int]],
    ) -> None:
        """Check ``allOf``/``anyOf``/``oneOf``/``not``/``if``-``then``-``else``."""
        all_of = schema.get("allOf")
        if all_of is not None:
            if not isinstance(all_of, (list, tuple)):
                raise SchemaError(f"{path}: schema 'allOf' must be an array")
            for subschema in all_of:
                self._validate(
                    instance, subschema, root, base, path, errors, depth + 1, seen
                )
        any_of = schema.get("anyOf")
        if any_of is not None:
            if not isinstance(any_of, (list, tuple)):
                raise SchemaError(f"{path}: schema 'anyOf' must be an array")
            branch_errors: list[list[str]] = []
            for subschema in any_of:
                sub: list[str] = []
                self._validate(
                    instance, subschema, root, base, path, sub, depth + 1, seen
                )
                branch_errors.append(sub)
            if all(branch_errors):
                errors.append(
                    f"{path}: value matches none of the {len(any_of)} anyOf schemas"
                )
        one_of = schema.get("oneOf")
        if one_of is not None:
            if not isinstance(one_of, (list, tuple)):
                raise SchemaError(f"{path}: schema 'oneOf' must be an array")
            matches = 0
            for subschema in one_of:
                sub = []
                self._validate(
                    instance, subschema, root, base, path, sub, depth + 1, seen
                )
                if not sub:
                    matches += 1
            if matches != 1:
                errors.append(
                    f"{path}: value must match exactly one of the "
                    f"{len(one_of)} oneOf schemas (matched {matches})"
                )
        if "not" in schema:
            sub = []
            self._validate(
                instance, schema["not"], root, base, path, sub, depth + 1, seen
            )
            if not sub:
                errors.append(f"{path}: value must not match the 'not' schema")
        if "if" in schema:
            condition: list[str] = []
            self._validate(
                instance, schema["if"], root, base, path, condition, depth + 1, seen
            )
            if not condition and "then" in schema:
                self._validate(
                    instance, schema["then"], root, base, path, errors, depth + 1, seen
                )
            elif condition and "else" in schema:
                self._validate(
                    instance,
                    schema["else"],
                    root,
                    base,
                    path,
                    errors,
                    depth + 1,
                    seen,
                )


def _check_datetime(value: str, fmt: str) -> bool:
    """Return True when ``value`` looks like an RFC 3339 date(-time)."""
    from datetime import datetime

    try:
        if fmt == "date":
            datetime.strptime(value, "%Y-%m-%d")
        else:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def validate(
    instance: Any,
    schema: Any,
    resolver: Any = None,
) -> list[str]:
    """Validate ``instance`` and return a list of human-readable errors.

    ``schema`` may be a schema dict, a filesystem path, or a schema name known
    to ``resolver`` (a :class:`mhs.schema.SchemaStore`, a path, or a callable
    ``resolver(uri, base)``).  An empty list means the instance is valid.
    """
    return Validator(resolver=resolver).validate(instance, schema)


def validate_file(
    instance: Any,
    schema_path: Any,
    resolver: Any = None,
) -> list[str]:
    """Validate ``instance`` against the JSON Schema stored in ``schema_path``."""
    import pathlib

    path = pathlib.Path(schema_path)
    if not path.is_file():
        raise SchemaError(f"schema file not found: {path}")
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SchemaError(f"schema file {path} is not valid JSON: {exc}") from exc
    validator = Validator(
        resolver=resolver if resolver is not None else path.parent
    )
    return validator.validate(instance, schema, base_uri=str(path))

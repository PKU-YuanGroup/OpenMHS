"""Reference implementation of the load-time data rules a JSON Schema cannot express.

These rules need a second document (the capability catalogue or the device
manifest an overlay applies to), so the schemas leave them to the loader.
This small, test-only checker gives the semantic invalid examples under
``MHS/schema/examples/invalid/`` their expected failure and keeps the valid
examples honest.  It is deliberately independent of the runtime limit engine;
the runtime must reach the same verdict on the same examples.

Every function returns a list of ``(json_pointer, rule, message)`` tuples.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from ._support import pointer

CONFIGURE = "cap.device.configure.v1"
_SEGMENT = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)|\[(\*|[0-9]+)\]|\.")
WILDCARD = object()


def path_tokens(path: str) -> list[Any]:
    """Tokenise a limit path (``a.b[0].c``, ``joints[*]``) like the bridge resolver."""
    tokens: list[Any] = []
    position = 0
    while position < len(path):
        match = _SEGMENT.match(path, position)
        if match is None:
            raise ValueError(f"bad limit path {path!r}")
        if match.group(1):
            tokens.append(match.group(1))
        elif match.group(2) == "*":
            tokens.append(WILDCARD)
        elif match.group(2):
            tokens.append(int(match.group(2)))
        position = match.end()
    return tokens


def fixed_length(field: Mapping[str, Any]) -> int | None:
    """The fixed length of an array field schema, or None when it may vary."""
    prefix = field.get("prefixItems")
    if isinstance(prefix, list) and field.get("items") is False:
        return len(prefix)
    if isinstance(field.get("minItems"), int) and field.get("minItems") == field.get("maxItems"):
        return int(field["minItems"])
    return None


def resolve(schema: Any, path: str) -> Mapping[str, Any] | None:
    """Return the field schema a limit path addresses, or None if it does not resolve."""
    node = schema
    for token in path_tokens(path):
        if not isinstance(node, Mapping):
            return None
        if isinstance(token, str):
            properties = node.get("properties")
            if not isinstance(properties, Mapping) or token not in properties:
                return None
            node = properties[token]
            continue
        if node.get("type") != "array" and "items" not in node:
            return None
        length = fixed_length(node)
        if isinstance(token, int) and length is not None and token >= length:
            return None
        prefix = node.get("prefixItems")
        if isinstance(token, int) and isinstance(prefix, list) and token < len(prefix):
            node = prefix[token]
        else:
            node = node.get("items")
    return node if isinstance(node, Mapping) else None


def field_unit(field: Mapping[str, Any]) -> str | None:
    """The x-mhs-unit of a field, or of its items for a numeric array."""
    unit = field.get("x-mhs-unit")
    if unit is None and isinstance(field.get("items"), Mapping):
        unit = field["items"].get("x-mhs-unit")
    return unit if isinstance(unit, str) else None


def _is_skeleton(schema: Any) -> bool:
    return not isinstance(schema, Mapping) or not schema.get("properties")


def effective_input(binding: Mapping[str, Any], manifest: Mapping[str, Any],
                    classes: Mapping[str, Mapping[str, Any]]) -> Mapping[str, Any]:
    """Binding input schema; a missing or skeleton one inherits the class schema.

    For ``cap.device.configure.v1`` the schema is derived from the writable
    (non-readOnly) properties of the bound resource's state schema.
    """
    capability_id = binding.get("capability_id")
    if capability_id == CONFIGURE:
        for resource in manifest.get("resources") or []:
            if resource.get("resource_id") == binding.get("resource"):
                state = resource.get("state_schema") or {}
                writable = {name: field for name, field in (state.get("properties") or {}).items()
                            if isinstance(field, Mapping) and not field.get("readOnly")}
                return {"type": "object", "properties": writable, "additionalProperties": False}
        return {"type": "object", "properties": {}}
    own = binding.get("input_schema")
    if not _is_skeleton(own):
        return own
    cls = classes.get(str(capability_id))
    if cls is not None:
        return cls.get("input_schema") or {}
    return own or {}


def check_rule(base: str, rule: Any, field: Mapping[str, Any]) -> list[tuple[str, str, str]]:
    """Array-bound length and unit rules for one resolved limit rule."""
    problems: list[tuple[str, str, str]] = []
    if not isinstance(rule, Mapping):
        return problems
    is_array = field.get("type") == "array"
    length = fixed_length(field) if is_array else None
    for key in ("min", "max", "names"):
        value = rule.get(key)
        if not isinstance(value, list):
            continue
        if not is_array:
            problems.append((f"{base}/{key}", "array-bound-length", f"per-element {key} on a non-array field"))
        elif length is None:
            problems.append((f"{base}/{key}", "array-bound-length", f"per-element {key} needs a fixed-length array"))
        elif len(value) != length:
            problems.append((f"{base}/{key}", "array-bound-length",
                             f"{key} has {len(value)} values for an array of length {length}"))
    unit = rule.get("unit")
    declared = field_unit(field)
    if isinstance(unit, str) and declared is not None and unit != declared:
        problems.append((f"{base}/unit", "limit-unit-matches-field",
                         f"limit unit {unit!r} differs from the field's x-mhs-unit {declared!r}"))
    return problems


def pattern_matches(pattern: str, capability_id: str) -> bool:
    """capabilityPattern matching: exact id or a trailing ``.*`` glob."""
    if pattern.endswith(".*"):
        return capability_id.startswith(pattern[:-1])
    return pattern == capability_id


def check_manifest(manifest: Mapping[str, Any], classes: Mapping[str, Mapping[str, Any]]) -> list[tuple[str, str, str]]:
    """Verb, limit-path, array-bound and unit rules for one device manifest."""
    problems: list[tuple[str, str, str]] = []
    bindings = list(manifest.get("capabilities") or [])
    for index, binding in enumerate(bindings):
        cls = classes.get(str(binding.get("capability_id")))
        if "verb" in binding and cls is not None and binding["verb"] != cls.get("verb"):
            problems.append((pointer("capabilities", index, "verb"), "verb-matches-class",
                             f"binding verb {binding['verb']!r} differs from class verb {cls.get('verb')!r}"))
        schema = effective_input(binding, manifest, classes)
        for path, rule in (binding.get("limits") or {}).items():
            base = pointer("capabilities", index, "limits", path)
            field = resolve(schema, path)
            if field is None:
                problems.append((base, "limit-path-resolves", f"limit path {path!r} does not resolve"))
                continue
            problems.extend(check_rule(base, rule, field))
    for pattern, limits in ((manifest.get("safety") or {}).get("envelope") or {}).items():
        matching = [b for b in bindings if pattern_matches(pattern, str(b.get("capability_id")))]
        for path, rule in (limits or {}).items():
            base = pointer("safety", "envelope", pattern, path)
            fields = [f for f in (resolve(effective_input(b, manifest, classes), path) for b in matching) if f is not None]
            if not fields:
                problems.append((base, "limit-path-resolves", f"envelope path {path!r} resolves in no bound capability"))
                continue
            problems.extend(check_rule(base, rule, fields[0]))
    return problems


def _broadcast(values: Iterable[Any]) -> list[Any]:
    return [value for value in values if isinstance(value, (int, float, list)) and not isinstance(value, bool)]


def _tighter(current: Any, value: Any, pick) -> Any:
    if current is None:
        return value
    if isinstance(current, list) or isinstance(value, list):
        size = len(current) if isinstance(current, list) else len(value)
        left = current if isinstance(current, list) else [current] * size
        right = value if isinstance(value, list) else [value] * size
        return [pick(a, b) for a, b in zip(left, right)]
    return pick(current, value)


def effective_rule(capability_id: str, path: str, binding: Mapping[str, Any], manifest: Mapping[str, Any],
                   classes: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Intersection of the class, binding and envelope rules for one path."""
    rules = []
    cls = classes.get(capability_id)
    if cls is not None:
        rules.append((cls.get("limits") or {}).get(path))
    rules.append((binding.get("limits") or {}).get(path))
    for pattern, limits in ((manifest.get("safety") or {}).get("envelope") or {}).items():
        if pattern_matches(pattern, capability_id):
            rules.append((limits or {}).get(path))
    result: dict[str, Any] = {}
    allowed: set | None = None
    for rule in rules:
        if not isinstance(rule, Mapping):
            continue
        for value in _broadcast([rule.get("max")]):
            result["max"] = _tighter(result.get("max"), value, min)
        for value in _broadcast([rule.get("min")]):
            result["min"] = _tighter(result.get("min"), value, max)
        if isinstance(rule.get("allowed"), list):
            values = set(map(repr, rule["allowed"]))
            allowed = values if allowed is None else allowed & values
    if allowed is not None:
        result["allowed"] = allowed
    return result


def _widens(overlay: Any, existing: Any, wider) -> bool:
    if overlay is None or existing is None:
        return False
    if isinstance(overlay, list) or isinstance(existing, list):
        size = len(overlay) if isinstance(overlay, list) else len(existing)
        left = overlay if isinstance(overlay, list) else [overlay] * size
        right = existing if isinstance(existing, list) else [existing] * size
        if len(left) != len(right):
            return True
        return any(wider(a, b) for a, b in zip(left, right))
    return wider(overlay, existing)


def check_overlay(overlay: Mapping[str, Any], manifests: Mapping[str, Mapping[str, Any]],
                  classes: Mapping[str, Mapping[str, Any]]) -> list[tuple[str, str, str]]:
    """Narrow-only rule of a site-limits overlay against the device manifests it names."""
    problems: list[tuple[str, str, str]] = []
    for device_id, entries in (overlay.get("devices") or {}).items():
        manifest = manifests.get(device_id)
        if manifest is None:
            problems.append((pointer("devices", device_id), "overlay-device-known", "no manifest for this device"))
            continue
        for key, value in (entries or {}).items():
            if key.startswith(("cap.", "x-cap.")):
                capability_id, rules, prefix = key, value, ("devices", device_id, key)
            else:
                capability_id, rules, prefix = CONFIGURE, {key: value}, ("devices", device_id)
            binding = next((b for b in manifest.get("capabilities") or [] if b.get("capability_id") == capability_id), None)
            if binding is None:
                problems.append((pointer("devices", device_id, key), "overlay-binding-known",
                                 f"{capability_id} is not bound on {device_id}"))
                continue
            schema = effective_input(binding, manifest, classes)
            for path, rule in (rules or {}).items():
                base = pointer(*prefix, path)
                field = resolve(schema, path)
                if field is None:
                    problems.append((base, "limit-path-resolves", f"overlay path {path!r} does not resolve"))
                    continue
                if not isinstance(rule, Mapping):
                    continue
                problems.extend(check_rule(base, rule, field))
                existing = effective_rule(capability_id, path, binding, manifest, classes)
                if _widens(rule.get("max"), existing.get("max"), lambda a, b: a > b):
                    problems.append((f"{base}/max", "overlay-narrows", f"max {rule['max']} widens {existing['max']}"))
                if _widens(rule.get("min"), existing.get("min"), lambda a, b: a < b):
                    problems.append((f"{base}/min", "overlay-narrows", f"min {rule['min']} widens {existing['min']}"))
                if isinstance(rule.get("allowed"), list) and "allowed" in existing:
                    if set(map(repr, rule["allowed"])) - existing["allowed"]:
                        problems.append((f"{base}/allowed", "overlay-narrows", "allowed adds values"))
    return problems

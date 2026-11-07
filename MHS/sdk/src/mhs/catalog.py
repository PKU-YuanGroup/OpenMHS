"""The capability catalogue at runtime: loading, lookup and binding resolution.

``MHS/spec/capabilities.json`` is the normative class catalogue.  This module
makes it binding (SC-01, SPEC-05): :func:`resolve_binding` turns one manifest
binding into the contract the runtime enforces.

* An unknown ``cap.*`` id is an error; ``x-cap.*`` and ``cap.x.*`` ids are
  extensions whose inline schemas are their own contract.
* The verb, risk floor, permit requirement and class limits come from the
  class.  A missing or skeleton binding schema inherits the class schema.
* Otherwise the effective schema is binding ∩ class as one merged schema
  (:func:`merge_schema`): every class keyword the binding omits is filled in,
  recursively (``type``, ``x-mhs-unit``, ``enum``/``const``, numeric, length
  and item bounds, ``required``, a closed ``additionalProperties`` and the
  ``items`` schema), the class properties an open binding does not list (and
  the class-required ones a closed binding leaves out) keep their class
  schema, and a ``pattern``/``format``/``multipleOf`` that both state
  differently is kept twice (under ``allOf``) so both apply.  A keyword the
  binding does state keeps the binding's value; when that conflicts with the
  class it is drift.
* For ``cap.device.configure.v1`` the input schema is derived from the
  writable (non-``readOnly``) properties of the bound resource's state schema.
* Drift is reported, not repaired: a binding property the class does not
  define, a different type or ``x-mhs-unit``, an enum that is not a subset, a
  stated required set that is not a superset (or a closed binding schema that
  leaves out a class-required property), or any explicitly wider bound.
  Keywords a binding omits, and class properties an open binding does not
  list, are inherited from the class, so they are never drift.  A local
  ``$ref`` target or an ``allOf`` branch is conjoined with its node, so its
  keywords are compared with the class like the node's own.  Strict loaders
  refuse a drifting binding; compatibility mode warns and runs the binding's
  stated keywords, so it should also validate against ``class_input_schema``.

:func:`compile_manifest_limits` combines the resolver with :mod:`mhs.limits`
for a whole device manifest (class, binding, envelope and operator overlay).

Lookup order of the catalogue file: ``$MHS_SCHEMA_DIR`` (the file itself, or
``spec/capabilities.json`` next to that schema directory), the packaged
``mhs/_data/spec/capabilities.json`` (unless a source checkout holds a
different copy, which then wins), then the checkout's ``MHS/spec``.
"""

from __future__ import annotations

import copy
import json
import os
import re
import threading
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import canonical
from . import limits as _limits

__all__ = [
    "CONFIGURE_CLASS",
    "BindingLimits",
    "Catalog",
    "CatalogError",
    "Drift",
    "Effective",
    "ManifestLimits",
    "UnknownCapabilityError",
    "catalogue_path",
    "clear_default_catalog",
    "compile_manifest_limits",
    "configure_input_schema",
    "default_catalog",
    "extension_digest",
    "get",
    "is_extension",
    "is_skeleton",
    "merge_schema",
    "resolve_binding",
    "risk_at_least",
    "schema_digest",
    "search",
]

#: The generic write class served by ``mhs.resource.write``.
CONFIGURE_CLASS = "cap.device.configure.v1"
RISK_ORDER = ("R0", "R1", "R2", "R3")

_CAPABILITY_ID = re.compile(r"^(cap|x-cap)\.[a-z0-9_.-]+\.v[0-9]+$")
_WORD = re.compile(r"[a-z0-9]+")
_LOWER_BOUNDS = ("minimum", "exclusiveMinimum", "minItems", "minLength", "minProperties")
_UPPER_BOUNDS = ("maximum", "exclusiveMaximum", "maxItems", "maxLength", "maxProperties")
#: Keywords a binding schema inherits from its class schema when it omits them.
_INHERITED = ("type", "x-mhs-unit", "x-mhs-delta", "x-mhs-open", "enum", "const", "uniqueItems",
              "additionalProperties", *_LOWER_BOUNDS, *_UPPER_BOUNDS)
#: Keywords whose values cannot be ordered: when both state different values, both apply.
_CONJOINED = ("pattern", "format", "multipleOf")
_MAX_DEPTH = 32


class CatalogError(ValueError):
    """The catalogue cannot be loaded, or a binding cannot be resolved against it."""


class UnknownCapabilityError(CatalogError):
    """A ``cap.*`` id that is neither in the catalogue nor an extension id."""

    def __init__(self, capability_id: str):
        self.capability_id = capability_id
        super().__init__(
            f"unknown capability class {capability_id!r}; use a catalogued id or an "
            "extension id (x-cap.<owner>.<name>.v1 or cap.x.<owner>.<name>.v1) with inline schemas"
        )


def is_extension(capability_id: Any) -> bool:
    """True for extension ids (``x-cap.*`` and ``cap.x.*``), which the catalogue does not define."""
    return isinstance(capability_id, str) and capability_id.startswith(("x-cap.", "cap.x."))


def is_skeleton(schema: Any) -> bool:
    """True for a missing or placeholder schema (no properties and no combinator)."""
    if not isinstance(schema, Mapping):
        return True
    if any(key in schema for key in ("allOf", "anyOf", "oneOf", "$ref")):
        return False
    properties = schema.get("properties")
    return not (isinstance(properties, Mapping) and properties)


def schema_digest(schema: Any) -> str:
    """``sha256:<hex>`` of the JCS form of ``schema`` (CAP-037 ``x-mhs-schema-digest``)."""
    return canonical.digest(schema)


def extension_digest(input_schema: Any, output_schema: Any) -> str:
    """The schema digest of an extension binding: of ``{input_schema, output_schema}`` as written."""
    return schema_digest({"input_schema": input_schema, "output_schema": output_schema})


def risk_at_least(*risks: Any) -> str:
    """The highest of the given risk classes (unknown values are ignored; ``R0`` if none)."""
    best = 0
    for risk in risks:
        if risk in RISK_ORDER:
            best = max(best, RISK_ORDER.index(risk))
    return RISK_ORDER[best]


def configure_input_schema(state_schema: Any) -> dict[str, Any]:
    """The effective input of a ``cap.device.configure.v1`` binding: the writable state properties.

    Each property keeps its type, ``x-mhs-unit`` and bounds; ``readOnly``
    properties are excluded; the patch is partial (nothing is required) but
    must name at least one parameter.
    """
    properties = state_schema.get("properties") if isinstance(state_schema, Mapping) else None
    writable = {
        name: copy.deepcopy(dict(schema))
        for name, schema in (properties or {}).items()
        if isinstance(schema, Mapping) and not schema.get("readOnly")
    }
    return {"type": "object", "properties": writable, "additionalProperties": False, "minProperties": 1}


# ---------------------------------------------------------------------------
# results
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Drift:
    """One difference between a binding schema and its class schema."""

    kind: str
    path: str
    message: str

    def to_json(self) -> dict[str, str]:
        return {"kind": self.kind, "path": self.path, "message": self.message}


@dataclass(frozen=True)
class Effective:
    """The contract the runtime enforces for one binding.

    ``input_schema``/``output_schema`` are binding ∩ class (:func:`merge_schema`),
    or the class schema for a skeleton binding; ``class_input_schema`` and
    ``class_output_schema`` are the class schemas as catalogued.
    """

    capability_id: str
    verb: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    risk_floor: str
    requires_permit: bool
    class_limits: dict[str, Any]
    kind_ok: bool
    drift: tuple[Drift, ...] = ()
    mode_ok: bool = True
    status: str = "stable"
    extension: bool = False
    inherited_input: bool = False
    inherited_output: bool = False
    class_input_schema: dict[str, Any] | None = None
    class_output_schema: dict[str, Any] | None = None
    class_digest: str | None = None
    constraints: dict[str, Any] = field(default_factory=dict)
    title: str | None = None
    summary: str | None = None

    @property
    def drifted(self) -> bool:
        return bool(self.drift)

    def to_json(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "verb": self.verb,
            "status": self.status,
            "risk_floor": self.risk_floor,
            "requires_permit": self.requires_permit,
            "kind_ok": self.kind_ok,
            "mode_ok": self.mode_ok,
            "inherited_input": self.inherited_input,
            "inherited_output": self.inherited_output,
            "drift": [item.to_json() for item in self.drift],
        }


# ---------------------------------------------------------------------------
# drift
# ---------------------------------------------------------------------------


def _types(schema: Mapping[str, Any]) -> set[str]:
    declared = schema.get("type")
    if isinstance(declared, str):
        return {declared}
    if isinstance(declared, list):
        return {item for item in declared if isinstance(item, str)}
    return set()


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _same(left: Any, right: Any) -> bool:
    try:
        return canonical.jcs(left) == canonical.jcs(right)
    except (TypeError, ValueError):
        return left == right


def _item_unit(schema: Mapping[str, Any]) -> Any:
    items = schema.get("items")
    return items.get("x-mhs-unit") if isinstance(items, Mapping) else None


def _local_target(root: Any, ref: str) -> Any:
    """The schema a local ``$ref`` (``#/$defs/x``) designates inside ``root``, or ``None``."""
    node = root
    for raw in [part for part in ref[1:].split("/") if part]:
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, Mapping):
            node = node.get(key)
        elif isinstance(node, list) and key.isdigit() and int(key) < len(node):
            node = node[int(key)]
        else:
            return None
    return node


def _views(node: Any, root: Any, depth: int = 0, seen: set[int] | None = None) -> list[Mapping[str, Any]]:
    """``node`` and the schemas it conjoins: local ``$ref`` targets and ``allOf`` branches, recursively."""
    seen = set() if seen is None else seen
    if not isinstance(node, Mapping) or depth > _MAX_DEPTH or id(node) in seen:
        return []
    seen.add(id(node))
    out: list[Mapping[str, Any]] = [node]
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#"):
        out.extend(_views(_local_target(root, ref), root, depth + 1, seen))
    branches = node.get("allOf")
    for branch in branches if isinstance(branches, list) else ():
        out.extend(_views(branch, root, depth + 1, seen))
    return out


def _keyword_drift(binding: Mapping[str, Any], cls: Mapping[str, Any], path: str, out: list[Drift]) -> None:
    """Drift of the keywords one schema node states (not its properties, items or required set)."""
    btypes, ctypes = _types(binding), _types(cls)
    if btypes and ctypes and not all(t in ctypes or (t == "integer" and "number" in ctypes) for t in btypes):
        out.append(Drift("type-differs", path, f"type {sorted(btypes)} where the class has {sorted(ctypes)}"))
    bunit, cunit = binding.get("x-mhs-unit"), cls.get("x-mhs-unit")
    if isinstance(bunit, str) and isinstance(cunit, str) and bunit != cunit:
        out.append(Drift("unit-differs", path, f"x-mhs-unit {bunit!r} where the class has {cunit!r}"))
    elif isinstance(bunit, str) != isinstance(cunit, str):
        # one side states the unit on the array, the other on its items
        level, other = (bunit, _item_unit(cls)) if isinstance(bunit, str) else (_item_unit(binding), cunit)
        if isinstance(level, str) and isinstance(other, str) and level != other:
            out.append(Drift("unit-differs", path, f"x-mhs-unit {level!r} where the class has {other!r}"))
    if isinstance(binding.get("enum"), list) and isinstance(cls.get("enum"), list):
        extra = [item for item in binding["enum"] if not any(_same(item, other) for other in cls["enum"])]
        if extra:
            out.append(Drift("enum-not-subset", path, f"enum values {extra} are not in the class enum"))
    if isinstance(binding.get("enum"), list) and "const" in cls and "const" not in binding:
        extra = [item for item in binding["enum"] if not _same(item, cls["const"])]
        if extra:
            out.append(Drift("enum-not-subset", path, f"enum values {extra} differ from the class const"))
    if "const" in binding and isinstance(cls.get("enum"), list):
        if not any(_same(binding["const"], other) for other in cls["enum"]):
            out.append(Drift("enum-not-subset", path, "const is not in the class enum"))
    if "const" in binding and "const" in cls and not _same(binding["const"], cls["const"]):
        out.append(Drift("enum-not-subset", path, "const differs from the class const"))
    for keyword in _LOWER_BOUNDS:
        if _number(binding.get(keyword)) and _number(cls.get(keyword)) and binding[keyword] < cls[keyword]:
            out.append(Drift("widens", path, f"{keyword} {binding[keyword]} is below the class {cls[keyword]}"))
    for keyword in _UPPER_BOUNDS:
        if _number(binding.get(keyword)) and _number(cls.get(keyword)) and binding[keyword] > cls[keyword]:
            out.append(Drift("widens", path, f"{keyword} {binding[keyword]} is above the class {cls[keyword]}"))
    open_class = bool(cls.get("x-mhs-open")) or cls.get("additionalProperties") is not False
    if not open_class and binding.get("additionalProperties") not in (None, False):
        out.append(Drift("widens", path, "additionalProperties is open where the class is closed"))


def _schema_drift(binding: Any, cls: Any, path: str, out: list[Drift], depth: int = 0, root: Any = None) -> None:
    """Compare ``binding`` with ``cls``; a local ``$ref`` or ``allOf`` branch is compared like the node itself.

    A ``$ref`` target or ``allOf`` branch is conjoined with its node, so each
    keyword it states is drift exactly when the node stating it would be.
    The required set is the exception: a branch only adds required
    properties, so ``required-missing`` is reported only when the node itself
    states ``required`` and, together with its branches, leaves out a
    class-required property.
    """
    if not isinstance(binding, Mapping) or not isinstance(cls, Mapping) or depth > _MAX_DEPTH:
        return
    root = binding if root is None else root
    views = _views(binding, root)
    for view in views:
        _keyword_drift(view, cls, path, out)
    open_class = bool(cls.get("x-mhs-open")) or cls.get("additionalProperties") is not False
    cprops = cls.get("properties") if isinstance(cls.get("properties"), Mapping) else {}
    for view in views:
        bprops = view.get("properties") if isinstance(view.get("properties"), Mapping) else {}
        for name in bprops:
            child = f"{path}.{name}"
            if name in cprops:
                _schema_drift(bprops[name], cprops[name], child, out, depth + 1, root)
            elif not open_class:
                out.append(Drift("property-not-in-class", child, f"{name!r} is not a property of the class"))
    if isinstance(binding.get("required"), list) and isinstance(cls.get("required"), list):
        stated: set[Any] = set()
        for view in views:
            if isinstance(view.get("required"), list):
                stated.update(item for item in view["required"] if isinstance(item, str))
        missing = sorted(set(cls["required"]) - stated)
        if missing:
            out.append(Drift("required-missing", path, f"class-required {missing} are not required"))
    own = binding.get("properties") if isinstance(binding.get("properties"), Mapping) else {}
    if binding.get("additionalProperties") is False and isinstance(cls.get("required"), list):
        closed_out = sorted(name for name in set(cls["required"]) - set(own) if isinstance(name, str))
        if closed_out:
            out.append(Drift("required-missing", path,
                             f"class-required {closed_out} are not properties of the closed binding schema"))
    if isinstance(cls.get("items"), Mapping):
        for view in views:
            if isinstance(view.get("items"), Mapping):
                _schema_drift(view["items"], cls["items"], f"{path}[*]", out, depth + 1, root)
            if isinstance(view.get("prefixItems"), list):
                for index, item in enumerate(view["prefixItems"]):
                    _schema_drift(item, cls["items"], f"{path}[{index}]", out, depth + 1, root)


def merge_schema(binding: Any, cls: Any, _depth: int = 0) -> dict[str, Any]:
    """Binding ∩ class as one schema: ``binding`` with every class keyword it omits filled in.

    The class's ``type``, ``x-mhs-unit``, ``enum``/``const``, numeric, length
    and item-count bounds, ``required`` and ``additionalProperties`` are copied
    where the binding omits them; a ``pattern``, ``format`` or ``multipleOf``
    that both state differently is kept twice (the class's under ``allOf``).
    Properties the binding lists are merged with the class property of the
    same name.  The class's other properties are added with their class
    schemas when the binding is open (no ``additionalProperties: false``), and
    only the class-required ones when it is closed; a binding without
    ``properties`` takes the class's.
    ``items`` and ``prefixItems`` elements are merged with the class ``items``.
    A keyword the binding states keeps the binding's value: a conflict with the
    class is drift (reported by the resolver), never silently repaired.  The
    result is one schema (no ``allOf`` around the properties), so
    :mod:`mhs.limits` and the reference renderer see a single ``properties``
    map.  Neither argument is modified.
    """
    if binding is None or binding is True:
        return copy.deepcopy(dict(cls)) if isinstance(cls, Mapping) else {}
    if not isinstance(binding, Mapping):
        return copy.deepcopy(binding)
    out = copy.deepcopy(dict(binding))
    if not isinstance(cls, Mapping) or _depth > _MAX_DEPTH:
        return out
    for keyword in _INHERITED:
        if keyword not in out and keyword in cls:
            out[keyword] = copy.deepcopy(cls[keyword])
    conjoined = []
    for keyword in _CONJOINED:
        if keyword not in cls:
            continue
        if keyword not in out:
            out[keyword] = copy.deepcopy(cls[keyword])
        elif not _same(out[keyword], cls[keyword]):
            conjoined.append({keyword: copy.deepcopy(cls[keyword])})
    if conjoined:
        branches = out.get("allOf")
        out["allOf"] = (list(branches) if isinstance(branches, list) else [] if branches is None
                        else [branches]) + conjoined
    if "required" not in out and isinstance(cls.get("required"), list):
        out["required"] = copy.deepcopy(cls["required"])
    cprops = cls.get("properties") if isinstance(cls.get("properties"), Mapping) else None
    bprops = out.get("properties")
    if isinstance(bprops, Mapping):
        merged: dict[str, Any] = {}
        for name, sub in bprops.items():
            cprop = cprops.get(name) if cprops is not None else None
            merged[name] = merge_schema(sub, cprop, _depth + 1) if isinstance(cprop, Mapping) else sub
        extra = binding.get("additionalProperties", True)
        required = out.get("required") if isinstance(out.get("required"), list) else []
        for name, cprop in (cprops or {}).items():
            if name in merged:
                continue
            if extra is True or (extra is False and name in required):
                # an open binding accepts the class's other properties (with their class
                # schemas); a closed one still has to accept the class-required ones
                merged[name] = copy.deepcopy(cprop)
            elif isinstance(extra, Mapping):
                merged[name] = merge_schema(extra, cprop, _depth + 1)
        out["properties"] = merged
    elif "properties" not in out and cprops is not None:
        out["properties"] = copy.deepcopy(dict(cprops))
    citems = cls.get("items")
    if isinstance(citems, Mapping):
        prefix = out.get("prefixItems")
        if isinstance(prefix, list):
            out["prefixItems"] = [merge_schema(item, citems, _depth + 1) if isinstance(item, Mapping) else item
                                  for item in prefix]
        if isinstance(out.get("items"), Mapping):
            out["items"] = merge_schema(out["items"], citems, _depth + 1)
        elif out.get("items") is None or out.get("items") is True:
            out["items"] = copy.deepcopy(dict(citems))
    return out


def _limit_drift(binding_limits: Any, class_limits: Any, out: list[Drift]) -> None:
    if not isinstance(binding_limits, Mapping) or not isinstance(class_limits, Mapping):
        return
    for path, rule in binding_limits.items():
        cls = class_limits.get(path)
        if not isinstance(rule, Mapping) or not isinstance(cls, Mapping):
            continue
        for kind, wider in (("max", lambda b, c: b > c), ("min", lambda b, c: b < c)):
            bvalue, cvalue = rule.get(kind), cls.get(kind)
            if bvalue is None or cvalue is None:
                continue
            size = len(bvalue) if isinstance(bvalue, list) else len(cvalue) if isinstance(cvalue, list) else 1
            bitems = bvalue if isinstance(bvalue, list) else [bvalue] * size
            citems = cvalue if isinstance(cvalue, list) else [cvalue] * size
            if any(_number(b) and _number(c) and wider(b, c) for b, c in zip(bitems, citems)):
                out.append(Drift("limit-widens", f"limits.{path}.{kind}",
                                 f"binding {kind} {bvalue} is wider than the class {cvalue}"))
        if isinstance(rule.get("allowed"), list) and isinstance(cls.get("allowed"), list):
            extra = [item for item in rule["allowed"] if not any(_same(item, other) for other in cls["allowed"])]
            if extra:
                out.append(Drift("limit-widens", f"limits.{path}.allowed",
                                 f"binding allows {extra} beyond the class"))


# ---------------------------------------------------------------------------
# catalogue
# ---------------------------------------------------------------------------


class Catalog:
    """One loaded capability catalogue (``capabilities.json``)."""

    def __init__(self, document: Mapping[str, Any], *, path: Path | None = None):
        classes = document.get("capabilities") if isinstance(document, Mapping) else None
        if not isinstance(classes, list):
            raise CatalogError("a capability catalogue has a 'capabilities' list")
        self.document = document
        self.path = path
        self.spec_version = document.get("spec_version")
        self.digest = canonical.digest(document)
        self._classes: dict[str, Mapping[str, Any]] = {}
        for entry in classes:
            if isinstance(entry, Mapping) and isinstance(entry.get("capability_id"), str):
                self._classes[entry["capability_id"]] = entry
        self._synonyms: dict[str, set[str]] = {}
        kinds = document.get("resource_kinds")
        for entry in kinds if isinstance(kinds, list) else []:
            if isinstance(entry, Mapping) and isinstance(entry.get("kind"), str):
                self._synonyms.setdefault(entry["kind"], set()).update(
                    item for item in entry.get("see_also") or [] if isinstance(item, str))
        self.resource_kinds = tuple(sorted(self._synonyms))

    @classmethod
    def load(cls, path: str | os.PathLike[str] | None = None) -> "Catalog":
        """Load the catalogue from ``path`` or from :func:`catalogue_path`."""
        target = Path(path) if path is not None else catalogue_path()
        if target is None:
            raise CatalogError("capabilities.json not found (set MHS_SCHEMA_DIR or run MHS/sdk/tools/sync_data.py)")
        try:
            document = json.loads(Path(target).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CatalogError(f"cannot read the capability catalogue {target}: {exc}") from exc
        return cls(document, path=Path(target))

    # -- lookup ------------------------------------------------------------

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._classes))

    def __contains__(self, capability_id: object) -> bool:
        return capability_id in self._classes

    def __len__(self) -> int:
        return len(self._classes)

    def get(self, capability_id: str, default: Any = None) -> dict[str, Any] | Any:
        """A copy of the class document, or ``default`` when the id is not catalogued."""
        entry = self._classes.get(capability_id)
        return copy.deepcopy(dict(entry)) if entry is not None else default

    def class_digest(self, capability_id: str) -> str:
        """``x-mhs-schema-digest`` of a catalogued class document."""
        entry = self._classes.get(capability_id)
        if entry is None:
            raise UnknownCapabilityError(capability_id)
        return schema_digest(entry)

    def search(self, text: str, *, limit: int = 10, include_deprecated: bool = False) -> list[dict[str, Any]]:
        """Rank classes by how well ``text`` matches their id, title, tags, domain and summary."""
        query = str(text or "").strip().lower()
        words = _WORD.findall(query)
        if not words:
            return []
        results = []
        for capability_id, entry in self._classes.items():
            status = entry.get("status")
            if status == "deprecated" and not include_deprecated:
                continue
            score = 0
            if query == capability_id:
                score += 100
            fields = (
                (capability_id.lower(), 4),
                (str(entry.get("title") or "").lower(), 3),
                (" ".join(str(tag) for tag in entry.get("tags") or []).lower(), 3),
                (str(entry.get("domain") or "").lower(), 2),
                (str(entry.get("summary") or "").lower(), 1),
            )
            for value, weight in fields:
                tokens = set(_WORD.findall(value))
                score += weight * sum(1 for word in words if word in tokens)
                if len(words) > 1 and query in value:
                    score += weight * 2
            if score:
                results.append({
                    "capability_id": capability_id,
                    "title": entry.get("title"),
                    "verb": entry.get("verb"),
                    "status": status,
                    "domain": entry.get("domain"),
                    "summary": entry.get("summary"),
                    "score": score,
                })
        results.sort(key=lambda item: (-item["score"], item["capability_id"]))
        return results[: max(0, int(limit))]

    def kind_ok(self, capability_id: str, resource_kind: str | None) -> bool:
        """True when ``resource_kind`` is a declared kind (or synonym) of the class, or kinds are ``*``."""
        entry = self._classes.get(capability_id)
        if entry is None or resource_kind is None:
            return True
        kinds = [item for item in entry.get("resource_kinds") or [] if isinstance(item, str)]
        if not kinds or "*" in kinds or resource_kind in kinds:
            return True
        return any(resource_kind in self._synonyms.get(kind, ()) for kind in kinds)

    # -- resolution --------------------------------------------------------

    def resolve_binding(
        self,
        capability_id: str,
        binding_input_schema: Any = None,
        binding_output_schema: Any = None,
        resource_kind: str | None = None,
        device_mode: str | None = None,
        *,
        state_schema: Any = None,
        binding_limits: Any = None,
        binding_verb: str | None = None,
        binding_requires_permit: bool = False,
    ) -> Effective:
        """Resolve one binding against its class (see the module docstring).

        ``state_schema`` is the bound resource's state schema (required for
        ``cap.device.configure.v1``); ``binding_limits`` and ``binding_verb``
        add limit-widening and verb drift.  Raises
        :class:`UnknownCapabilityError` for an unknown ``cap.*`` id.
        """
        if not isinstance(capability_id, str) or not _CAPABILITY_ID.match(capability_id):
            raise CatalogError(f"invalid capability id {capability_id!r}")
        if is_extension(capability_id):
            return self._extension(capability_id, binding_input_schema, binding_output_schema,
                                   binding_verb, binding_requires_permit)
        entry = self._classes.get(capability_id)
        if entry is None:
            raise UnknownCapabilityError(capability_id)
        drift: list[Drift] = []
        class_input = copy.deepcopy(dict(entry.get("input_schema") or {}))
        class_output = copy.deepcopy(dict(entry.get("output_schema") or {}))
        if capability_id == CONFIGURE_CLASS:
            if not isinstance(state_schema, Mapping):
                raise CatalogError(f"{CONFIGURE_CLASS} needs the bound resource's state_schema")
            input_schema = configure_input_schema(state_schema)
            inherited_input = True
            if not is_skeleton(binding_input_schema):
                _schema_drift(binding_input_schema, input_schema, "input", drift)
            output_schema = copy.deepcopy(class_output)
            applied = (output_schema.get("properties") or {}).get("applied")
            if isinstance(applied, dict):
                applied["properties"] = copy.deepcopy(input_schema["properties"])
                applied["additionalProperties"] = False
                applied.pop("x-mhs-open", None)
            inherited_output = is_skeleton(binding_output_schema)
            if not inherited_output:
                _schema_drift(binding_output_schema, output_schema, "output", drift)
        else:
            inherited_input = is_skeleton(binding_input_schema)
            if inherited_input:
                input_schema = copy.deepcopy(class_input)
            else:
                _schema_drift(binding_input_schema, class_input, "input", drift)
                input_schema = merge_schema(binding_input_schema, class_input)
            inherited_output = is_skeleton(binding_output_schema)
            if inherited_output:
                output_schema = copy.deepcopy(class_output)
            else:
                _schema_drift(binding_output_schema, class_output, "output", drift)
                output_schema = merge_schema(binding_output_schema, class_output)
        verb = str(entry.get("verb") or "invoke")
        if binding_verb is not None and binding_verb != verb:
            drift.append(Drift("verb-differs", "verb", f"binding verb {binding_verb!r} where the class verb is {verb!r}"))
        class_limits = copy.deepcopy(dict(entry.get("limits") or {}))
        _limit_drift(binding_limits, class_limits, drift)
        modes = [item for item in entry.get("modes") or [] if isinstance(item, str)]
        status = str(entry.get("status") or "stable")
        return Effective(
            capability_id=capability_id,
            verb=verb,
            input_schema=input_schema,
            output_schema=output_schema,
            risk_floor=str(entry.get("risk_class") or "R0"),
            requires_permit=bool(entry.get("requires_permit")) or bool(binding_requires_permit),
            class_limits=class_limits,
            kind_ok=self.kind_ok(capability_id, resource_kind),
            drift=tuple(dict.fromkeys(drift)),
            mode_ok=device_mode is None or not modes or device_mode in modes,
            status="stable" if status == "active" else status,
            extension=False,
            inherited_input=inherited_input,
            inherited_output=inherited_output,
            class_input_schema=class_input,
            class_output_schema=class_output,
            class_digest=schema_digest(entry),
            constraints=copy.deepcopy(dict(entry.get("constraints") or {})),
            title=entry.get("title"),
            summary=entry.get("summary"),
        )

    def _extension(self, capability_id: str, input_schema: Any, output_schema: Any, verb: str | None,
                   requires_permit: bool) -> Effective:
        return Effective(
            capability_id=capability_id,
            verb=verb if verb in ("read", "write", "invoke") else "invoke",
            input_schema=copy.deepcopy(dict(input_schema)) if isinstance(input_schema, Mapping)
            else {"type": "object", "properties": {}},
            output_schema=copy.deepcopy(dict(output_schema)) if isinstance(output_schema, Mapping)
            else {"type": "object"},
            risk_floor="R0",
            requires_permit=bool(requires_permit),
            class_limits={},
            kind_ok=True,
            status="extension",
            extension=True,
        )


# ---------------------------------------------------------------------------
# default catalogue
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve()
_default_lock = threading.Lock()
_default: tuple[tuple, Catalog] | None = None
_stale_warned = False


def _checkout_catalogue() -> Path | None:
    parents = _HERE.parents
    if len(parents) < 4 or parents[1].name != "src" or parents[2].name != "sdk":
        return None
    candidate = parents[3] / "spec" / "capabilities.json"
    return candidate if candidate.is_file() else None


def _packaged_catalogue() -> Path | None:
    try:
        from .schema.store import packaged_data_dir
    except ImportError:  # pragma: no cover - partial installs
        return None
    data = packaged_data_dir()
    candidate = data / "spec" / "capabilities.json" if data is not None else None
    return candidate if candidate is not None and candidate.is_file() else None


def catalogue_path() -> Path | None:
    """Return the ``capabilities.json`` this process uses (see the module docstring)."""
    env = os.environ.get("MHS_SCHEMA_DIR")
    if env:
        base = Path(env).expanduser()
        for candidate in (base / "capabilities.json", base / "spec" / "capabilities.json",
                          base.parent / "spec" / "capabilities.json"):
            if candidate.is_file():
                return candidate
    packaged = _packaged_catalogue()
    checkout = _checkout_catalogue()
    if packaged is not None:
        if checkout is not None:
            try:
                stale = packaged.read_bytes() != checkout.read_bytes()
            except OSError:  # pragma: no cover - unreadable file
                stale = True
            if stale:
                _warn_stale(packaged, checkout)
                return checkout
        return packaged
    return checkout


def _warn_stale(packaged: Path, checkout: Path) -> None:
    global _stale_warned
    with _default_lock:
        if _stale_warned:
            return
        _stale_warned = True
    warnings.warn(
        f"packaged capability catalogue {packaged} differs from the checkout's {checkout}; using the "
        "checkout (run MHS/sdk/tools/sync_data.py before building a wheel)",
        RuntimeWarning,
        stacklevel=3,
    )


def default_catalog() -> Catalog:
    """The process-wide catalogue, reloaded when the file or ``MHS_SCHEMA_DIR`` changes."""
    global _default
    path = catalogue_path()
    if path is None:
        raise CatalogError("capabilities.json not found (set MHS_SCHEMA_DIR or run MHS/sdk/tools/sync_data.py)")
    try:
        stat = path.stat()
        key: tuple = (str(path), stat.st_size, stat.st_mtime_ns)
    except OSError as exc:  # pragma: no cover - vanished file
        raise CatalogError(f"cannot read the capability catalogue {path}: {exc}") from exc
    with _default_lock:
        if _default is not None and _default[0] == key:
            return _default[1]
    catalog = Catalog.load(path)
    with _default_lock:
        _default = (key, catalog)
    return catalog


def clear_default_catalog() -> None:
    """Forget the cached default catalogue (tests that switch ``MHS_SCHEMA_DIR``)."""
    global _default
    with _default_lock:
        _default = None


def get(capability_id: str, default: Any = None) -> dict[str, Any] | Any:
    """:meth:`Catalog.get` on the default catalogue."""
    return default_catalog().get(capability_id, default)


def search(text: str, *, limit: int = 10, include_deprecated: bool = False) -> list[dict[str, Any]]:
    """:meth:`Catalog.search` on the default catalogue."""
    return default_catalog().search(text, limit=limit, include_deprecated=include_deprecated)


def resolve_binding(capability_id: str, binding_input_schema: Any = None, binding_output_schema: Any = None,
                    resource_kind: str | None = None, device_mode: str | None = None, **options: Any) -> Effective:
    """:meth:`Catalog.resolve_binding` on the default catalogue."""
    return default_catalog().resolve_binding(capability_id, binding_input_schema, binding_output_schema,
                                             resource_kind, device_mode, **options)


# ---------------------------------------------------------------------------
# manifest limits
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BindingLimits:
    """The resolved contract and compiled limits of one binding of a manifest."""

    capability_id: str
    resource: str
    effective: Effective
    limits: _limits.EffectiveLimits


@dataclass(frozen=True)
class ManifestLimits:
    """Compiled limits of every binding of one device manifest."""

    device_id: str
    bindings: tuple[BindingLimits, ...]
    unused_envelope: tuple[str, ...] = ()

    def get(self, capability_id: str, resource: str | None = None) -> BindingLimits | None:
        """The binding of ``capability_id`` (on ``resource`` when several resources bind it)."""
        matches = [item for item in self.bindings if item.capability_id == capability_id
                   and (resource is None or item.resource == resource)]
        return matches[0] if len(matches) == 1 or (matches and resource is not None) else None

    def by_capability(self) -> dict[tuple[str, str], _limits.EffectiveLimits]:
        return {(item.capability_id, item.resource): item.limits for item in self.bindings}

    @property
    def narrowed(self) -> tuple[str, ...]:
        """What the operator overlay narrowed, e.g. ``setpoint.max: 150 -> 95``."""
        out: list[str] = []
        for item in self.bindings:
            prefix = "" if item.capability_id == CONFIGURE_CLASS else f"{item.capability_id} "
            out.extend(prefix + message for message in item.limits.narrowed)
        return tuple(out)

    @property
    def unset(self) -> tuple[tuple[str, str, str], ...]:
        """``(capability_id, resource, path)`` of every operator_required bound not yet supplied."""
        return tuple((item.capability_id, item.resource, path) for item in self.bindings for path in item.limits.unset)


def compile_manifest_limits(manifest: Mapping[str, Any], overlay: Mapping[str, Any] | None = None, *,
                            catalog: Catalog | None = None) -> ManifestLimits:
    """Resolve every binding of ``manifest`` and intersect its class, binding, envelope and overlay limits.

    Raises :class:`CatalogError` for an unknown class or an undeclared
    resource and :class:`mhs.limits.LimitConfigError` for any limit defect,
    including an envelope pattern path that resolves in no bound capability
    and overlay entries that name an unbound capability or an unknown
    parameter.  Envelope entries for capabilities the manifest does not bind
    are returned in :attr:`ManifestLimits.unused_envelope`.
    """
    catalog = catalog or default_catalog()
    device_id = str(manifest.get("device_id") or "")
    mode = manifest.get("mode")
    resources = {item.get("resource_id"): item for item in manifest.get("resources") or [] if isinstance(item, Mapping)}
    safety = manifest.get("safety") if isinstance(manifest.get("safety"), Mapping) else {}
    envelope = safety.get("envelope") if isinstance(safety.get("envelope"), Mapping) else {}
    results: list[BindingLimits] = []
    pattern_hits: dict[str, set[str]] = {}
    parameter_hits: set[str] = set()
    bound_ids: set[str] = set()
    for index, binding in enumerate(manifest.get("capabilities") or []):
        if not isinstance(binding, Mapping):
            raise CatalogError(f"capabilities[{index}] is not an object")
        capability_id = str(binding.get("capability_id"))
        resource_id = binding.get("resource")
        resource = resources.get(resource_id)
        if resource is None:
            raise CatalogError(f"capabilities[{index}] {capability_id} binds undeclared resource {resource_id!r}")
        bound_ids.add(capability_id)
        effective = catalog.resolve_binding(
            capability_id, binding.get("input_schema"), binding.get("output_schema"), resource.get("kind"), mode,
            state_schema=resource.get("state_schema"), binding_limits=binding.get("limits"),
            binding_verb=binding.get("verb"), binding_requires_permit=bool(binding.get("requires_permit")),
        )
        sources = [
            _limits.LimitSource("class", effective.class_limits, partial=True, default_source="class_default"),
            _limits.LimitSource("binding", binding.get("limits")),
            *_limits.envelope_sources(envelope, capability_id),
        ]
        narrow = _limits.overlay_sources(overlay, device_id, capability_id,
                                         parameter_paths=capability_id == CONFIGURE_CLASS, partial_parameters=True)
        compiled = _limits.compile_limits(effective.input_schema, sources, narrow)
        skipped = {(label, path) for label, path in compiled.skipped}
        for pattern in envelope:
            if _limits.pattern_matches(pattern, capability_id) and pattern != capability_id:
                hits = pattern_hits.setdefault(pattern, set())
                hits.update(path for path in envelope[pattern] or {}
                            if (f"envelope:{pattern}", path) not in skipped)
        if capability_id == CONFIGURE_CLASS:
            parameter_hits.update(path for label, path in _overlay_parameter_paths(overlay, device_id)
                                  if ("overlay", path) not in skipped)
        results.append(BindingLimits(capability_id, str(resource_id), effective, compiled))
    for pattern, rules in envelope.items():
        if pattern.endswith(".*") and pattern in pattern_hits:
            for path in rules or {}:
                if path not in pattern_hits[pattern]:
                    raise _limits.LimitConfigError(f"envelope path {path!r} resolves in no capability matching "
                                                   f"{pattern}", rule="limit-path-resolves", path=path,
                                                   source=f"envelope:{pattern}")
    unused = tuple(sorted(pattern for pattern in envelope
                          if not any(_limits.pattern_matches(pattern, cid) for cid in bound_ids)))
    _check_overlay_targets(overlay, device_id, bound_ids, parameter_hits)
    return ManifestLimits(device_id, tuple(results), unused)


def _overlay_parameter_paths(overlay: Any, device_id: str) -> list[tuple[str, str]]:
    devices = overlay.get("devices") if isinstance(overlay, Mapping) else None
    entry = devices.get(device_id) if isinstance(devices, Mapping) else None
    if not isinstance(entry, Mapping):
        return []
    return [("overlay", key) for key in entry if not key.startswith(("cap.", "x-cap."))]


def _check_overlay_targets(overlay: Any, device_id: str, bound_ids: Iterable[str], parameter_hits: set[str]) -> None:
    devices = overlay.get("devices") if isinstance(overlay, Mapping) else None
    entry = devices.get(device_id) if isinstance(devices, Mapping) else None
    if not isinstance(entry, Mapping):
        return
    bound = set(bound_ids)
    for key in entry:
        if key.startswith(("cap.", "x-cap.")):
            if key not in bound:
                raise _limits.LimitConfigError(f"overlay names {key}, which {device_id} does not bind",
                                               rule="overlay-binding-known", path=key, source="overlay")
        elif key not in parameter_hits:
            raise _limits.LimitConfigError(f"overlay parameter {key!r} is not a writable parameter of {device_id}",
                                           rule="limit-path-resolves", path=key, source="overlay")

"""Deterministic reference-file renderer (plan 3.4; ``reference.schema.json``).

A reference file says what a device can measure, what can be adjusted and
within which *enforced* limits, which actions it offers, its safety facts and
where every statement comes from.  It is generated, never written by hand:
:func:`render` builds it from the device manifest, the capability catalogue,
the effective limits (class, binding, envelope and operator overlay), tags and
facts; :func:`render_markdown` gives the human view (``REFERENCE.md``) with the
sections Measures, Adjusts, Actions, Safety and Facts; :func:`dump` gives the
JCS bytes, so the same inputs always produce the same file.

Mapping from a manifest:

* **measures** are the resource state properties that are not adjustable,
  plus read-verb bindings that need no input (nothing required, nothing
  limited, no permit, risk R0), typed after their first required output field
  with a unit (``temperature`` of ``cap.measure.temperature.v1``); such a
  measure lists the optional parameters it accepts as ``inputs``;
* **adjusts** are the writable (non-``readOnly``) state properties of a
  resource bound to ``cap.device.configure.v1``, each with its effective limit
  or ``operator_required``;
* **actions** are every other binding, with typed inputs (and their effective
  limits) and outputs.  An action is named by the binding member
  ``x-mhs-name`` when present, otherwise after its capability id
  (``cap.fluid.aspirate.v1`` -> ``fluid.aspirate``);
* risks never fall below the class floor or the device's declared risk class;
* ``safety`` copies the manifest's e-stop, safe state, interlocks and
  watchdog; ``safety.estop.native`` is the native stop the runtime calls,
  given by the driver (``render(..., estop_native=...)``) or the manifest.

Limits passed in precompiled must be the ones the recorded overlay produces:
when an overlay is given, every given binding's limits are compared with
:func:`mhs.catalog.compile_manifest_limits` of the manifest and that overlay,
so a file can never record an overlay its limits do not apply.
"""

from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import canonical
from ._ids import SCHEMA_BASE, SDK_VERSION, SPEC_VERSION
from .catalog import (
    CONFIGURE_CLASS,
    BindingLimits,
    Catalog,
    ManifestLimits,
    compile_manifest_limits,
    default_catalog,
    risk_at_least,
)
from .limits import WILDCARD, EffectiveLimits, EffectiveRule, format_path

__all__ = [
    "GENERATED_BY",
    "PROVENANCE_KEYS",
    "ReferenceFileError",
    "dump",
    "render",
    "render_markdown",
    "validate",
]

#: ``provenance.generated_by`` of every rendered file.
GENERATED_BY = "mhs.reference_file"
#: The provenance members a caller may add; the rest are generated.
PROVENANCE_KEYS = ("authored_by", "reviewed_by")
_UNSET = object()

_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TAG = re.compile(r"^[a-z0-9][a-z0-9 -]{0,79}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")
_JSON_TYPES = ("number", "integer", "boolean", "string", "array", "object", "null")
_FACT_SOURCES = ("vendor_doc", "upstream_code", "operator", "interview")
_MAX_FIELD_DEPTH = 4


class ReferenceFileError(ValueError):
    """The inputs cannot be rendered into a valid reference file."""


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _json_type(schema: Any) -> str:
    if not isinstance(schema, Mapping):
        return "object"
    declared = schema.get("type")
    if isinstance(declared, str) and declared in _JSON_TYPES:
        return declared
    if isinstance(declared, list):
        for item in declared:
            if item in _JSON_TYPES and item != "null":
                return item
        if "null" in declared:
            return "null"
    sample = None
    if "const" in schema:
        sample = schema["const"]
    elif isinstance(schema.get("enum"), list) and schema["enum"]:
        sample = schema["enum"][0]
    if isinstance(sample, bool):
        return "boolean"
    if isinstance(sample, int):
        return "integer"
    if isinstance(sample, float):
        return "number"
    if isinstance(sample, str):
        return "string"
    if "items" in schema or "prefixItems" in schema:
        return "array"
    return "object"


def _items(schema: Mapping[str, Any]) -> Mapping[str, Any] | None:
    items = schema.get("items")
    return items if isinstance(items, Mapping) else None


def _unit(schema: Mapping[str, Any]) -> str | None:
    unit = schema.get("x-mhs-unit")
    if not isinstance(unit, str):
        items = _items(schema)
        unit = items.get("x-mhs-unit") if items is not None else None
    return unit if isinstance(unit, str) and unit else None


def _length(schema: Mapping[str, Any]) -> int | None:
    low, high = schema.get("minItems"), schema.get("maxItems")
    if isinstance(low, int) and not isinstance(low, bool) and low == high and low >= 1:
        return low
    return None


def _describe(schema: Mapping[str, Any], fallback: Any = None, limit: int = 1000) -> str | None:
    text = schema.get("description") if isinstance(schema.get("description"), str) else fallback
    if not isinstance(text, str) or not text.strip():
        return None
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _limit_value(rule: EffectiveRule | None) -> Any:
    if rule is None:
        return None
    if rule.unset:
        return "operator_required"
    if rule.has_bound:
        return rule.to_json()
    return None


def _manifest_digest(manifest: Mapping[str, Any]) -> str:
    return canonical.digest({key: value for key, value in manifest.items() if key != "reference"})


def _action_name(binding: Mapping[str, Any], capability_id: str) -> str:
    declared = binding.get("x-mhs-name")
    if isinstance(declared, str) and _NAME.match(declared) and len(declared) <= 128:
        return declared
    name = capability_id
    for prefix in ("x-cap.", "cap."):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    return re.sub(r"\.v[0-9]+$", "", name)


def _load_overlay(overlay: Any) -> tuple[Mapping[str, Any] | None, str | None]:
    if overlay is None:
        return None, None
    if isinstance(overlay, Mapping):
        return overlay, None
    if isinstance(overlay, (str, os.PathLike)):
        path = Path(overlay)
        try:
            return json.loads(path.read_text(encoding="utf-8")), path.name
        except (OSError, ValueError) as exc:
            raise ReferenceFileError(f"cannot read the operator overlay {path}: {exc}") from exc
    raise ReferenceFileError("overlay must be a site-limits document or a path to one")


def _fact(item: Any) -> dict[str, Any]:
    if hasattr(item, "to_json") and callable(item.to_json):
        item = item.to_json()
    if isinstance(item, Mapping):
        data = dict(item)
    else:
        data = {key: getattr(item, key) for key in ("text", "source", "ref", "reviewed_by") if hasattr(item, key)}
    out: dict[str, Any] = {}
    for key in ("text", "source", "ref", "reviewed_by"):
        if key in data and (data[key] is not None or key == "reviewed_by"):
            out[key] = data[key]
    if out.get("source") not in _FACT_SOURCES:
        raise ReferenceFileError(f"fact source must be one of {list(_FACT_SOURCES)}, got {out.get('source')!r}")
    if out["source"] in ("vendor_doc", "upstream_code") and not out.get("ref"):
        raise ReferenceFileError(f"a {out['source']} fact must cite ref (file:line or a manual page)")
    return out


# ---------------------------------------------------------------------------
# field descriptors
# ---------------------------------------------------------------------------


def _field_entries(schema: Mapping[str, Any], limits: EffectiveLimits | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    _walk_fields(schema, (), True, limits, out, seen, 0)
    if limits is not None:
        for path, rule in limits.rules.items():
            if path in seen:
                continue
            value = _limit_value(rule)
            if value is None:
                continue
            entry = _descriptor(path, rule.field.schema, None, rule)
            out.append(entry)
            seen.add(path)
    return out


def _walk_fields(schema: Any, prefix: tuple[Any, ...], parent_required: bool, limits: EffectiveLimits | None,
                 out: list[dict[str, Any]], seen: set[str], depth: int) -> None:
    if not isinstance(schema, Mapping) or depth > _MAX_FIELD_DEPTH:
        return
    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        return
    required = set(schema.get("required") or []) if isinstance(schema.get("required"), list) else set()
    for name, sub in properties.items():
        if not isinstance(name, str) or not _IDENT.match(name):
            raise ReferenceFileError(f"field name {name!r} is not an identifier; it cannot be a limit path")
        if not isinstance(sub, Mapping):
            continue
        tokens = prefix + (name,)
        path = format_path(tokens)
        rule = limits.rules.get(path) if limits is not None else None
        out.append(_descriptor(path, sub, parent_required and name in required, rule))
        seen.add(path)
        _walk_fields(sub, tokens, parent_required and name in required, limits, out, seen, depth + 1)
        items = _items(sub)
        if items is not None and isinstance(items.get("properties"), Mapping):
            _walk_fields(items, tokens + (WILDCARD,), False, limits, out, seen, depth + 1)


def _descriptor(path: str, schema: Mapping[str, Any], required: bool | None, rule: EffectiveRule | None) -> dict[str, Any]:
    entry: dict[str, Any] = {"name": path, "type": _json_type(schema)}
    items = _items(schema)
    if entry["type"] == "array" and items is not None:
        entry["items_type"] = _json_type(items)
    unit = _unit(schema)
    if unit:
        entry["unit"] = unit
    description = _describe(schema)
    if description:
        entry["description"] = description
    if required is not None:
        entry["required"] = bool(required)
    if isinstance(schema.get("enum"), list) and schema["enum"]:
        entry["enum"] = copy.deepcopy(schema["enum"])
    if "default" in schema:
        entry["default"] = copy.deepcopy(schema["default"])
    length = _length(schema)
    if length is not None:
        entry["length"] = length
    if rule is not None and rule.names is not None:
        entry["names"] = list(rule.names)
    limit = _limit_value(rule)
    if limit is not None:
        entry["limit"] = limit
    return entry


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------


def _limits_key(limits: EffectiveLimits) -> Any:
    """What a reference file publishes of one binding's limits (per-call rules and budgets)."""
    budgets = [(item.path, item.per, item.max.value, item.unit, item.max.origin.source) for item in limits.cumulative]
    return canonical.jcs({"rules": limits.to_json(), "cumulative": budgets})


def _check_overlay_applied(entries: list[BindingLimits], manifest: Mapping[str, Any], overlay: Mapping[str, Any],
                           catalog: Catalog) -> None:
    """Refuse given limits that differ from the ones the recorded ``overlay`` produces."""
    standard = compile_manifest_limits(manifest, overlay, catalog=catalog)
    for item in entries:
        expected = standard.get(item.capability_id, item.resource)
        if expected is None or _limits_key(expected.limits) != _limits_key(item.limits):
            raise ReferenceFileError(
                f"the effective limits given for {item.capability_id} on {item.resource} were not compiled with "
                "the operator overlay the file would record; pass limits from "
                "mhs.catalog.compile_manifest_limits(manifest, overlay) or omit them")


def _binding_entries(manifest: Mapping[str, Any], given: Any, overlay: Mapping[str, Any] | None,
                     catalog: Catalog) -> list[BindingLimits]:
    if given is None:
        return list(compile_manifest_limits(manifest, overlay, catalog=catalog).bindings)
    entries = _given_entries(manifest, given, overlay, catalog)
    if overlay is not None:
        _check_overlay_applied(entries, manifest, overlay, catalog)
    return entries


def _given_entries(manifest: Mapping[str, Any], given: Any, overlay: Mapping[str, Any] | None,
                   catalog: Catalog) -> list[BindingLimits]:
    if isinstance(given, ManifestLimits):
        return list(given.bindings)
    if not isinstance(given, Mapping):
        raise ReferenceFileError("effective limits are a ManifestLimits or a {capability id: EffectiveLimits} mapping")
    resources = {item.get("resource_id"): item for item in manifest.get("resources") or [] if isinstance(item, Mapping)}
    standard: ManifestLimits | None = None
    out: list[BindingLimits] = []
    for binding in manifest.get("capabilities") or []:
        capability_id = str(binding.get("capability_id"))
        resource_id = str(binding.get("resource"))
        resource = resources.get(resource_id) or {}
        effective = catalog.resolve_binding(
            capability_id, binding.get("input_schema"), binding.get("output_schema"), resource.get("kind"),
            manifest.get("mode"), state_schema=resource.get("state_schema"), binding_limits=binding.get("limits"),
            binding_verb=binding.get("verb"), binding_requires_permit=bool(binding.get("requires_permit")),
        )
        compiled = given.get((capability_id, resource_id), given.get(capability_id))
        if isinstance(compiled, BindingLimits):
            compiled = compiled.limits
        if compiled is None:
            # not in a partial mapping: compile it the standard way, overlay included,
            # so the overlay recorded in the file applies to every binding
            if standard is None:
                standard = compile_manifest_limits(manifest, overlay, catalog=catalog)
            found = standard.get(capability_id, resource_id)
            compiled = found.limits if found is not None else None
        if not isinstance(compiled, EffectiveLimits):
            raise ReferenceFileError(f"effective limits for {capability_id} must be an EffectiveLimits")
        out.append(BindingLimits(capability_id, resource_id, effective, compiled))
    return out


def render(
    manifest: Mapping[str, Any],
    effective_limits_by_capability: Any = None,
    overlay: Any = None,
    facts: Iterable[Any] = (),
    tags: Iterable[str] = (),
    provenance: Mapping[str, Any] | None = None,
    *,
    catalog: Catalog | None = None,
    upstream: Mapping[str, Any] | None = None,
    estop_native: Any = _UNSET,
) -> dict[str, Any]:
    """Render the reference file of one device manifest (a dict valid against ``reference.schema.json``).

    ``effective_limits_by_capability`` is a :class:`mhs.catalog.ManifestLimits`
    or a mapping ``{capability id or (capability id, resource): EffectiveLimits}``;
    when omitted the limits are compiled from the manifest and ``overlay``
    (a site-limits document or a path to one).  ``facts`` are mappings or
    objects with ``text``, ``source``, ``ref`` and ``reviewed_by``;
    ``provenance`` may add ``authored_by`` and ``reviewed_by`` (nothing else:
    the generator, SDK version and digests are always generated); ``upstream``
    is ``{repo, commit}`` (defaults to the manifest provenance);
    ``estop_native`` is the native stop the runtime calls (a method name, or
    ``None`` for a software-only stop) and becomes ``safety.estop.native``
    (defaults to the manifest's ``safety.estop.native`` when present).  Raises
    :class:`ReferenceFileError` when the result would not validate.
    """
    if not isinstance(manifest, Mapping):
        raise ReferenceFileError("manifest must be a device manifest object")
    if provenance is not None and not isinstance(provenance, Mapping):
        raise ReferenceFileError("provenance must be an object with authored_by and/or reviewed_by")
    unknown = sorted(str(key) for key in provenance or {} if key not in PROVENANCE_KEYS)
    if unknown:
        raise ReferenceFileError(f"provenance may only add {list(PROVENANCE_KEYS)}; {unknown} are generated")
    catalog = catalog or default_catalog()
    overlay_doc, overlay_file = _load_overlay(overlay)
    entries = _binding_entries(manifest, effective_limits_by_capability, overlay_doc, catalog)
    safety = manifest.get("safety") if isinstance(manifest.get("safety"), Mapping) else {}
    device_risk = str(safety.get("risk_class") or "R0")
    operator_required: list[dict[str, Any]] = []

    measures: list[dict[str, Any]] = []
    adjusts: list[dict[str, Any]] = []
    configure = {item.resource: item for item in entries if item.capability_id == CONFIGURE_CLASS}
    for resource in manifest.get("resources") or []:
        if not isinstance(resource, Mapping):
            continue
        resource_id = str(resource.get("resource_id"))
        state = resource.get("state_schema") if isinstance(resource.get("state_schema"), Mapping) else {}
        bound = configure.get(resource_id)
        for name, schema in (state.get("properties") or {}).items():
            if not isinstance(schema, Mapping):
                continue
            if not isinstance(name, str) or not _NAME.match(name) or len(name) > 128:
                raise ReferenceFileError(f"state property {name!r} of {resource_id} is not a valid parameter name")
            if bound is not None and not schema.get("readOnly"):
                adjusts.append(_adjust(name, schema, resource_id, bound, device_risk, operator_required))
            else:
                measures.append(_measure(name, schema, resource_id))

    actions: list[dict[str, Any]] = []
    names_used: dict[str, int] = {}
    for item in entries:
        if item.capability_id != CONFIGURE_CLASS:
            base = _action_name(_binding(manifest, item), item.capability_id)
            names_used[base] = names_used.get(base, 0) + 1
    for item in entries:
        if item.capability_id == CONFIGURE_CLASS:
            continue
        binding = _binding(manifest, item)
        name = _action_name(binding, item.capability_id)
        if names_used.get(name, 0) > 1:
            name = f"{name}.{item.resource}"
        effective = item.effective
        if (effective.verb == "read" and not effective.requires_permit and effective.risk_floor == "R0"
                and _needs_no_input(effective.input_schema, item.limits)):
            measures.append(_read_measure(name, item, binding))
            continue
        actions.append(_action(name, binding, item, device_risk, operator_required, catalog))

    risks = [device_risk] + [entry["risk"] for entry in actions] + [entry["risk"] for entry in adjusts if "risk" in entry]
    device: dict[str, Any] = {
        "id": str(manifest.get("device_id")),
        "kind": _device_kind(manifest),
        "name": str(manifest.get("display_name") or manifest.get("device_id")),
    }
    vendor = manifest.get("vendor")
    if isinstance(vendor, Mapping) and isinstance(vendor.get("name"), str) and vendor["name"]:
        device["vendor"] = vendor["name"][:200]
    if isinstance(manifest.get("model"), str) and manifest["model"]:
        device["model"] = manifest["model"][:200]
    device["mode"] = str(manifest.get("mode"))
    device["risk"] = risk_at_least(*risks)
    if isinstance(manifest.get("models"), list) and manifest["models"]:
        device["models"] = [str(item) for item in manifest["models"]]
    composed = _composed_resources(manifest)
    if composed:
        device["resources"] = composed
    upstream_doc = _upstream(manifest, upstream)
    if upstream_doc is not None:
        device["upstream"] = upstream_doc

    tag_list: list[str] = []
    profile = manifest.get("profile") if isinstance(manifest.get("profile"), Mapping) else {}
    for tag in list(tags) + list(profile.get("tags") or []):
        if not isinstance(tag, str) or not _TAG.match(tag):
            raise ReferenceFileError(f"tag {tag!r} is not a short lowercase keyword")
        if tag not in tag_list:
            tag_list.append(tag)

    reference: dict[str, Any] = {
        "$schema": SCHEMA_BASE + "reference.schema.json",
        "openmhs": SPEC_VERSION,
        "device": device,
        "measures": measures,
        "adjusts": adjusts,
        "actions": actions,
        "safety": _safety(manifest, safety, operator_required, estop_native),
        "facts": [_fact(item) for item in facts],
        "tags": tag_list,
    }
    if isinstance(manifest.get("fidelity"), Mapping):
        reference["fidelity"] = copy.deepcopy(dict(manifest["fidelity"]))
    if overlay_doc is not None:
        narrowed: list[str] = []
        for item in entries:
            prefix = "" if item.capability_id == CONFIGURE_CLASS else f"{item.capability_id} "
            narrowed.extend(prefix + message for message in item.limits.narrowed)
        overlay_entry: dict[str, Any] = {"digest": canonical.digest(overlay_doc), "narrowed": narrowed}
        if overlay_file:
            overlay_entry["file"] = overlay_file
        reference["overlay"] = overlay_entry
    else:
        reference["overlay"] = None
    record: dict[str, Any] = {
        "generated_by": GENERATED_BY,
        "sdk_version": SDK_VERSION,
        "catalogue_digest": catalog.digest,
        "manifest_digest": _manifest_digest(manifest),
    }
    for key in PROVENANCE_KEYS:
        if provenance and key in provenance:
            record[key] = copy.deepcopy(provenance[key])
    reference["provenance"] = record
    problems = validate(reference)
    if problems:
        raise ReferenceFileError("rendered reference file is invalid: " + "; ".join(problems[:5]))
    return reference


def _binding(manifest: Mapping[str, Any], item: BindingLimits) -> Mapping[str, Any]:
    for binding in manifest.get("capabilities") or []:
        if (isinstance(binding, Mapping) and binding.get("capability_id") == item.capability_id
                and str(binding.get("resource")) == item.resource):
            return binding
    return {}


def _composed_resources(manifest: Mapping[str, Any]) -> list[dict[str, str]] | None:
    """``[{id, kind, title?}]`` of a device with several resources (package composition); ``None`` for one."""
    resources = [item for item in manifest.get("resources") or [] if isinstance(item, Mapping)]
    if len(resources) < 2:
        return None
    out = []
    for item in resources:
        entry = {"id": str(item.get("resource_id")), "kind": str(item.get("kind"))}
        if isinstance(item.get("title"), str) and item["title"].strip():
            entry["title"] = item["title"][:200]
        out.append(entry)
    return out


def _device_kind(manifest: Mapping[str, Any]) -> str:
    for resource in manifest.get("resources") or []:
        if isinstance(resource, Mapping) and isinstance(resource.get("kind"), str):
            return resource["kind"]
    return "device"


def _upstream(manifest: Mapping[str, Any], upstream: Mapping[str, Any] | None) -> dict[str, str] | None:
    if upstream is not None:
        repo, commit = upstream.get("repo"), upstream.get("commit")
    else:
        record = manifest.get("provenance") if isinstance(manifest.get("provenance"), Mapping) else {}
        repo, commit = record.get("source_repo"), record.get("source_commit")
    if isinstance(repo, str) and repo and isinstance(commit, str) and _COMMIT.match(commit):
        return {"repo": repo, "commit": commit}
    if upstream is not None:
        raise ReferenceFileError("upstream needs a repo and a full commit id")
    return None


def _measure(name: str, schema: Mapping[str, Any], resource_id: str) -> dict[str, Any]:
    entry: dict[str, Any] = {"name": name, "type": _json_type(schema)}
    items = _items(schema)
    if entry["type"] == "array" and items is not None:
        entry["items_type"] = _json_type(items)
    unit = _unit(schema)
    if unit:
        entry["unit"] = unit
    description = _describe(schema)
    if description:
        entry["description"] = description
    entry["resource"] = resource_id
    length = _length(schema)
    if length is not None:
        entry["length"] = length
    return entry


def _needs_no_input(input_schema: Any, limits: EffectiveLimits) -> bool:
    """True when a read can be served with an empty input (nothing required, nothing limited)."""
    required = input_schema.get("required") if isinstance(input_schema, Mapping) else None
    if isinstance(required, list) and required:
        return False
    if isinstance(input_schema, Mapping) and isinstance(input_schema.get("minProperties"), int) \
            and input_schema["minProperties"] > 0:
        return False
    return not limits.rules and not limits.cumulative


def _principal_output(schema: Any) -> Mapping[str, Any]:
    """The value a read returns: its first required output field with a unit, else the whole output."""
    if not isinstance(schema, Mapping):
        return {}
    properties = schema.get("properties") if isinstance(schema.get("properties"), Mapping) else {}
    for name in schema.get("required") if isinstance(schema.get("required"), list) else ():
        field = properties.get(name)
        if isinstance(field, Mapping) and _unit(field):
            return field
    return schema


def _read_measure(name: str, item: BindingLimits, binding: Mapping[str, Any]) -> dict[str, Any]:
    effective = item.effective
    value = _principal_output(effective.output_schema)
    entry: dict[str, Any] = {"name": name, "type": _json_type(value)}
    items = _items(value)
    if entry["type"] == "array" and items is not None:
        entry["items_type"] = _json_type(items)
    unit = _unit(value)
    if unit:
        entry["unit"] = unit
    description = _describe({}, binding.get("title") if effective.extension else (effective.summary or effective.title))
    if description:
        entry["description"] = description
    entry["resource"] = item.resource
    entry["cap_id"] = item.capability_id
    length = _length(value)
    if length is not None:
        entry["length"] = length
    inputs = _field_entries(effective.input_schema, item.limits)
    if inputs:
        # every one is optional (a measure needs no input), e.g. the probe or channel to read
        entry["inputs"] = inputs
    return entry


def _adjust(name: str, schema: Mapping[str, Any], resource_id: str, bound: BindingLimits, device_risk: str,
            operator_required: list[dict[str, Any]]) -> dict[str, Any]:
    rule = bound.limits.rules.get(name)
    entry: dict[str, Any] = {"name": name, "type": _json_type(schema)}
    items = _items(schema)
    if entry["type"] == "array" and items is not None:
        entry["items_type"] = _json_type(items)
    unit = _unit(schema)
    if unit:
        entry["unit"] = unit
    description = _describe(schema)
    if description:
        entry["description"] = description
    entry["resource"] = resource_id
    entry["risk"] = risk_at_least(device_risk, bound.effective.risk_floor)
    if isinstance(schema.get("enum"), list) and schema["enum"]:
        entry["enum"] = copy.deepcopy(schema["enum"])
    length = _length(schema)
    if length is not None:
        entry["length"] = length
    if rule is not None and rule.names is not None:
        entry["names"] = list(rule.names)
    limit = _limit_value(rule)
    if limit is not None:
        entry["limit"] = limit
    if rule is not None and rule.unset:
        operator_required.append(_operator_entry(name, None, rule))
    return entry


def _operator_entry(name: str, path: str | None, rule: EffectiveRule) -> dict[str, Any]:
    entry: dict[str, Any] = {"name": name}
    if path is not None:
        entry["path"] = path
    if rule.reason:
        entry["reason"] = rule.reason[:500]
    return entry


def _action(name: str, binding: Mapping[str, Any], item: BindingLimits, device_risk: str,
            operator_required: list[dict[str, Any]], catalog: Catalog) -> dict[str, Any]:
    effective = item.effective
    constraints = dict(effective.constraints)
    if isinstance(binding.get("constraints"), Mapping):
        constraints.update(binding["constraints"])
    entry: dict[str, Any] = {
        "name": name,
        "cap_id": item.capability_id,
        "verb": effective.verb,
        "status": effective.status if effective.status in ("stable", "experimental", "deprecated", "extension")
        else "stable",
        "resource": item.resource,
    }
    description = _describe({}, binding.get("title") if effective.extension else (effective.summary or effective.title),
                            limit=2000)
    if description:
        entry["description"] = description
    entry["inputs"] = _field_entries(effective.input_schema, item.limits)
    entry["outputs"] = _field_entries(effective.output_schema, None)
    entry["long_running"] = bool(constraints.get("long_running"))
    entry["cancellable"] = bool(constraints.get("cancellable"))
    entry["risk"] = risk_at_least(device_risk, effective.risk_floor)
    entry["requires_permit"] = bool(effective.requires_permit)
    if effective.inherited_input and not effective.extension:
        examples = [copy.deepcopy(example) for example in (catalog.get(item.capability_id) or {}).get("examples") or []
                    if isinstance(example, Mapping)]
        if examples:
            entry["examples"] = examples
    for path in item.limits.unset:
        operator_required.append(_operator_entry(name, path, item.limits.rules[path]))
    return entry


def _safety(manifest: Mapping[str, Any], safety: Mapping[str, Any], operator_required: list[dict[str, Any]],
            estop_native: Any = _UNSET) -> dict[str, Any]:
    estop_doc = safety.get("estop") if isinstance(safety.get("estop"), Mapping) else {}
    estop: dict[str, Any] = {"kind": estop_doc.get("kind", "software"), "latching": bool(estop_doc.get("latching"))}
    native = estop_native if estop_native is not _UNSET else estop_doc.get("native", _UNSET)
    if native is not _UNSET:
        if native is not None and not (isinstance(native, str) and native.strip()):
            raise ReferenceFileError(f"estop native must be the native stop's name or None, got {native!r}")
        estop["native"] = native
    if isinstance(estop_doc.get("physical_ref"), str) and estop_doc["physical_ref"]:
        estop["physical_ref"] = estop_doc["physical_ref"]
    if isinstance(estop_doc.get("latency_ms"), int) and not isinstance(estop_doc.get("latency_ms"), bool):
        estop["latency_ms"] = estop_doc["latency_ms"]
    # Declared recovery after an e-stop (CORE-086, CORE-087); absent unless declared.
    if isinstance(estop_doc.get("reenable"), str) and estop_doc["reenable"]:
        estop["reenable"] = estop_doc["reenable"]
    if isinstance(estop_doc.get("terminal"), str) and estop_doc["terminal"].strip():
        estop["terminal"] = estop_doc["terminal"]
    # A sensed-confirmation stop of a simulated device (SAFE-049); absent unless declared.
    if isinstance(estop_doc.get("confirmation"), Mapping):
        estop["confirmation"] = copy.deepcopy(dict(estop_doc["confirmation"]))
    safe_doc = safety.get("safe_state") if isinstance(safety.get("safe_state"), Mapping) else {}
    out: dict[str, Any] = {
        "estop": estop,
        "safe_state": {
            "description": str(safe_doc.get("description") or "not declared"),
            "achieved_by": [str(item) for item in safe_doc.get("achieved_by") or []],
        },
    }
    interlocks = []
    for item in safety.get("interlocks") or []:
        if not isinstance(item, Mapping) or not item.get("id"):
            continue
        interlocks.append({key: copy.deepcopy(item[key]) for key in
                           ("id", "description", "required_for", "source", "reset_exempt") if key in item})
    out["interlocks"] = interlocks
    watchdog = manifest.get("watchdog_ms")
    if isinstance(watchdog, int) and not isinstance(watchdog, bool) and watchdog >= 1:
        out["watchdog_ms"] = watchdog
    out["operator_required"] = operator_required
    out["not_certified"] = True
    return out


# ---------------------------------------------------------------------------
# output forms
# ---------------------------------------------------------------------------


def validate(reference: Mapping[str, Any]) -> list[str]:
    """Validation errors of ``reference`` against ``reference.schema.json`` (empty when valid)."""
    from .schema import default_store

    return default_store().validate(reference, "reference.schema.json")


def dump(reference: Mapping[str, Any]) -> bytes:
    """The canonical (JCS) bytes of a reference file: identical inputs give identical bytes."""
    return canonical.jcs(reference)


def _cell(value: Any) -> str:
    if value is None or value == "":
        return ""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    return " ".join(text.split()).replace("|", "\\|")


def _format_limit(limit: Any, unit: str | None = None) -> str:
    if limit is None:
        return ""
    if limit == "operator_required":
        return "operator required (not set)"
    if not isinstance(limit, Mapping):
        return _cell(limit)
    suffix = f" {limit.get('unit') or unit}" if (limit.get("unit") or unit) else ""
    parts = []
    low, high = limit.get("min"), limit.get("max")
    if low is not None and high is not None:
        parts.append(f"{_cell(low)} .. {_cell(high)}{suffix}")
    elif low is not None:
        parts.append(f">= {_cell(low)}{suffix}")
    elif high is not None:
        parts.append(f"<= {_cell(high)}{suffix}")
    if limit.get("allowed") is not None:
        parts.append("one of " + ", ".join(_cell(item) for item in limit["allowed"]))
    if limit.get("names"):
        parts.append("elements " + ", ".join(_cell(item) for item in limit["names"]))
    origin = limit.get("source")
    if origin:
        parts.append(f"({origin}{': ' + _cell(limit['ref']) if limit.get('ref') else ''})")
    elif parts:
        # an unsourced bound (one derived from a fake backend's action space) says where it came from instead
        parts.append(f"(no source{': ' + _cell(limit['ref']) if limit.get('ref') else ''})")
    return "; ".join(parts)


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def render_markdown(reference: Mapping[str, Any]) -> str:
    """The human-readable ``REFERENCE.md`` of a rendered reference file (deterministic)."""
    device = reference.get("device") or {}
    lines = [f"# {_cell(device.get('name'))}", ""]
    lines.append(
        f"Device `{device.get('id')}`, kind `{device.get('kind')}`, mode **{device.get('mode')}**, "
        f"risk **{device.get('risk')}**."
    )
    if device.get("vendor") or device.get("model"):
        lines.append(f"Vendor {_cell(device.get('vendor')) or 'unknown'}, model {_cell(device.get('model')) or 'unknown'}.")
    if device.get("upstream"):
        lines.append(f"Upstream {device['upstream']['repo']} at `{device['upstream']['commit']}`.")
    if device.get("models"):
        lines.append("Stands in for: " + ", ".join(f"`{item}`" for item in device["models"]) + ".")
    if device.get("resources"):
        lines.append("Resources (one device, one e-stop latch): " + ", ".join(
            f"`{item.get('id')}` (kind `{item.get('kind')}`)" for item in device["resources"]) + ".")
    lines += ["", "Generated by OpenMHS from the driver, the capability catalogue and the operator overlay; "
              "do not edit. The limits below are the ones the runtime enforces.", ""]

    lines += ["## Measures", ""]
    measures = reference.get("measures") or []
    if measures:
        lines += _table(["Name", "Type", "Unit", "Resource", "Served by", "Optional inputs", "Description"], [
            [f"`{item['name']}`", _cell(item.get("type")), _cell(item.get("unit")), _cell(item.get("resource")),
             f"`{item['cap_id']}`" if item.get("cap_id") else "mhs.resource.read",
             ", ".join(f"`{field['name']}`" for field in item.get("inputs") or []), _cell(item.get("description"))]
            for item in measures])
    else:
        lines.append("None.")
    lines += ["", "## Adjusts", ""]
    adjusts = reference.get("adjusts") or []
    if adjusts:
        lines.append("Written with `mhs.resource.write` (class `cap.device.configure.v1`); every adjust is also readable.")
        lines.append("")
        lines += _table(["Name", "Type", "Unit", "Limit", "Risk", "Resource", "Description"], [
            [f"`{item['name']}`", _cell(item.get("type")), _cell(item.get("unit")),
             _format_limit(item.get("limit"), item.get("unit")), _cell(item.get("risk")), _cell(item.get("resource")),
             _cell(item.get("description"))]
            for item in adjusts])
    else:
        lines.append("None.")
    lines += ["", "## Actions", ""]
    actions = reference.get("actions") or []
    if not actions:
        lines.append("None.")
    for action in actions:
        flags = [action.get("verb") or "invoke", f"risk {action.get('risk')}"]
        if action.get("status") and action["status"] != "stable":
            flags.append(action["status"])
        if action.get("requires_permit"):
            flags.append("permit required")
        if action.get("long_running"):
            flags.append("long-running")
        if action.get("cancellable"):
            flags.append("cancellable")
        lines += [f"### `{action['name']}`", "", f"`{action['cap_id']}` on `{action.get('resource')}`: "
                  + ", ".join(flags) + "."]
        if action.get("description"):
            lines += ["", _cell(action["description"])]
        lines += ["", "Inputs:", ""]
        if action.get("inputs"):
            lines += _table(["Field", "Type", "Unit", "Required", "Limit", "Description"], [
                [f"`{item['name']}`", _cell(item.get("type")), _cell(item.get("unit")),
                 "yes" if item.get("required") else "", _format_limit(item.get("limit"), item.get("unit")),
                 _cell(item.get("description"))]
                for item in action["inputs"]])
        else:
            lines.append("None.")
        lines += ["", "Outputs:", ""]
        if action.get("outputs"):
            lines += _table(["Field", "Type", "Unit", "Description"], [
                [f"`{item['name']}`", _cell(item.get("type")), _cell(item.get("unit")), _cell(item.get("description"))]
                for item in action["outputs"]])
        else:
            lines.append("None.")
        lines.append("")
    safety = reference.get("safety") or {}
    estop = safety.get("estop") or {}
    lines += ["## Safety", ""]
    estop_text = f"E-stop: {estop.get('kind')}, {'latching' if estop.get('latching') else 'not latching'}"
    if estop.get("native"):
        estop_text += f", native stop `{estop['native']}`"
    elif "native" in estop:
        estop_text += ", no native stop (software latch only)"
    if estop.get("latency_ms") is not None:
        estop_text += f", latency {estop['latency_ms']} ms"
    if estop.get("physical_ref"):
        estop_text += f"; physical stop: {_cell(estop['physical_ref'])}"
    lines.append(f"- {estop_text}.")
    if estop.get("reenable"):
        lines.append(f"- Re-enable after a reset: `{estop['reenable']}` (the reset never runs it; it is refused "
                     "while the e-stop is latched).")
    if estop.get("terminal"):
        statement = _cell(estop["terminal"]).rstrip()
        statement += "" if statement.endswith(".") else "."
        lines.append(f"- Terminal e-stop: {statement} Every reset after an e-stop on the same endpoint is refused "
                     "(`terminal_estop`).")
    if isinstance(estop.get("confirmation"), Mapping):
        lines += _confirmation_lines(estop["confirmation"])
    safe_state = safety.get("safe_state") or {}
    achieved = ", ".join(f"`{item}`" for item in safe_state.get("achieved_by") or []) or "nothing declared"
    lines.append(f"- Safe state: {_cell(safe_state.get('description'))} (achieved by {achieved}).")
    for interlock in safety.get("interlocks") or []:
        gated = ", ".join(f"`{item}`" for item in interlock.get("required_for") or []) or "informative only"
        text = f"- Interlock `{interlock['id']}`"
        if interlock.get("description"):
            text += f": {_cell(interlock['description'])}"
        lines.append(f"{text} (gates {gated}).")
    if safety.get("watchdog_ms") is not None:
        lines.append(f"- Watchdog: {safety['watchdog_ms']} ms without a command returns the device to its safe state.")
    unset = safety.get("operator_required") or []
    if unset:
        names = ", ".join(f"`{item['name']}{'.' + item['path'] if item.get('path') else ''}`" for item in unset)
        lines.append(f"- Operator-required limits not yet set: {names}. Hardware use is refused "
                     "(MHS.SAFETY.LIMITS_UNSET) until site-limits.json supplies them.")
    lines.append("- OpenMHS is not a safety certification and not a safety-rated channel; the physical e-stop "
                 "stays authoritative.")
    bridges = safety.get("operator_bridges") or []
    if bridges:
        # E3: endpoints that exist on the ROS graph only while the operator runs these bridges.
        lines += ["", "## Operator must run", "",
                  "The package never starts these bridges; the endpoints they carry exist only while the operator "
                  "runs them (ros_gz `parameter_bridge`, one argument each, with no other options):", ""]
        lines += _table(["Argument", "Cited", "Note"], [
            [f"`{_cell(item.get('args'))}`", _cell(item.get("ref")), _cell(item.get("description"))]
            for item in bridges])
    lines += ["", "## Facts", ""]
    facts = reference.get("facts") or []
    if facts:
        for fact in facts:
            cite = fact.get("source")
            if fact.get("ref"):
                cite += f": {_cell(fact['ref'])}"
            reviewed = f"; reviewed by {_cell(fact['reviewed_by'])}" if fact.get("reviewed_by") else ""
            lines.append(f"- {_cell(fact.get('text'))} ({cite}{reviewed})")
    else:
        lines.append("None.")
    if reference.get("tags"):
        lines += ["", "Tags: " + ", ".join(reference["tags"]) + "."]
    overlay = reference.get("overlay")
    if isinstance(overlay, Mapping):
        lines += ["", f"Operator overlay {_cell(overlay.get('file')) or ''} `{overlay.get('digest')}`".replace("  ", " ")
                  + (":" if overlay.get("narrowed") else " (narrowed nothing).")]
        lines.extend(f"- {_cell(item)}" for item in overlay.get("narrowed") or [])
    provenance = reference.get("provenance")
    if isinstance(provenance, Mapping):
        lines += ["", f"Provenance: generated by {_cell(provenance.get('generated_by'))} "
                  f"{_cell(provenance.get('sdk_version'))}; catalogue `{provenance.get('catalogue_digest')}`; "
                  f"manifest `{provenance.get('manifest_digest')}`."]
    return "\n".join(lines).rstrip() + "\n"


def _confirmation_lines(confirmation: Mapping[str, Any]) -> list[str]:
    """REFERENCE.md lines of a sensed-confirmation stop (SAFE-049): request, sources, predicate and bounds."""
    request = ", ".join(f"`{item.get('native')}` ({item.get('kind')})" for item in confirmation.get("request") or [])
    sources = ", ".join(f"`{item.get('topic')}` ({_cell(item.get('type'))}, stamp `{item.get('stamp_path')}`)"
                        for item in confirmation.get("sources") or [])
    lines = [f"- Sensed-confirmation stop (simulated devices only; SAFE-049): the request steps {request} prove "
             f"nothing by themselves. The e-stop is achieved only when every source ({sources}) delivers "
             f"{confirmation.get('consecutive')} fresh samples, on subscriptions opened after the request, that "
             f"satisfy every term below within {confirmation.get('confirm_within_ms')} ms of the first transmission; "
             "otherwise it fails `MHS.SAFETY.SAFE_STATE_UNREACHED`, the latch is kept and the background retry sends "
             "the request again. A reset re-confirms without a request.",
             f"- Sensed state: {_cell(confirmation.get('description'))}."]
    for term in confirmation.get("predicate") or []:
        lines.append(f"- Predicate: `{_cell(term)}`.")
    for item in confirmation.get("thresholds") or []:
        unit = f" {item['unit']}" if item.get("unit") else ""
        if item.get("operator_required"):
            text = f"operator_required ({_cell(item['operator_required'])})"
        elif item.get("source") == "operator":
            text = f"{item.get('value')}{unit}, operator value"
        else:
            text = f"{item.get('value')}{unit}, {item.get('source')} `{_cell(item.get('ref'))}`"
        lines.append(f"- Threshold `{item.get('name')}` ({item.get('bound')}): {text}.")
    for item in confirmation.get("sources") or []:
        history = item.get("history")
        if not isinstance(history, Mapping):
            continue  # a ROS 1 source declares no history: every ROS 1 stamp sample is discarded
        if history.get("operator_required"):
            text = f"operator_required ({_cell(history['operator_required'])})"
        else:
            depth = f", depth {history.get('depth')}" if history.get("depth") is not None else ""
            origin = ("operator value" if history.get("source") == "operator"
                      else f"cited `{_cell(history.get('ref'))}`")
            text = f"{history.get('durability')}{depth}, {origin}"
        lines.append(f"- Publisher history of `{item.get('topic')}` (a new subscription's replay, discarded before "
                     f"any sample counts): {text}.")
    lines.append(f"- Client execution bounds (no source: a wrong value can only withhold the confirmation): "
                 f"consecutive {confirmation.get('consecutive')}, min_span_ms {confirmation.get('min_span_ms')}, "
                 f"max_gap_ms {confirmation.get('max_gap_ms')}, confirm_within_ms "
                 f"{confirmation.get('confirm_within_ms')}.")
    return lines

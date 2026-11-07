#!/usr/bin/env python3
"""Validate the OpenMHS registry (stdlib only; ``--no-corpus`` needs nothing outside ``MHS/``).

Checks
------
1. Records ``repos/**/*.json``: ``MHS/schema/registry-record.schema.json`` with
   the embedded validator below and the SDK validator (``mhs.schema``); the
   MHS-007 common envelope (``id == package_id``; ``registry_id`` equal to
   ``mhs._ids.REGISTRY_ID``, the deployment-local publisher policy,
   overridable with ``$MHS_REGISTRY_ID``); capability referents; known pure
   simulators; empty modes for tier D/X; hardware first, also for a record
   whose triage evidence (``x-vendor.triage.hardware_transport``) shows code
   that drives hardware outside a simulator family; no
   "no physical effect" text for a record with a hardware mode; no Chinese text
   and no ``[zh]`` marker outside ``x-vendor``; ``adapter.manifest_ref`` null or
   an existing file; quarantine honoured; ``source.commit`` equal to the
   corpus lock; the device plan (``x-vendor.device_plan``): CAP-017 risk floor,
   KIND_MISMATCH and mode fit through ``mhs.catalog.resolve_binding``, and
   ``models`` links to the hardware device.
2. Task cards ``tasks/**/*.json``: one per record,
   ``schema/taskcard.schema.json`` (SDK validator: ``contains`` and
   ``uniqueItems``), agreement with the record, the catalogue risk floor of the
   candidate classes, stable catalogue classes only, ``blocked_on`` for a
   blocked helper, the dispatch rule, ``models`` only on simulator cards and
   ``needs_recon: model`` on a MuJoCo card without one;
   ``tasks/pilot-candidates.json``.
3. Overrides ``overrides/*.json``: ``schema/overrides.schema.json``, the
   triage override rules, targets that are registry records, and records
   whose modes are an override's reviewed ``modes`` (which never drop a
   hardware mode the scan found, ``check_mode_override``).
4. Overlays ``MHS/drivers/<track>/<owner>__<repo>/``: a card for every
   package; ``driver.lock.json``, ``RESULT.json``, ``check-report.json`` and
   ``reference.json`` valid against their schemas; the lock and task pinned to
   the card's commit; the record's evidence equal to the overlay's; a
   ``RESULT.json`` pass whose ``gate.digest`` is the digest of the present
   ``check-report.json`` without its clock (``mhs.driver.check.stable_digest``,
   or the report's own ``report_digest``; a package without that generated
   file has nothing to compare); reference devices at or above the catalogue
   floor of their actions and kind-matched.
5. ``corpus.lock.jsonl``: one sorted line per record with the same identity.
6. Family recipes: one per family present, exactly one launch line
   ``mhs serve <driver-dir>``, a ``bridge_status`` line, resolvable capability
   ids, no ``python -m mhs.bridge`` launch commands.
7. Aggregates (``index.json``, ``index.jsonl``, ``records.csv``; git-ignored):
   when present they must equal ``build_index.render`` of the records.
8. Corpus (skipped with ``--no-corpus``): one record per clone directory,
   every card entry symbol's ``file:line`` exists in its clone, the line of
   an ``ast`` entry symbol defines its class, and every card model's
   ``file:line`` holds its ``<mujoco>`` element.

Usage:  python3 MHS/registry/validate.py [--no-corpus] [--quiet] [--allow-stale-cards]
Exit code 0 iff everything validates. ``--allow-stale-cards`` (used by pull-request CI) turns the two comparisons of
check 4 that a registry rebuild settles (the card's ``package_status`` and the record's evidence against the package) into
a warning: a driver pull request changes nothing outside ``MHS/drivers/``, so the registry is rebuilt after the merge.
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.abspath(os.path.join(HERE, "..", ".."))
SCHEMA_DIR = os.path.join(WORKSPACE, "MHS", "schema")
REGISTRY_SCHEMA_DIR = os.path.join(HERE, "schema")
SDK_SRC = os.path.join(WORKSPACE, "MHS", "sdk", "src")
CAPABILITIES_JSON = os.path.join(WORKSPACE, "MHS", "spec", "capabilities.json")
if SDK_SRC not in sys.path:
    sys.path.insert(0, SDK_SRC)
from mhs import _ids  # noqa: E402

REGISTRY_ID = _ids.REGISTRY_ID
#: Deployment-local publication policy for *this* corpus.  Mirrors that publish
#: the same validator may set ``$MHS_REGISTRY_ID`` to their own identifier; the
#: shared ``registry-record.schema.json`` deliberately does not hard-code it.
REGISTRY_ID_ENV = "MHS_REGISTRY_ID"
CAPABILITY_ID_RE = re.compile(r"^(?:x-)?cap\.[a-z0-9_.-]+\.v[0-9]+$")
CAPABILITY_SCAN_RE = re.compile(r"(?<![A-Za-z0-9_.-])((?:x-)?cap\.[a-z0-9_.-]+\.v[0-9]+)")
CJK_RE = re.compile(r"[\u3000-\u303f\u3400-\u9fff\uf900-\ufaff\uff00-\uffef]")
NO_PHYSICAL_EFFECT = re.compile(r"no physical effect", re.IGNORECASE)
LAUNCH_LINE = "mhs serve <driver-dir>"

sys.path.insert(0, HERE)
import family_data as FD  # noqa: E402  (same-directory data module; stdlib only)

DATE_TIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")


# ---------------------------------------------------------------------------
# Minimal JSON-Schema (2020-12 subset) validator
# ---------------------------------------------------------------------------
class SchemaStore:
    def __init__(self, schema_dir: str):
        self.dir = schema_dir
        self.schemas = {}
        for path in sorted(glob.glob(os.path.join(schema_dir, "*.schema.json"))):
            with open(path, "r", encoding="utf-8") as fh:
                self.schemas[os.path.basename(path)] = json.load(fh)

    def resolve_ref(self, ref: str, base_file: str):
        if ref.startswith("#"):
            target_file, pointer = base_file, ref[1:]
        elif "#" in ref:
            target_file, pointer = ref.split("#", 1)
        else:
            target_file, pointer = ref, ""
        if target_file not in self.schemas:
            raise KeyError(f"unknown schema ref: {ref}")
        node = self.schemas[target_file]
        for token in [t for t in pointer.split("/") if t]:
            token = token.replace("~1", "/").replace("~0", "~")
            node = node[token]
        return node, target_file


class Validator:
    def __init__(self, store: SchemaStore):
        self.store = store

    def validate(self, instance, schema, base_file, path="$"):
        errors = []
        self._v(instance, schema, base_file, path, errors)
        return errors

    # -- helpers -----------------------------------------------------------
    def _v(self, instance, schema, base_file, path, errors):
        if not isinstance(schema, dict):
            return
        if "$ref" in schema:
            target, target_file = self.store.resolve_ref(schema["$ref"], base_file)
            self._v(instance, target, target_file, path, errors)
            # a $ref can be combined with other keywords in draft 2020-12
            rest = {k: v for k, v in schema.items() if k != "$ref"}
            if rest:
                self._v(instance, rest, base_file, path, errors)
            return

        if "allOf" in schema:
            for sub in schema["allOf"]:
                self._v(instance, sub, base_file, path, errors)

        if "if" in schema:
            cond_errors = []
            self._v(instance, schema["if"], base_file, path, cond_errors)
            if not cond_errors:
                if "then" in schema:
                    self._v(instance, schema["then"], base_file, path, errors)
            elif "else" in schema:
                self._v(instance, schema["else"], base_file, path, errors)

        if "not" in schema:
            not_errors = []
            self._v(instance, schema["not"], base_file, path, not_errors)
            if not not_errors:
                errors.append(f"{path}: must NOT validate against 'not' schema")

        # type
        if "type" in schema:
            types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            if not any(self._is_type(instance, t) for t in types):
                errors.append(f"{path}: expected type {schema['type']}, got {type(instance).__name__}")
                return

        if "const" in schema and instance != schema["const"]:
            errors.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")
        if "enum" in schema and instance not in schema["enum"]:
            errors.append(f"{path}: value {instance!r} not in enum {schema['enum']}")

        if isinstance(instance, str):
            if "pattern" in schema:
                try:
                    if not re.search(schema["pattern"], instance):
                        errors.append(f"{path}: {instance!r} does not match pattern {schema['pattern']!r}")
                except re.error as exc:
                    errors.append(f"{path}: bad schema pattern {schema['pattern']!r}: {exc}")
            if "minLength" in schema and len(instance) < schema["minLength"]:
                errors.append(f"{path}: shorter than minLength {schema['minLength']}")
            if "maxLength" in schema and len(instance) > schema["maxLength"]:
                errors.append(f"{path}: longer than maxLength {schema['maxLength']} ({len(instance)})")
            if schema.get("format") == "date-time" and not DATE_TIME_RE.match(instance):
                errors.append(f"{path}: {instance!r} is not an RFC 3339 date-time")

        if isinstance(instance, (int, float)) and not isinstance(instance, bool):
            if "minimum" in schema and instance < schema["minimum"]:
                errors.append(f"{path}: {instance} < minimum {schema['minimum']}")
            if "maximum" in schema and instance > schema["maximum"]:
                errors.append(f"{path}: {instance} > maximum {schema['maximum']}")
            if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
                errors.append(f"{path}: {instance} <= exclusiveMinimum")

        if isinstance(instance, list):
            if "minItems" in schema and len(instance) < schema["minItems"]:
                errors.append(f"{path}: fewer than minItems {schema['minItems']} ({len(instance)})")
            if "maxItems" in schema and len(instance) > schema["maxItems"]:
                errors.append(f"{path}: more than maxItems {schema['maxItems']} ({len(instance)})")
            items = schema.get("items")
            if isinstance(items, dict):
                for idx, item in enumerate(instance):
                    self._v(item, items, base_file, f"{path}[{idx}]", errors)

        if isinstance(instance, dict):
            required = schema.get("required", [])
            for key in required:
                if key not in instance:
                    errors.append(f"{path}: missing required property {key!r}")
            props = schema.get("properties", {})
            for key, value in instance.items():
                if key in props:
                    self._v(value, props[key], base_file, f"{path}.{key}", errors)
                else:
                    add = schema.get("additionalProperties", True)
                    if add is False:
                        errors.append(f"{path}: additional property {key!r} not allowed")
                    elif isinstance(add, dict):
                        self._v(value, add, base_file, f"{path}.{key}", errors)

    @staticmethod
    def _is_type(instance, type_name: str) -> bool:
        if type_name == "object":
            return isinstance(instance, dict)
        if type_name == "array":
            return isinstance(instance, list)
        if type_name == "string":
            return isinstance(instance, str)
        if type_name == "integer":
            return isinstance(instance, int) and not isinstance(instance, bool)
        if type_name == "number":
            return isinstance(instance, (int, float)) and not isinstance(instance, bool)
        if type_name == "boolean":
            return isinstance(instance, bool)
        if type_name == "null":
            return instance is None
        return True


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_core_capabilities():
    """Return {capability_id: class document} from MHS/spec/capabilities.json."""
    if not os.path.exists(CAPABILITIES_JSON):
        raise SystemExit(f"missing core capability catalogue: {CAPABILITIES_JSON}")
    doc = load_json(CAPABILITIES_JSON)
    return {entry["capability_id"]: entry for entry in doc.get("capabilities", [])
            if entry.get("capability_id")}


def declared_extension_ids(doc):
    """x-cap ids explicitly declared by a record in x-vendor.capability_extensions."""
    declared = set()
    vendor = (doc or {}).get("x-vendor")
    if not isinstance(vendor, dict):
        return declared
    ext = vendor.get("capability_extensions")
    if isinstance(ext, dict):
        for key, value in ext.items():
            if isinstance(key, str) and key.startswith("x-cap."):
                declared.add(key)
            if isinstance(value, str) and value.startswith("x-cap."):
                declared.add(value)
            elif isinstance(value, dict) and str(value.get("capability_id", "")).startswith("x-cap."):
                declared.add(value["capability_id"])
    elif isinstance(ext, list):
        for value in ext:
            if isinstance(value, str) and value.startswith("x-cap."):
                declared.add(value)
            elif isinstance(value, dict) and str(value.get("capability_id", "")).startswith("x-cap."):
                declared.add(value["capability_id"])
    return declared


def check_capability_refs(cap_ids, core_caps, declared_extensions, where):
    """Resolve core capability ids; allow only explicitly declared x-cap ids.

    Returns (errors, extension_ids). Extension use is reported separately so a
    validator run makes x-cap usage visible instead of silently accepting it.
    """
    errors = []
    extensions = []
    for cap in cap_ids or []:
        if not isinstance(cap, str):
            continue
        if cap.startswith("x-cap."):
            if cap not in declared_extensions:
                errors.append(f"{where}: extension capability {cap!r} is not explicitly "
                              "declared by the device/adapter (x-vendor.capability_extensions)")
            else:
                extensions.append(cap)
        elif cap.startswith("cap."):
            if cap not in core_caps:
                errors.append(f"{where}: unknown core capability {cap!r} "
                              "(not in MHS/spec/capabilities.json)")
    return errors, extensions


def expected_registry_id():
    """Return the publisher this deployment expects for its own corpus.

    ``MHS_REGISTRY_ID`` lets a mirror validate its own records without editing
    the shared schema or pretending its records were published by the reference
    registry.  The default remains the reference registry for this checkout.
    """
    value = os.environ.get(REGISTRY_ID_ENV, "").strip()
    return value or REGISTRY_ID


def strings_outside_vendor(doc, path="$"):
    """Yield (path, string) for every string value outside ``x-vendor`` / ``x-*`` members."""
    if isinstance(doc, dict):
        for key, value in doc.items():
            if isinstance(key, str) and key.startswith("x-"):
                continue
            yield from strings_outside_vendor(value, f"{path}.{key}")
    elif isinstance(doc, list):
        for idx, value in enumerate(doc):
            yield from strings_outside_vendor(value, f"{path}[{idx}]")
    elif isinstance(doc, str):
        yield path, doc


def check_english(doc, where="record"):
    """No CJK text and no ``[zh]`` marker outside x-vendor (REGQ-07, OSS-13)."""
    errors = []
    for path, text in strings_outside_vendor(doc):
        if CJK_RE.search(text) or "[zh]" in text:
            errors.append(f"{where} {path}: non-English text outside x-vendor ({text[:40]!r})")
    return errors


#: families whose driver drives a simulator (build_registry.SIMULATOR_FAMILIES)
SIMULATOR_FAMILIES = frozenset({"gymnasium", "mujoco"})


def check_hardware_evidence(doc):
    """A record whose code drives real hardware is never simulated only.

    ``x-vendor.triage.hardware_transport`` names the class that uses a hardware
    transport.  A device driver, driver pack or twin candidate outside the
    simulator families, and a recon (``untriaged``) card of any role, must then
    list hardware first; a decided simulation environment and a gymnasium or
    MuJoCo twin are exempt (their driver drives the simulator).
    """
    modes = doc.get("modes") or []
    triage = (doc.get("x-vendor") or {}).get("triage") or {}
    evidence = triage.get("hardware_transport")
    if not evidence or not modes or (doc.get("x-vendor") or {}).get("classification", {}).get("mode_override"):
        return []
    integration = doc.get("integration") or {}
    role, strategy = integration.get("role"), integration.get("strategy")
    applies = (role in ("device-driver", "driver-pack")
               or (role == "twin-candidate" and triage.get("family") not in SIMULATOR_FAMILIES)
               or strategy == "untriaged")
    if applies and modes[0] != "hardware":
        return [f"modes: {evidence}, so the record must list hardware first (modes {modes}, role {role}, "
                f"family {triage.get('family')})"]
    return []


def check_mode_override(doc):
    """A reviewed ``modes`` override (rule ``override:modes``) records the scanned modes and never drops hardware."""
    meta = ((doc.get("x-vendor") or {}).get("classification") or {}).get("mode_override") or {}
    if meta.get("rule") != "override:modes":
        return []
    scanned = meta.get("scanned_modes")
    modes = doc.get("modes") or []
    if not isinstance(scanned, list):
        return ["modes: a reviewed modes override must record the scanned modes (mode_override.scanned_modes)"]
    if list(meta.get("modes") or []) != list(modes):
        return [f"modes: the record's modes {modes} are not the reviewed override's {meta.get('modes')}"]
    if "hardware" in scanned and "hardware" not in modes:
        return [f"modes: the reviewed override {modes} drops the hardware mode the scan found ({scanned})"]
    return []


def check_served_mode(doc):
    """A reviewed ``served_mode`` (rule ``override:served-mode``) serves simulated and keeps hardware first."""
    meta = ((doc.get("x-vendor") or {}).get("classification") or {}).get("served_mode") or {}
    if not meta:
        return []
    modes = doc.get("modes") or []
    if meta.get("rule") != "override:served-mode" or meta.get("mode") != "simulated":
        return [f"served_mode: only rule override:served-mode with mode simulated is recognized (got {meta!r})"]
    if not modes or modes[0] != "hardware" or "simulated" not in modes or "hardware" not in modes:
        return [f"served_mode: simulated service keeps hardware in modes and hardware first ({modes})"]
    return []


def check_record_semantics(doc, core_caps, registry_id=None, lock=None):
    """Envelope, referents, modes, English, quarantine and device-plan checks for a package record.

    ``registry_id`` is the deployment-local expected publisher (default:
    :func:`expected_registry_id`); ``lock`` is the record's corpus-lock line.
    Returns (errors, extension_ids).
    """
    errors = []
    expected_registry = registry_id or expected_registry_id()
    package_id = doc.get("package_id")
    if doc.get("record_type") == "package":
        if doc.get("id") != package_id:
            errors.append(f"envelope: id {doc.get('id')!r} != package_id {package_id!r} "
                          "(MHS-007 §4.1: package records reuse package_id as id)")
        if doc.get("registry_id") != expected_registry:
            errors.append(f"envelope: registry_id {doc.get('registry_id')!r} != "
                          f"{expected_registry!r} (deployment-local publisher policy; "
                          "the shared schema accepts any conforming registry identifier)")
    declared = declared_extension_ids(doc)
    cap_errors, extensions = check_capability_refs(
        doc.get("capabilities_offered"), core_caps, declared, "capabilities_offered")
    errors.extend(cap_errors)
    modes = doc.get("modes") or []
    spec = FD.pure_simulator(package_id)
    if spec is not None and doc.get("tier") not in ("D", "X"):
        if "hardware" in modes:
            errors.append(f"modes: known pure simulator {package_id!r} must not advertise "
                          f"hardware (source-backed modes {spec['modes']}; {spec['evidence']})")
        if set(modes) != set(spec["modes"]):
            errors.append(f"modes: {package_id!r} has {modes}, source-backed override is "
                          f"{spec['modes']} ({spec['evidence']})")
    if doc.get("tier") in ("D", "X") and modes:
        errors.append(f"modes: tier {doc['tier']} must have empty modes, has {modes}")
    errors.extend(check_mode_override(doc))
    errors.extend(check_served_mode(doc))
    if "hardware" in modes and modes[0] != "hardware":
        errors.append(f"modes: hardware must come first in a dual-mode record ({modes})")
    errors.extend(check_hardware_evidence(doc))
    if "hardware" in modes and any(NO_PHYSICAL_EFFECT.search(t) for _p, t in strings_outside_vendor(doc)):
        errors.append("a record whose modes include hardware must not say 'no physical effect'")
    if "hardware" in modes and any(NO_PHYSICAL_EFFECT.search(json.dumps(d)) for d in
                                   ((doc.get("x-vendor") or {}).get("device_plan") or [])):
        errors.append("the device plan of a hardware record must not say 'no physical effect'")
    errors.extend(check_english(doc))
    adapter = doc.get("adapter") or {}
    ref = adapter.get("manifest_ref")
    if ref is not None and not os.path.isfile(os.path.join(HERE, ref)):
        errors.append(f"adapter.manifest_ref {ref!r} names no file")
    integration = doc.get("integration") or {}
    strategy = integration.get("strategy")
    if doc.get("quarantine"):
        if strategy != "skip":
            errors.append(f"quarantine: a quarantined record must be skipped, strategy is {strategy!r}")
        if "QUARANTINE" not in (doc.get("blocked_on") or []):
            errors.append("quarantine: blocked_on lacks QUARANTINE")
    if doc.get("variant_of") and strategy != "skip":
        errors.append(f"variant_of {doc['variant_of']!r} on a {strategy!r} record (a duplicate is skipped)")
    if lock is not None:
        commit = (doc.get("source") or {}).get("commit")
        if commit != lock.get("commit"):
            errors.append(f"source.commit {commit!r} != corpus lock {lock.get('commit')!r}")
        if doc.get("local_path") != lock.get("local_path"):
            errors.append(f"local_path {doc.get('local_path')!r} != corpus lock {lock.get('local_path')!r}")
    errors.extend(check_device_plan(doc))
    return errors, extensions


def _catalog():
    import catalog_view as CV  # noqa: E402  (mhs.catalog over the checkout's capabilities.json)
    return CV


EMPTY_STATE = {"type": "object", "properties": {}}


def check_bindings(caps, kind, mode, risk, where):
    """CAP-017 risk floor, KIND_MISMATCH and mode fit of capability ids bound on one resource kind."""
    CV = _catalog()
    from mhs import catalog as C  # noqa: E402
    errors = []
    for cap in caps:
        if not isinstance(cap, str) or not cap.startswith("cap."):
            continue
        try:
            eff = CV.catalog().resolve_binding(cap, None, None, kind, mode, state_schema=EMPTY_STATE)
        except C.CatalogError as exc:
            errors.append(f"{where}: {cap}: {exc}")
            continue
        if not eff.kind_ok:
            errors.append(f"{where}: KIND_MISMATCH: {cap} cannot bind a {kind!r} resource")
        if not eff.mode_ok:
            errors.append(f"{where}: {cap} is not available in mode {mode!r}")
        if CV.RISK_ORDER.index(risk) < CV.RISK_ORDER.index(eff.risk_floor):
            errors.append(f"{where}: CAP-017: risk {risk} below the {cap} floor {eff.risk_floor}")
    return errors


def check_device_plan(doc):
    """Planned devices: hardware first, ``models`` links, CAP-017 and KIND_MISMATCH per resource."""
    plan = (doc.get("x-vendor") or {}).get("device_plan")
    if plan is None:
        return []
    errors = []
    modes = doc.get("modes") or []
    if [d.get("mode") for d in plan] != list(modes):
        errors.append(f"device_plan: modes {[d.get('mode') for d in plan]} != record modes {modes}")
    hardware = [d.get("device_id") for d in plan if d.get("mode") == "hardware"]
    for device in plan:
        risk = device.get("risk_floor") or "R0"
        if device.get("mode") in ("simulated", "replay") and hardware and device.get("models") != hardware:
            errors.append(f"device_plan {device.get('device_id')}: models {device.get('models')} must name {hardware}")
        if device.get("mode") == "hardware" and _catalog().RISK_ORDER.index(risk) >= 1 and not device.get("estop_required"):
            errors.append(f"device_plan {device.get('device_id')}: hardware at {risk} needs estop_required")
        caps = [c for r in device.get("resources") or [] for c in r.get("capabilities") or []]
        if risk != _catalog().risk_floor(caps):
            errors.append(f"device_plan {device.get('device_id')}: risk_floor {risk} != catalogue floor "
                          f"{_catalog().risk_floor(caps)}")
        for resource in device.get("resources") or []:
            errors.extend(check_bindings(resource.get("capabilities") or [], resource.get("kind"), device.get("mode"),
                                         risk, f"device_plan {device.get('device_id')}"))
    return errors


def check_manifest_semantics(doc, core_caps):
    """Capability-referent checks for an adapter manifest (devices[].capabilities).

    A device manifest that binds an x-cap class is itself the explicit adapter
    declaration required by CAP-038; such use is reported as extension usage.
    """
    cap_ids = []
    for device in doc.get("devices", []) or []:
        if not isinstance(device, dict):
            continue
        for cap in device.get("capabilities", []) or []:
            if isinstance(cap, dict) and isinstance(cap.get("capability_id"), str):
                cap_ids.append(cap["capability_id"])
    declared = {cap for cap in cap_ids if cap.startswith("x-cap.")}
    declared |= declared_extension_ids(doc)
    return check_capability_refs(cap_ids, core_caps, declared, "devices[].capabilities")


def check_recipe_semantics(text, core_caps):
    """Find capability ids in a family recipe; unknown core ids are errors."""
    ids = sorted(set(CAPABILITY_SCAN_RE.findall(text or "")))
    declared = {cap for cap in ids if cap.startswith("x-cap.")}
    return check_capability_refs(ids, core_caps, declared, "recipe")


def check_recipe_layout(text):
    """One launch line, a bridge_status line and no launch command that names a bridge module."""
    errors = []
    launches = [line for line in text.splitlines() if line.strip().startswith(("mhs serve", "python -m mhs.bridge",
                                                                              "python3 -m mhs.bridge"))]
    if launches != [LAUNCH_LINE]:
        errors.append(f"recipe launch lines {launches} != [{LAUNCH_LINE!r}]")
    if not re.search(r"^- bridge_status: `(?:available|planned|none)`", text, re.MULTILINE):
        errors.append("recipe has no bridge_status line")
    if re.search(r"mhs\.bridge\.[a-z_]+:main|--adapter mhs/mhs-adapter\.json", text):
        errors.append("recipe names a bridge-module launcher")
    return errors


# ---------------------------------------------------------------------------
# task cards
# ---------------------------------------------------------------------------
CARD_RECORD_FIELDS = (("decision", ("integration", "strategy")), ("role", ("integration", "role")),
                      ("reason_code", ("integration", "reason_code")), ("blocked_on", ("blocked_on",)),
                      ("wave", ("wave",)), ("rank", ("rank",)), ("quarantine", ("quarantine",)),
                      ("variant_of", ("variant_of",)), ("local_path", ("local_path",)))


def _get(doc, path):
    for key in path:
        doc = (doc or {}).get(key) if isinstance(doc, dict) else None
    return doc


# --- w1-waiting-routing (2026-11-05): Sila2Driver proves one source profile ---
def sila2_pin():
    """(driver_dir, commit) of the one card Sila2Driver can serve today, or None when the SDK is not importable.

    G7 proves exactly one PhenixImager feature at one commit (mhs/driver/sila2_check.py), while triage rule 9 tags every
    repository that imports a SiLA library as family sila2: any other such card needs a reviewed override.
    """
    try:
        from mhs.driver.sila2_check import SOURCE_COMMIT
        import triage as T
    except Exception:  # pragma: no cover - the SDK and triage are part of MHS/
        return None
    exemplar = T.FAMILIES["sila2"].exemplar
    return (exemplar, SOURCE_COMMIT) if exemplar else None
# --- end w1-waiting-routing ---


def check_card(card, record):
    """A card agrees with its record, its risk floor with the catalogue, and the dispatch rule holds."""
    CV = _catalog()
    errors = []
    pid = card.get("package_id")
    if record is None:
        return [f"card {pid}: no registry record"]
    for field, path in CARD_RECORD_FIELDS:
        if card.get(field) != _get(record, path):
            errors.append(f"card {pid}: {field} {card.get(field)!r} != record {_get(record, path)!r}")
    up = card.get("upstream") or {}
    if up.get("commit") != (record.get("source") or {}).get("commit"):
        errors.append(f"card {pid}: upstream.commit != record source.commit")
    if up.get("license_spdx") != record.get("license_spdx") or up.get("license_class") != record.get("license_class"):
        errors.append(f"card {pid}: licence differs from the record")
    track, owner, repo = str(record.get("local_path")).split("/")[:3]
    want_dir = f"MHS/drivers/{track}/{owner}__{repo}"
    if card.get("driver_dir") != want_dir:
        errors.append(f"card {pid}: driver_dir {card.get('driver_dir')!r} != {want_dir!r}")
    if card.get("acceptance") != f"python3 -m mhs.driver check {want_dir} --backend fake":
        errors.append(f"card {pid}: acceptance command does not name its driver_dir")
    classes = (card.get("hints") or {}).get("candidate_classes") or []
    floor = CV.risk_floor(classes)
    if (card.get("safety") or {}).get("risk_floor") != floor:
        errors.append(f"card {pid}: risk_floor {(card.get('safety') or {}).get('risk_floor')!r} != catalogue floor {floor}")
    for cap in classes:
        entry = CV.catalog().get(cap)
        if entry is None:
            errors.append(f"card {pid}: unknown candidate class {cap}")
        elif entry.get("status") == "deprecated":
            errors.append(f"card {pid}: deprecated candidate class {cap}")
    if record.get("tier") not in ("D", "X") and list(classes) != list(record.get("capabilities_offered") or []):
        errors.append(f"card {pid}: candidate classes != record capabilities_offered")
    decision = card.get("decision")
    if decision in ("direct-driver", "family-config") and card.get("helper_status") == "blocked" and not card.get("blocked_on"):
        errors.append(f"card {pid}: blocked helper without blocked_on")
    if decision in ("direct-driver", "family-config") and card.get("family") == "sila2":  # w1-waiting-routing
        pin = sila2_pin()
        if pin is not None and (card.get("driver_dir"), (card.get("upstream") or {}).get("commit")) != pin:
            errors.append(f"card {pid}: family sila2 is dispatchable only for {pin[0]} at {pin[1][:12]} (the one "
                          "source profile Sila2Driver proves); route this card by a reviewed override")
    if card.get("quarantine") and (decision in ("direct-driver", "family-config") or "QUARANTINE" not in card.get("blocked_on", [])):
        errors.append(f"card {pid}: quarantined card is dispatchable or lacks QUARANTINE")
    if card.get("package_status") not in ("none", "in_progress", "pass", "blocked", "skip-proposed"):
        errors.append(f"card {pid}: package_status {card.get('package_status')!r} missing or unknown")
    empty = not card.get("entry_symbols") and not classes and (
        card.get("family") == "python-object"
        or (card.get("family") in ("serial", "scpi") and not (card.get("install") or {}).get("commands")))
    recon = "recon:entry_symbol" in card.get("blocked_on", [])
    if decision in ("direct-driver", "family-config") and empty != recon:
        errors.append(f"card {pid}: recon:entry_symbol in blocked_on is {recon}, but the card is "
                      f"{'' if empty else 'not '}missing its entry symbol and candidate classes")
    models = card.get("models") or []
    if models and not (card.get("family") in ("mujoco", "gymnasium") or card.get("role") in ("sim-env", "twin-candidate")):
        errors.append(f"card {pid}: models on a card that is not a simulator")
    if (decision in ("direct-driver", "family-config") and card.get("family") == "mujoco" and not models
            and "model" not in (card.get("needs_recon") or [])):
        errors.append(f"card {pid}: MuJoCo card without a main model and without needs_recon model")
    errors.extend(check_english(card, f"card {pid}"))
    return errors


def check_pilot(doc, cards):
    errors = []
    candidates = doc.get("candidates") or []
    if doc.get("count") != len(candidates) or len(candidates) != 40:
        errors.append(f"pilot-candidates: {len(candidates)} candidates (count {doc.get('count')}), expected 40")
    ids = [c.get("package_id") for c in candidates]
    for pid in ("gh.tiagocoutinho/julabo", "gh.thinksrs/srsinst.sr860", "gh.xarm-developer/xarm-python-sdk",
                "gh.farama-foundation/gymnasium"):
        if pid not in ids:
            errors.append(f"pilot-candidates: exemplar {pid} missing")
    for item in candidates:
        card = cards.get(item.get("package_id"))
        if card is None:
            errors.append(f"pilot-candidates: {item.get('package_id')} has no card")
            continue
        if item.get("task") != card:
            errors.append(f"pilot-candidates: {item.get('package_id')} task differs from its card")
        if card["helper_status"] != "available" or card["blocked_on"] or card["quarantine"]:
            errors.append(f"pilot-candidates: {card['package_id']} is not dispatchable with an available helper")
        if card["wave"] not in (0, 1):
            errors.append(f"pilot-candidates: {card['package_id']} is wave {card['wave']}, not 0 or 1")
    return errors


# ---------------------------------------------------------------------------
# overlays, lock, aggregates, corpus
# ---------------------------------------------------------------------------
def gate_digest_problem(digest, report):
    """Why RESULT.json's ``gate.digest`` does not describe ``check-report.json`` (``None`` when it does).

    Every gate run rewrites ``check-report.json`` with a new ``generated_at``,
    so its ``report_digest`` changes with each run of an unchanged package.
    ``gate.digest`` therefore is the report's timestamp-free digest
    (``mhs.driver.check.stable_digest``, printed by the gate after a pass),
    and the report's own ``report_digest`` is accepted too (a hand-recorded
    or hardware report).  A package without a ``check-report.json`` (it is
    generated, not committed) has nothing to compare and is not an error.
    """
    stable = None
    try:
        from mhs.driver.check import stable_digest
        stable = stable_digest(report)
    except Exception:  # noqa: BLE001 - a malformed report is reported by its schema check
        pass
    if digest in (report.get("report_digest"), stable):
        return None
    return (f"RESULT.json gate digest {digest} != check-report.json (report_digest {report.get('report_digest')}, "
            f"digest without the clock {stable}): the gate result changed since RESULT.json was written; re-run "
            "the gate and record the digest it prints")


def check_overlays(overlays, cards, records_by_key, sdk_store, stale=None):
    """Driver packages are read-only inputs; their files must be valid and pinned to the card.

    A card whose ``package_status`` or a record whose evidence does not show the outcome of its package yet is an error,
    unless ``stale`` is a list: then those messages are appended to it instead. A driver pull request cannot touch the
    registry, so CI passes a list and a maintainer rebuilds the registry after the merge."""
    import overlays as OV  # noqa: E402
    errors = []
    pending = errors if stale is None else stale
    schemas = {"driver.lock.json": "driver-lock.schema.json", "RESULT.json": "driver-result.schema.json",
               "check-report.json": "check-report.schema.json", "reference.json": "reference.schema.json",
               "task.json": "taskcard.schema.json"}
    for key, overlay in sorted(overlays.items()):
        record = records_by_key.get(key)
        where = f"overlay MHS/drivers/{key}"
        if record is None:
            errors.append(f"{where}: no registry record (no task card)")
            continue
        card = cards.get(record["package_id"])
        errors.extend(f"{where}: {e}" for e in overlay.errors)
        for name, schema in schemas.items():
            doc = overlay.docs.get(name)
            if doc is not None and sdk_store is not None:
                errors.extend(f"{where}/{name}: {e}" for e in sdk_store.validate(doc, schema)[:5])
        commit = (card or {}).get("upstream", {}).get("commit")
        lock = overlay.lock
        if isinstance(lock, dict):
            if lock.get("package_id") != record["package_id"]:
                errors.append(f"{where}/driver.lock.json: package_id {lock.get('package_id')!r} != {record['package_id']!r}")
            if (lock.get("upstream") or {}).get("commit") != commit:
                errors.append(f"{where}/driver.lock.json: commit != card upstream.commit {commit!r}")
            if "companions" in lock or "companions" in (card or {}):
                expected = [{"package_id": item.get("package_id"), "commit": item.get("commit"),
                             **({"lock": item.get("lock")} if "lock" in item else {})}
                            for item in (card or {}).get("companions") or []]
                if lock.get("companions") != expected:
                    errors.append(f"{where}/driver.lock.json: companions != the card's companions {expected!r}")
        task = overlay.task
        if isinstance(task, dict):
            for field in ("package_id", "decision", "driver_dir"):
                if task.get(field) != (card or {}).get(field):
                    errors.append(f"{where}/task.json: {field} {task.get(field)!r} != card {(card or {}).get(field)!r}")
            if (task.get("upstream") or {}).get("commit") != commit:
                errors.append(f"{where}/task.json: upstream.commit != card")
            # Companion sources (user decision 2026-11-05) come only from a reviewed override through the card
            # (check_companions); the gate reads them from task.json, so it must carry exactly the card's, or none
            # when the card has none.
            have = ("companions" in task, task.get("companions"))
            want = ("companions" in (card or {}), (card or {}).get("companions"))
            if have != want:
                errors.append(f"{where}/task.json: companions differ from the card's (task.json is never edited; "
                              "companions come only from a reviewed override through the registry card)")
        result, report = overlay.result, overlay.report
        if overlay.passed() and isinstance(report, dict):
            problem = gate_digest_problem(result["gate"]["digest"], report)
            if problem:
                errors.append(f"{where}: {problem}")
        if card is not None and card.get("package_status") != overlay.package_status():
            pending.append(f"{where}: card package_status {card.get('package_status')!r} != overlay "
                           f"{overlay.package_status()!r}")
        state = overlay.evidence_state()
        if state and (record.get("evidence") or {}).get("state") != state:
            pending.append(f"{where}: record evidence {(record.get('evidence') or {}).get('state')!r} != overlay {state!r}")
        reference = overlay.reference
        if isinstance(reference, dict):
            device = reference.get("device") or {}
            # A composed device (package composition) lists its resources; each action binds its own resource's
            # kind.  Without that list every action binds device.kind, exactly as before.
            listed = [item for item in device.get("resources") or [] if isinstance(item, dict)]
            kinds = {item.get("id"): item.get("kind") for item in listed}
            if listed:
                # The list must describe this device: the main resource first (device.kind), each id once, and every
                # entry of the reference on a listed resource.  A hand-edited list cannot widen a binding.
                ids = [item.get("id") for item in listed]
                if listed[0].get("kind") != device.get("kind"):
                    errors.append(f"{where}/reference.json: device.resources[0].kind {listed[0].get('kind')!r} is "
                                  f"not device.kind {device.get('kind')!r}")
                if len(set(ids)) != len(ids):
                    errors.append(f"{where}/reference.json: device.resources ids are not unique: {ids}")
                for group in ("actions", "measures", "adjusts"):
                    for entry in reference.get(group) or []:
                        if isinstance(entry, dict) and entry.get("resource") not in ids:
                            errors.append(f"{where}/reference.json: {group} entry {entry.get('name')!r} names "
                                          f"resource {entry.get('resource')!r}, which device.resources does not list")
            by_kind: dict = {}
            for a in reference.get("actions") or []:
                if isinstance(a, dict):
                    by_kind.setdefault(kinds.get(a.get("resource"), device.get("kind")), []).append(a.get("cap_id"))
            for kind, caps in (by_kind.items() if by_kind else [(device.get("kind"), [])]):
                errors.extend(check_bindings(caps, kind, device.get("mode"), device.get("risk") or "R0",
                                             f"{where}/reference.json"))
    return errors


def check_companions(overrides, cards, by_pid, locks, workspace):
    """Companion sources (user decision 2026-11-05): a card carries ``companions`` only as its reviewed override
    declares them (resolved with the corpus lock's local_path and repo_url and the companion record's licence), and
    each override's companions meet the corpus rules (``triage.companion_problems``; with ``workspace``, the corpus
    present, also each clone's HEAD and every version-evidence range).

    A companion with ``lock`` (a clone fetched under work/companions, DESIGN-2) is resolved against
    work/companions/LOCK.json with the corpus (``workspace``); without it (``--no-corpus``, an export, where LOCK.json
    does not travel) only the card's own shape is checked (:func:`lock_shape_problems`)."""
    import triage as T  # noqa: E402
    errors = []
    companion_lock = None
    if workspace is not None and any(T.COMPANION_LOCK_KEY in entry for item in overrides.values()
                                     for entry in item.get("companions") or []):
        companion_lock, problem = T.read_companion_lock(workspace)
        if problem:
            errors.append(f"overrides: {problem}")
    for pid, card in sorted(cards.items(), key=lambda kv: str(kv[0])):
        declared = list((overrides.get(pid) or {}).get("companions") or [])
        if "companions" in card and not declared:
            errors.append(f"card {pid}: companions without a reviewed override that declares them")
        if not declared:
            continue
        if workspace is None and any(T.COMPANION_LOCK_KEY in entry for entry in declared):
            # Shape only: the corpus rules of the other entries need no workspace, the lock entries need LOCK.json.
            problems = T.companion_problems(pid, [entry for entry in declared if T.COMPANION_LOCK_KEY not in entry],
                                            by_pid, locks, None)
            problems += lock_shape_problems(pid, declared, card)
            errors.extend(f"override {problem}" for problem in problems)
            continue
        problems = T.companion_problems(pid, declared, by_pid, locks, workspace, companion_lock)
        errors.extend(f"override {problem}" for problem in problems)
        if problems:
            continue
        want = []
        for entry in declared:
            if T.COMPANION_LOCK_KEY in entry:
                line = companion_lock[entry[T.COMPANION_LOCK_KEY]]
                spdx, note = T.lock_licence(line.get("licence"))
                head = {key: entry[key] for key in T.COMPANION_KEYS}
                if entry.get(T.COMPANION_HARDWARE_STOP_KEY) is True:
                    head["hardware_stop"] = True
                want.append({**head, "lock": entry[T.COMPANION_LOCK_KEY],
                             "ref": line.get("ref"), "local_path": line.get("path"), "repo_url": line.get("repo_url"),
                             "license_spdx": spdx, **({"licence_note": note} if note else {})})
                continue
            line = locks.get(entry["package_id"]) or {}
            companion = by_pid.get(entry["package_id"]) or {}
            want.append({**{key: entry[key] for key in T.COMPANION_KEYS}, "local_path": line.get("local_path"),
                         "repo_url": line.get("repo_url") or companion.get("repo_url"),
                         "license_spdx": companion.get("license_spdx")})
        if card.get("companions") != want:
            errors.append(f"card {pid}: companions differ from the reviewed override resolved against the corpus lock "
                          "and work/companions/LOCK.json (rebuild the registry)")
    return errors


def lock_shape_problems(pid, declared, card):
    """Without LOCK.json (``--no-corpus``): each lock companion of the card repeats its override entry and is shaped as
    a fetched clone: a LOCK.json alias, a 40-hex commit, the local path ``work/companions/<owner>__<repo>@<commit12>``
    of its repo_url, a package_id that repo_url names, and the ref that the alias ends with."""
    import triage as T  # noqa: E402
    problems = []
    items = card.get("companions") if isinstance(card.get("companions"), list) else []
    for index, entry in enumerate(declared):
        if T.COMPANION_LOCK_KEY not in entry:
            continue
        item = items[index] if index < len(items) and isinstance(items[index], dict) else {}
        alias, lock = entry.get("alias"), entry[T.COMPANION_LOCK_KEY]
        if any(item.get(key) != entry.get(key) for key in T.COMPANION_KEYS + (T.COMPANION_LOCK_KEY,)):
            problems.append(f"{pid}: companion {alias!r}: the card entry differs from the override (rebuild the "
                            "registry)")
            continue
        if not T.COMPANION_LOCK_RE.match(str(lock)) or not T.COMMIT_RE.match(str(entry.get("commit"))):
            problems.append(f"{pid}: companion {alias!r}: lock or commit is malformed")
            continue
        if item.get("local_path") != T.lock_clone_path(item.get("repo_url"), entry.get("commit")):
            problems.append(f"{pid}: companion {alias!r}: local_path {item.get('local_path')!r} is not "
                            "work/companions/<owner>__<repo>@<first 12 hex of the commit> of its repo_url")
        if T.lock_package_id(item.get("repo_url")) != entry.get("package_id"):
            problems.append(f"{pid}: companion {alias!r}: repo_url {item.get('repo_url')!r} does not name "
                            f"{entry.get('package_id')!r}")
        # A hardware_stop companion (user decision 4, 2026-11-05) stores the full commit as ref. The lock alias
        # still ends in the first 12 hex digits. Every other lock companion keeps ref == the text after '@'.
        if entry.get(T.COMPANION_HARDWARE_STOP_KEY) is True:
            commit = str(entry.get("commit") or "")
            suffix = str(lock).partition("@")[2]
            if item.get("hardware_stop") is not True or item.get("ref") != commit or suffix != commit[:12]:
                problems.append(f"{pid}: companion {alias!r}: a hardware_stop companion's ref must be the full "
                                f"commit {commit!r} and its lock must end in the first 12 hex digits {commit[:12]!r} "
                                f"(card ref {item.get('ref')!r}, hardware_stop {item.get('hardware_stop')!r})")
        elif item.get("hardware_stop") not in (None, False):
            problems.append(f"{pid}: companion {alias!r}: the card sets hardware_stop but the override does not")
        elif item.get("ref") != str(lock).partition("@")[2]:
            problems.append(f"{pid}: companion {alias!r}: ref {item.get('ref')!r} is not the ref its lock names")
    return problems


def check_lock(lock_lines, records):
    errors = []
    ids = [line.get("package_id") for line in lock_lines]
    if ids != sorted(ids):
        errors.append("corpus.lock.jsonl is not sorted by package_id")
    by_id = {line.get("package_id"): line for line in lock_lines}
    for record in records:
        line = by_id.get(record["package_id"])
        if line is None:
            errors.append(f"corpus.lock.jsonl: no line for {record['package_id']}")
            continue
        commit = line.get("commit")
        if commit is not None and not re.match(r"^[0-9a-f]{40}([0-9a-f]{24})?$", str(commit)):
            errors.append(f"corpus.lock.jsonl: {record['package_id']}: bad commit {commit!r}")
        if not str(line.get("repo_url") or "").startswith("https://"):
            errors.append(f"corpus.lock.jsonl: {record['package_id']}: repo_url is not https")
    extra = sorted(set(by_id) - {r["package_id"] for r in records})
    if extra:
        errors.append(f"corpus.lock.jsonl: {len(extra)} line(s) without a record, e.g. {extra[:3]}")
    return errors


def check_aggregates(records, results):
    import build_index as BI  # noqa: E402
    texts = BI.render(records)
    present = [p for p in texts if os.path.exists(p)]
    if not present:
        results.append(("info", "aggregates index.json/index.jsonl/records.csv not present (git-ignored; "
                                "python3 MHS/registry/build_index.py builds them)"))
        return []
    errors = []
    for path, text in texts.items():
        if not os.path.exists(path):
            errors.append(f"{os.path.basename(path)} missing while other aggregates exist")
            continue
        with open(path, encoding="utf-8", newline="") as fh:
            if fh.read() != text:
                errors.append(f"{os.path.basename(path)} is stale (python3 MHS/registry/build_index.py)")
    if os.path.exists(BI.INDEX_JSON) and os.path.getsize(BI.INDEX_JSON) > BI.INDEX_BUDGET_BYTES:
        errors.append(f"index.json exceeds the {BI.INDEX_BUDGET_BYTES // (1024 * 1024)} MB budget")
    results.append(("info", f"aggregates checked: {', '.join(os.path.basename(p) for p in present)}"))
    return errors


def count_physical_dirs():
    n = 0
    for track in ("labs", "robots"):
        base = os.path.join(WORKSPACE, track)
        if not os.path.isdir(base):
            continue
        for owner in sorted(os.listdir(base)):
            owner_dir = os.path.join(base, owner)
            if not os.path.isdir(owner_dir):
                continue
            for repo in os.listdir(owner_dir):
                if os.path.isdir(os.path.join(owner_dir, repo)):
                    n += 1
    return n


def check_corpus(records, cards):
    """Clone count, every card entry symbol's file:line in its clone, and ``ast`` lines defining the class."""
    errors = []
    physical = count_physical_dirs()
    if physical != len(records):
        errors.append(f"repo records {len(records)} != physical clone directories {physical}")
    missing = 0
    for card in cards.values():
        for symbol in card.get("entry_symbols") or []:
            if str(symbol.get("symbol", "")).startswith("pyfile:") or " " in str(symbol.get("file", "")):
                # New source-only entries must agree with the exact pinned regular blob.
                from mhs.driver.source_selector import entry_shape, parse_selector
                from mhs.driver.source_surface import explicit_surface
                from mhs.driver.upstream import UpstreamTree
                from pathlib import Path

                if not entry_shape(symbol.get("symbol"), symbol.get("file"), symbol.get("line")):
                    errors.append(f"card {card['package_id']}: invalid source entry {symbol}")
                    continue
                selected = parse_selector(symbol["symbol"])
                if not selected.explicit:
                    selected = parse_selector(f"pyfile:{symbol['file']}#{selected.name}")
                tree = UpstreamTree(Path(WORKSPACE) / card["local_path"],
                                    (card.get("upstream") or {}).get("commit"))
                if not tree.pinned or selected is None:
                    errors.append(f"card {card['package_id']}: source entry has no available pinned source")
                    continue
                surface = explicit_surface(tree, selected)
                if not surface.found or surface.line != symbol["line"]:
                    errors.append(f"card {card['package_id']}: source entry does not match the pinned AST: "
                                  f"{surface.problems or f'actual line {surface.line}'}")
                continue
            path = os.path.join(WORKSPACE, card["local_path"], symbol["file"])
            try:
                with open(path, "rb") as fh:
                    lines = fh.read().splitlines()
            except OSError:
                errors.append(f"card {card['package_id']}: entry symbol file {symbol['file']} not in the clone")
                missing += 1
                continue
            if symbol["line"] > len(lines):
                errors.append(f"card {card['package_id']}: {symbol['file']}:{symbol['line']} beyond the file end")
            elif symbol.get("confidence") == "ast":
                name = symbol["symbol"].rsplit(":", 1)[-1].encode()
                if not re.search(rb"^\s*class\s+" + re.escape(name) + rb"\b", lines[symbol["line"] - 1]):
                    errors.append(f"card {card['package_id']}: {symbol['file']}:{symbol['line']} does not define "
                                  f"class {name.decode()} (confidence ast)")
            elif symbol.get("confidence") == "override":
                name = symbol["symbol"].rsplit(":", 1)[-1].split(".")[0].encode()
                if not re.search(rb"\b" + re.escape(name) + rb"\b", b" ".join(lines[symbol["line"] - 1:symbol["line"] + 2])):
                    errors.append(f"card {card['package_id']}: {name.decode()} is not defined at "
                                  f"{symbol['file']}:{symbol['line']} (confidence override)")
        for model in card.get("models") or []:
            path = os.path.join(WORKSPACE, card["local_path"], model["file"])
            try:
                with open(path, "rb") as fh:
                    lines = fh.read().splitlines()
            except OSError:
                errors.append(f"card {card['package_id']}: model {model['file']} not in the clone")
                continue
            if model["line"] > len(lines) or b"<mujoco" not in lines[model["line"] - 1]:
                errors.append(f"card {card['package_id']}: {model['file']}:{model['line']} is not its <mujoco> element")
    return errors


# ---------------------------------------------------------------------------
# optional SDK validator
# ---------------------------------------------------------------------------
def sdk_store():
    """The SDK validator (``contains``, ``uniqueItems`` and the full 2020-12 subset) over both schema roots."""
    try:
        from mhs.schema import SchemaStore as SdkStore  # type: ignore
    except Exception as exc:  # pragma: no cover - the SDK is part of MHS/
        return None, f"mhs.schema not importable ({exc}); card and overlay schemas are not checked"
    return SdkStore(SCHEMA_DIR, extra_roots=[REGISTRY_SCHEMA_DIR]), \
        "validating with the embedded validator and mhs.schema (cards, overrides and overlays with mhs.schema)"


def _jsonl(path):
    out = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            out = [json.loads(line) for line in fh if line.strip()]
    return out


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate the OpenMHS registry.")
    parser.add_argument("--no-corpus", action="store_true",
                        help="check only what MHS/ holds (no labs/, robots/, work/ or catalogue)")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--allow-stale-cards", action="store_true",
                        help="report a card or record that does not yet show the outcome of a driver package as a warning "
                             "(a driver pull request cannot touch the registry; rebuild it after the merge)")
    args = parser.parse_args(list(argv) if argv is not None else None)
    store = SchemaStore(SCHEMA_DIR)
    validator = Validator(store)
    sdk, sdk_note = sdk_store()
    core_caps = load_core_capabilities()
    publisher = expected_registry_id()
    results = [("info", f"schemas loaded: {len(store.schemas)} from MHS/schema"), ("info", sdk_note),
               ("info", f"deployment-local publisher policy: {publisher} (override with ${REGISTRY_ID_ENV})"),
               ("info", f"core capability catalogue: {len(core_caps)} classes"),
               ("info", "mode: --no-corpus (MHS/ only)" if args.no_corpus else "mode: with the corpus")]
    record_schema = store.schemas["registry-record.schema.json"]
    errors_by = OrderedDict((k, []) for k in ("records", "cards", "overrides", "overlays", "lock", "recipes",
                                               "aggregates", "corpus"))
    extension_usage = Counter()

    # ---- records ---------------------------------------------------------
    lock_lines = _jsonl(os.path.join(HERE, "corpus.lock.jsonl"))
    locks = {line.get("package_id"): line for line in lock_lines}
    records = []
    for path in sorted(glob.glob(os.path.join(HERE, "repos", "*", "*.json"))):
        rel = os.path.relpath(path, HERE)
        try:
            doc = load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors_by["records"].append(f"{rel}: unreadable: {exc}")
            continue
        records.append(doc)
        errs = validator.validate(doc, record_schema, "registry-record.schema.json")
        if sdk is not None:
            errs += [f"sdk: {e}" for e in sdk.validate(doc, "registry-record.schema.json")[:5]]
        sem, extensions = check_record_semantics(doc, core_caps, publisher, locks.get(doc.get("package_id")))
        extension_usage.update(extensions)
        errors_by["records"].extend(f"{rel}: {e}" for e in (errs + sem)[:6])
        stem = f"{doc.get('owner')}__{doc.get('repo')}.json"
        if os.path.basename(path) != stem or os.path.basename(os.path.dirname(path)) != doc.get("track"):
            errors_by["records"].append(f"{rel}: file name does not match track/owner__repo")
    results.append(("info", f"records validated: {len(records)}"))
    ids = Counter(r.get("package_id") for r in records)
    dupes = [pid for pid, n in ids.items() if n > 1]
    if dupes:
        errors_by["records"].append(f"duplicate package_id: {dupes[:5]}")
    by_pid = {r.get("package_id"): r for r in records}

    # ---- cards -------------------------------------------------------------
    cards = {}
    for path in sorted(glob.glob(os.path.join(HERE, "tasks", "*", "*.json"))):
        rel = os.path.relpath(path, HERE)
        card = load_json(path)
        cards[card.get("package_id")] = card
        if sdk is not None:
            errors_by["cards"].extend(f"{rel}: {e}" for e in sdk.validate(card, "taskcard.schema.json")[:5])
        errors_by["cards"].extend(f"{rel}: {e}" for e in check_card(card, by_pid.get(card.get("package_id")))[:6])
        record = by_pid.get(card.get("package_id")) or {}
        want = f"tasks/{record.get('track')}/{record.get('owner')}__{record.get('repo')}.json"
        if record and rel != want:
            errors_by["cards"].append(f"{rel}: card path != {want}")
    missing_cards = sorted(set(by_pid) - set(cards))
    if missing_cards:
        errors_by["cards"].append(f"{len(missing_cards)} record(s) without a card, e.g. {missing_cards[:3]}")
    pilot_path = os.path.join(HERE, "tasks", "pilot-candidates.json")
    if os.path.exists(pilot_path):
        errors_by["cards"].extend(check_pilot(load_json(pilot_path), cards))
    else:
        errors_by["cards"].append("tasks/pilot-candidates.json missing")
    import taskcards as TC  # noqa: E402  (the dispatch rule, package_status included)
    dispatchable = sum(1 for c in cards.values() if TC.dispatchable_now(c))
    results.append(("info", f"task cards validated: {len(cards)}; dispatchable now: {dispatchable}; quarantined: "
                            f"{sum(1 for c in cards.values() if c['quarantine'])}"))

    # ---- overrides --------------------------------------------------------
    import triage as T  # noqa: E402
    for path in sorted(glob.glob(os.path.join(HERE, "overrides", "*.json"))):
        rel = os.path.relpath(path, HERE)
        doc = load_json(path)
        if sdk is not None:
            errors_by["overrides"].extend(f"{rel}: {e}" for e in sdk.validate(doc, "overrides.schema.json")[:5])
        for item in doc.get("overrides") or []:
            try:
                T.check_override(item, rel)
            except T.OverrideError as exc:
                errors_by["overrides"].append(str(exc))
    try:
        overrides = T.load_overrides()
        errors_by["overrides"].extend(f"override for {pid}, which is not a registry record"
                                      for pid in T.unknown_overrides(overrides, by_pid))
        for pid, item in overrides.items():
            card = cards.get(pid)
            if card is not None and card["decision"] != item["strategy"]:
                errors_by["overrides"].append(f"override {pid}: card decision {card['decision']!r} != {item['strategy']!r}")
            record = by_pid.get(pid)
            if item.get("modes") and record is not None and list(record.get("modes") or []) != list(item["modes"]):
                errors_by["overrides"].append(f"override {pid}: record modes {record.get('modes')} != the reviewed "
                                              f"modes {item['modes']} (rebuild the registry)")
            if item.get("served_mode"):
                meta = (((record or {}).get("x-vendor") or {}).get("classification") or {}).get("served_mode") or {}
                if record is not None and (meta.get("rule") != "override:served-mode"
                                            or meta.get("mode") != item["served_mode"]):
                    errors_by["overrides"].append(
                        f"override {pid}: record served_mode {meta.get('mode')!r} is not the reviewed served_mode "
                        f"{item['served_mode']!r} (rebuild the registry)")
                expected = ((card or {}).get("safety") or {}).get("expected_mode") if card is not None else None
                if card is not None and expected != item["served_mode"]:
                    errors_by["overrides"].append(
                        f"override {pid}: card safety.expected_mode {expected!r} != served_mode "
                        f"{item['served_mode']!r} (the record keeps hardware; the card serves simulated)")
        errors_by["overrides"].extend(check_companions(overrides, cards, by_pid, locks,
                                                       None if args.no_corpus else WORKSPACE))
        results.append(("info", f"overrides: {len(overrides)}; with companion sources: "
                                f"{sum(1 for item in overrides.values() if item.get('companions'))}"))
    except T.OverrideError as exc:
        errors_by["overrides"].append(str(exc))

    # ---- overlays -----------------------------------------------------------
    import overlays as OV  # noqa: E402
    overlays = OV.load()
    by_key = {OV.key_for(r["local_path"]): r for r in records if r.get("local_path")}
    stale = [] if args.allow_stale_cards else None
    errors_by["overlays"].extend(check_overlays(overlays, cards, by_key, sdk, stale))
    results.append(("info", f"driver packages (overlays) checked: {len(overlays)}"))
    if stale:
        results.append(("warn", f"{len(stale)} card or record not rebuilt after a driver package yet "
                                "(python3 MHS/registry/build_registry.py --jobs 8, then "
                                "python3 MHS/handoff/tools/prepare.py --sync): " + "; ".join(stale[:3])))

    # ---- lock, recipes, aggregates ------------------------------------------
    errors_by["lock"].extend(check_lock(lock_lines, records))
    families = sorted({(r.get("families") or ["other"])[0] for r in records})
    for family in families:
        path = os.path.join(HERE, "families", f"{family}.md")
        if not os.path.exists(path):
            errors_by["recipes"].append(f"families/{family}.md missing")
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        sem, extensions = check_recipe_semantics(text, core_caps)
        extension_usage.update(extensions)
        errors_by["recipes"].extend(f"families/{family}.md: {e}" for e in sem + check_recipe_layout(text))
    extra = sorted(set(os.path.basename(p)[:-3] for p in glob.glob(os.path.join(HERE, "families", "*.md"))) - set(families))
    if extra:
        errors_by["recipes"].append(f"recipes for families no record has: {extra}")
    results.append(("info", f"family recipes: {len(families)}"))
    errors_by["aggregates"].extend(check_aggregates(records, results))

    # ---- corpus --------------------------------------------------------------
    if not args.no_corpus:
        errors_by["corpus"].extend(check_corpus(records, cards))
        results.append(("info", "corpus checks: clone count and entry-symbol file:line"))
    if extension_usage:
        results.append(("info", "extension capability usage: " + ", ".join(
            f"{cid} x{n}" for cid, n in sorted(extension_usage.items()))))

    # ---- report ----------------------------------------------------------
    print("== OpenMHS registry validation ==")
    for level, message in results:
        if not (args.quiet and level == "info"):
            print(f"[{level}] {message}")
    total = 0
    for area, errs in errors_by.items():
        total += len(errs)
        if errs:
            print(f"[error] {area}: {len(errs)} error(s)")
            for msg in errs[:12]:
                print(f"   - {msg}")
    print("-- summary --")
    for area, errs in errors_by.items():
        if area == "corpus" and args.no_corpus:
            print(f"{area:11} skipped (--no-corpus)")
        else:
            print(f"{area:11} {'ok' if not errs else f'{len(errs)} error(s)'}")
    print(f"errors:     {total}")
    print("RESULT:", "PASS" if not total else "FAIL")
    return 0 if not total else 1


if __name__ == "__main__":
    sys.exit(main())

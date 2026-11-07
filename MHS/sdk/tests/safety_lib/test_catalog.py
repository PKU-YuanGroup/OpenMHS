"""mhs.catalog: loading, lookup, binding resolution, drift and manifest limits."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

from mhs import canonical, catalog, limits
from mhs.catalog import CONFIGURE_CLASS, CatalogError, UnknownCapabilityError
from mhs.limits import LimitConfigError
from mhs.schema import validate

from ._support import CAPABILITIES, INVALID, VALID, expected_failures, load_json, pointer_tokens, valid_manifests

CAT = catalog.default_catalog()
SKELETON = {"type": "object", "description": "skeleton; to be defined by the adapter"}

#: SPEC-05: the 9 of 22 core-class bindings of the reference endpoints whose
#: input schema does not follow the class (names, required set or type).
KNOWN_DRIFT = {
    ("conveyor", "conveyor-workcell", "cap.actuation.valve.v1"),
    ("arm", "arm-2dof", "cap.motion.joint_position.v1"),
    ("arm", "arm-2dof", "cap.motion.cartesian_pose.v1"),
    ("lab", "liquid-handler", "cap.fluid.aspirate.v1"),
    ("lab", "liquid-handler", "cap.fluid.dispense.v1"),
    ("lab", "liquid-handler", "cap.fluid.transfer.v1"),
    ("lab", "liquid-handler", "cap.fluid.level.v1"),
    ("lab", "plate-reader", "cap.measure.spectrum.v1"),
    ("lab", "sample-mover", "cap.sample.move.v1"),
}
#: Drift the stricter resolver finds beyond SPEC-05: the conveyor's world.step
#: binding declares ticks minimum 0 where the class requires at least 1.
EXTRA_DRIFT = {("conveyor", "conveyor-workcell", "cap.world.step.v1")}
STRUCTURAL = {"property-not-in-class", "required-missing", "type-differs"}


def _kinds(effective):
    return sorted({item.kind for item in effective.drift})


_LOWER = ("minimum", "exclusiveMinimum", "minItems", "minLength", "minProperties")
_UPPER = ("maximum", "exclusiveMaximum", "maxItems", "maxLength", "maxProperties")


def _uncovered(effective, cls, path="input"):
    """Class constraints the effective schema does not state (empty when it is binding ∩ class)."""
    if not isinstance(cls, dict):
        return []
    if not isinstance(effective, dict):
        return [f"{path}: not a schema"]
    out = [f"{path}:{key}" for key in ("type", "x-mhs-unit", "enum", "const", "pattern")
           if key in cls and key not in effective]
    out += [f"{path}:{key}" for key in _LOWER if key in cls and not effective.get(key, float("-inf")) >= cls[key]]
    out += [f"{path}:{key}" for key in _UPPER if key in cls and not effective.get(key, float("inf")) <= cls[key]]
    if cls.get("additionalProperties") is False and effective.get("additionalProperties") is not False:
        out.append(f"{path}:additionalProperties")
    missing = set(cls.get("required") or []) - set(effective.get("required") or [])
    out += [f"{path}:required {name}" for name in sorted(missing)]
    out += [f"{path}.{name}: not accepted" for name in cls.get("required") or []
            if name not in (effective.get("properties") or {})]
    for name, sub in (cls.get("properties") or {}).items():
        if name in (effective.get("properties") or {}):
            out += _uncovered(effective["properties"][name], sub, f"{path}.{name}")
    if isinstance(cls.get("items"), dict):
        out += _uncovered(effective.get("items"), cls["items"], f"{path}[*]")
    return out


class LoadingTests(unittest.TestCase):
    def test_default_catalogue(self):
        document = load_json(CAPABILITIES)
        self.assertEqual(len(CAT), document["capability_count"])
        self.assertEqual(set(CAT.ids()), {entry["capability_id"] for entry in document["capabilities"]})
        self.assertEqual(CAT.digest, canonical.digest(document))
        self.assertEqual(catalog.get(CONFIGURE_CLASS)["resource_kinds"], ["*"])

    def test_packaged_copy_first_then_checkout(self):
        from mhs.schema import packaged_data_dir

        saved = os.environ.pop("MHS_SCHEMA_DIR", None)
        try:
            path = catalog.catalogue_path()
            data = packaged_data_dir()
            packaged = data / "spec" / "capabilities.json" if data is not None else None
            if packaged is not None and packaged.is_file() and packaged.read_bytes() == CAPABILITIES.read_bytes():
                self.assertEqual(path, packaged)
            else:
                self.assertEqual(path.resolve(), CAPABILITIES.resolve())
            self.assertEqual(path.read_bytes(), CAPABILITIES.read_bytes())
        finally:
            if saved is not None:
                os.environ["MHS_SCHEMA_DIR"] = saved

    def test_mhs_schema_dir_is_honoured(self):
        minimal = {"capabilities": [copy.deepcopy(CAT.get("cap.thermal.setpoint.v1"))], "spec_version": "0.9"}
        saved = os.environ.get("MHS_SCHEMA_DIR")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "schema").mkdir()
            (root / "spec").mkdir()
            (root / "spec" / "capabilities.json").write_text(json.dumps(minimal), encoding="utf-8")
            try:
                os.environ["MHS_SCHEMA_DIR"] = str(root / "schema")
                catalog.clear_default_catalog()
                self.assertEqual(catalog.catalogue_path(), root / "spec" / "capabilities.json")
                self.assertEqual(catalog.default_catalog().ids(), ("cap.thermal.setpoint.v1",))
                with self.assertRaises(UnknownCapabilityError):
                    catalog.resolve_binding("cap.motion.stop.v1")
            finally:
                if saved is None:
                    os.environ.pop("MHS_SCHEMA_DIR", None)
                else:
                    os.environ["MHS_SCHEMA_DIR"] = saved
                catalog.clear_default_catalog()
        self.assertEqual(len(catalog.default_catalog()), len(CAT))

    def test_bad_documents(self):
        with self.assertRaises(CatalogError):
            catalog.Catalog({"classes": []})
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "capabilities.json"
            broken.write_text("{", encoding="utf-8")
            with self.assertRaises(CatalogError):
                catalog.Catalog.load(broken)


class LookupTests(unittest.TestCase):
    def test_get_returns_a_copy(self):
        entry = catalog.get("cap.thermal.setpoint.v1")
        entry["verb"] = "read"
        self.assertEqual(catalog.get("cap.thermal.setpoint.v1")["verb"], "write")
        self.assertIsNone(catalog.get("cap.nope.v1"))
        self.assertEqual(catalog.get("cap.nope.v1", {}), {})

    def test_search(self):
        self.assertEqual(catalog.search("temperature setpoint")[0]["capability_id"], "cap.thermal.setpoint.v1")
        self.assertEqual(catalog.search("joint position")[0]["capability_id"], "cap.motion.joint_position.v1")
        self.assertEqual(catalog.search("cap.fluid.aspirate.v1")[0]["capability_id"], "cap.fluid.aspirate.v1")
        self.assertNotIn("cap.world.state.v1", [r["capability_id"] for r in catalog.search("world state", limit=50)])
        self.assertIn("cap.world.state.v1",
                      [r["capability_id"] for r in catalog.search("world state", limit=50, include_deprecated=True)])
        self.assertEqual(catalog.search("   "), [])
        self.assertLessEqual(len(catalog.search("set", limit=3)), 3)

    def test_is_extension(self):
        self.assertTrue(catalog.is_extension("x-cap.acme.heater_off.v1"))
        self.assertTrue(catalog.is_extension("cap.x.acme.heater_off.v1"))
        self.assertFalse(catalog.is_extension("cap.thermal.setpoint.v1"))
        self.assertFalse(catalog.is_extension(None))

    def test_digests(self):
        schema = {"type": "object", "properties": {"b": {"type": "number"}, "a": {"type": "string"}}}
        self.assertEqual(catalog.schema_digest(schema), "sha256:" + canonical.sha256_hex(canonical.jcs(schema)))
        self.assertEqual(CAT.class_digest("cap.thermal.setpoint.v1"),
                         catalog.schema_digest(catalog.get("cap.thermal.setpoint.v1")))
        manifest = load_json(VALID / "device.thermal-bath.json")
        binding = next(b for b in manifest["capabilities"] if b["capability_id"].startswith("x-cap."))
        self.assertEqual(catalog.extension_digest(binding["input_schema"], binding["output_schema"]),
                         binding["x-mhs-schema-digest"])

    def test_risk_at_least(self):
        self.assertEqual(catalog.risk_at_least("R1", "R3", "R0"), "R3")
        self.assertEqual(catalog.risk_at_least(), "R0")
        self.assertEqual(catalog.risk_at_least("R2", "bogus"), "R2")


class ResolveTests(unittest.TestCase):
    def test_every_class_resolves_and_its_examples_hold(self):
        state = {"type": "object", "properties": {"setpoint": {"type": "number"}}}
        for capability_id in CAT.ids():
            with self.subTest(capability_id=capability_id):
                effective = CAT.resolve_binding(capability_id, state_schema=state)
                self.assertEqual(effective.drift, ())
                self.assertEqual(effective.verb, catalog.get(capability_id)["verb"])
                compiled = limits.compile_limits(effective.input_schema, [("class", effective.class_limits)])
                for example in catalog.get(capability_id)["examples"]:
                    self.assertEqual(validate(example, effective.input_schema), [])
                    self.assertEqual(limits.check(example, compiled), [])

    def test_unknown_ids(self):
        for capability_id in ("cap.thermal.setpointt.v1", "cap.nope.v1"):
            with self.subTest(capability_id=capability_id):
                with self.assertRaises(UnknownCapabilityError):
                    catalog.resolve_binding(capability_id, {"type": "object", "properties": {"t": {"type": "number"}}})
        for capability_id in ("thermal.setpoint", "", None, "cap.Thermal.v1"):
            with self.assertRaises(CatalogError):
                catalog.resolve_binding(capability_id)

    def test_extension(self):
        schema_in = {"type": "object", "properties": {"on": {"type": "boolean"}}}
        effective = catalog.resolve_binding("x-cap.acme.heater.v1", schema_in, None, "thermal.zone", "hardware",
                                            binding_verb="write", binding_requires_permit=True)
        self.assertTrue(effective.extension)
        self.assertEqual(effective.status, "extension")
        self.assertEqual(effective.verb, "write")
        self.assertEqual(effective.input_schema, schema_in)
        self.assertTrue(effective.requires_permit)
        self.assertEqual(effective.drift, ())
        self.assertEqual(catalog.resolve_binding("cap.x.acme.heater.v1").verb, "invoke")

    def test_skeleton_binding_inherits_the_class(self):
        cls = catalog.get("cap.thermal.setpoint.v1")
        for skeleton in (None, SKELETON, {"type": "object", "properties": {}}):
            with self.subTest(skeleton=skeleton):
                effective = catalog.resolve_binding("cap.thermal.setpoint.v1", skeleton, skeleton)
                self.assertTrue(effective.inherited_input)
                self.assertTrue(effective.inherited_output)
                self.assertEqual(effective.input_schema, cls["input_schema"])
                self.assertEqual(effective.output_schema, cls["output_schema"])
        # a skeleton no longer accepts what the class rejects (SC-01: 9,109 registry skeletons)
        effective = catalog.resolve_binding("cap.thermal.setpoint.v1", SKELETON)
        self.assertNotEqual(validate({"target_temperature": "hot"}, effective.input_schema), [])

    def test_contract_comes_from_the_class(self):
        effective = catalog.resolve_binding("cap.optics.set_power.v1", None, None, "optics.laser", "simulated")
        cls = catalog.get("cap.optics.set_power.v1")
        self.assertEqual(effective.verb, cls["verb"])
        self.assertEqual(effective.risk_floor, cls["risk_class"])
        self.assertTrue(effective.requires_permit)
        self.assertEqual(effective.class_limits, cls["limits"])
        self.assertEqual(effective.status, cls["status"])
        self.assertEqual(effective.class_digest, catalog.schema_digest(cls))
        plain = catalog.resolve_binding("cap.thermal.setpoint.v1", binding_requires_permit=True)
        self.assertTrue(plain.requires_permit)
        self.assertFalse(catalog.resolve_binding("cap.thermal.setpoint.v1").requires_permit)

    def test_kind_and_mode(self):
        self.assertTrue(catalog.resolve_binding("cap.thermal.setpoint.v1", resource_kind="thermal.zone").kind_ok)
        self.assertFalse(catalog.resolve_binding("cap.thermal.setpoint.v1", resource_kind="robot.arm").kind_ok)
        self.assertTrue(catalog.resolve_binding("cap.thermal.setpoint.v1").kind_ok)
        state = {"type": "object", "properties": {"gain": {"type": "number"}}}
        for kind in ("robot.arm", "thermal.zone", "anything.at_all"):
            self.assertTrue(catalog.resolve_binding(CONFIGURE_CLASS, resource_kind=kind, state_schema=state).kind_ok)
        sim_only = next(cid for cid in CAT.ids() if "hardware" not in catalog.get(cid)["modes"])
        self.assertFalse(catalog.resolve_binding(sim_only, device_mode="hardware",
                                                 state_schema=state).mode_ok)
        self.assertTrue(catalog.resolve_binding(sim_only, device_mode="simulated", state_schema=state).mode_ok)
        local = catalog.Catalog({
            "capabilities": [{"capability_id": "cap.fluid.pump.v1", "verb": "invoke", "resource_kinds": ["fluid.pump"],
                              "input_schema": {"type": "object", "properties": {}}}],
            "resource_kinds": [{"kind": "fluid.pump", "see_also": ["actuation.pump"]}],
        })
        self.assertTrue(local.resolve_binding("cap.fluid.pump.v1", resource_kind="actuation.pump").kind_ok)
        self.assertFalse(local.resolve_binding("cap.fluid.pump.v1", resource_kind="fluid.valve").kind_ok)


class DriftTests(unittest.TestCase):
    CAP = "cap.thermal.setpoint.v1"

    def drift(self, schema, output=None, **options):
        return catalog.resolve_binding(self.CAP, schema, output, **options).drift

    def test_omitted_keywords_inherit_and_narrowing_is_fine(self):
        narrower = {"type": "object", "properties": {"target_temperature": {"type": "integer", "minimum": 0},
                                                      "wait": {"type": "boolean"}},
                    "required": ["target_temperature", "wait"], "additionalProperties": False}
        self.assertEqual(self.drift(narrower), ())
        self.assertEqual(self.drift({"properties": {"target_temperature": {"type": "number"}}}), ())

    def test_each_drift_kind(self):
        cases = [
            ({"properties": {"temp": {"type": "number"}}}, "property-not-in-class", "input.temp"),
            ({"properties": {"target_temperature": {"type": "string"}}}, "type-differs", "input.target_temperature"),
            ({"properties": {"target_temperature": {"type": "number", "x-mhs-unit": "K"}}}, "unit-differs",
             "input.target_temperature"),
            ({"properties": {"wait": {"type": "boolean"}}, "required": ["wait"]}, "required-missing", "input"),
            ({"properties": {"rate": {"type": "number", "minimum": -1}}}, "widens", "input.rate"),
            ({"properties": {"rate": {"type": "number"}}, "additionalProperties": True}, "widens", "input"),
        ]
        for schema, kind, path in cases:
            with self.subTest(kind=kind):
                drift = self.drift(dict(schema, type="object"))
                self.assertEqual([(item.kind, item.path) for item in drift], [(kind, path)])

    def test_enum_nested_and_output_drift(self):
        pose = {"type": "object", "properties": {
            "position": {"type": "object", "properties": {"x": {"type": "number", "x-mhs-unit": "m"}}},
            "frame": {"type": "string", "enum": ["base", "world"]}}}
        drift = catalog.resolve_binding("cap.motion.cartesian_pose.v1", pose).drift
        self.assertEqual(sorted((item.kind, item.path) for item in drift),
                         [("enum-not-subset", "input.frame"), ("unit-differs", "input.position.x")])
        output = {"type": "object", "properties": {"setpoint": {"type": "number"}, "extra": {"type": "string"}}}
        self.assertEqual([(item.kind, item.path) for item in self.drift(None, output)],
                         [("property-not-in-class", "output.extra")])
        wide_items = {"type": "object", "properties": {"joint_positions": {"type": "array", "maxItems": 128,
                                                                          "items": {"type": "number", "x-mhs-unit": "deg"}}}}
        drift = catalog.resolve_binding("cap.motion.joint_position.v1", wide_items).drift
        self.assertEqual(sorted((item.kind, item.path) for item in drift),
                         [("unit-differs", "input.joint_positions[*]"), ("widens", "input.joint_positions")])

    def test_verb_and_limit_drift(self):
        drift = self.drift(None, binding_verb="read",
                           binding_limits={"target_temperature": {"min": -100, "max": 100}})
        self.assertEqual(sorted((item.kind, item.path) for item in drift),
                         [("limit-widens", "limits.target_temperature.min"), ("verb-differs", "verb")])
        self.assertEqual(self.drift(None, binding_verb="write", binding_limits={"target_temperature": {"max": 100}}), ())

    def test_configure_class_derives_its_input_from_the_state(self):
        state = {"type": "object", "properties": {
            "temperature": {"type": "number", "x-mhs-unit": "Cel", "readOnly": True},
            "setpoint": {"type": "number", "x-mhs-unit": "Cel", "maximum": 200},
            "mode": {"type": "string", "enum": ["eco", "boost"]}}}
        effective = catalog.resolve_binding(CONFIGURE_CLASS, SKELETON, None, "thermal.zone", "hardware",
                                            state_schema=state)
        self.assertEqual(sorted(effective.input_schema["properties"]), ["mode", "setpoint"])
        self.assertIs(effective.input_schema["additionalProperties"], False)
        self.assertEqual(effective.input_schema["properties"]["setpoint"]["x-mhs-unit"], "Cel")
        self.assertEqual(validate({}, effective.input_schema) != [], True)
        self.assertEqual(validate({"setpoint": 37}, effective.input_schema), [])
        self.assertNotEqual(validate({"temperature": 37}, effective.input_schema), [])
        applied = effective.output_schema["properties"]["applied"]
        self.assertEqual(sorted(applied["properties"]), ["mode", "setpoint"])
        self.assertEqual(effective.verb, "write")
        self.assertEqual(effective.risk_floor, "R1")
        drift = catalog.resolve_binding(CONFIGURE_CLASS, {"type": "object", "properties": {"temperature": {"type": "number"}}},
                                        state_schema=state).drift
        self.assertEqual([(item.kind, item.path) for item in drift], [("property-not-in-class", "input.temperature")])
        with self.assertRaises(CatalogError):
            catalog.resolve_binding(CONFIGURE_CLASS)

    def test_reference_endpoints_drift_report(self):
        from mhs.reference import build_endpoint

        drifting, structural, total = set(), set(), 0
        for name in ("conveyor", "arm", "lab"):
            for device in build_endpoint(name).devices:
                kinds = {r["resource_id"]: r["kind"] for r in device["resources"]}
                for binding in device["capabilities"]:
                    capability_id = binding["capability_id"]
                    if catalog.is_extension(capability_id):
                        continue
                    total += 1
                    effective = catalog.resolve_binding(capability_id, binding.get("input_schema"),
                                                        binding.get("output_schema"), kinds[binding["resource"]],
                                                        device["mode"], binding_limits=binding.get("limits"))
                    key = (name, device["device_id"].rsplit("/", 1)[-1], capability_id)
                    if effective.drift:
                        drifting.add(key)
                    if STRUCTURAL & {item.kind for item in effective.drift}:
                        structural.add(key)
        self.assertEqual(total, 22)
        self.assertEqual(structural, KNOWN_DRIFT)
        # WP-06 06c raised the conveyor's ticks minimum to the class's 1 (EXTRA_DRIFT fixed).
        self.assertIn(drifting, (KNOWN_DRIFT, KNOWN_DRIFT | EXTRA_DRIFT))

    def test_new_drift_checks(self):
        joints = {"type": "object", "properties": {"joint_positions": {
            "type": "array", "x-mhs-unit": "deg", "items": {"type": "number"}}}}
        self.assertEqual([(item.kind, item.path) for item in
                          catalog.resolve_binding("cap.motion.joint_position.v1", joints).drift],
                         [("unit-differs", "input.joint_positions")])   # array-level unit vs the class item unit
        prefix = {"type": "object", "properties": {"joint_positions": {
            "type": "array", "prefixItems": [{"type": "number", "x-mhs-unit": "deg"}, {"type": "number"}]}}}
        self.assertEqual([(item.kind, item.path) for item in
                          catalog.resolve_binding("cap.motion.joint_position.v1", prefix).drift],
                         [("unit-differs", "input.joint_positions[0]")])
        closed = {"type": "object", "properties": {"rate": {"type": "number"}}, "additionalProperties": False}
        drift = self.drift(closed)
        self.assertEqual([(item.kind, item.path) for item in drift], [("required-missing", "input")])
        self.assertIn("closed", drift[0].message)
        local = catalog.Catalog({"capabilities": [{
            "capability_id": "cap.demo.mode.v1", "verb": "invoke",
            "input_schema": {"type": "object", "properties": {"mode": {"const": "safe"}}}}]})
        drift = local.resolve_binding("cap.demo.mode.v1", {"properties": {"mode": {"enum": ["safe", "fast"]}}}).drift
        self.assertEqual([(item.kind, item.path) for item in drift], [("enum-not-subset", "input.mode")])


class EffectiveSchemaTests(unittest.TestCase):
    """The effective schema of a non-skeleton binding is binding ∩ class (SC-01 fix 3)."""

    CAP = "cap.thermal.setpoint.v1"

    def test_omitted_class_keywords_are_enforced(self):
        binding = {"type": "object", "properties": {"target_temperature": {"type": "number"},
                                                    "rate": {"type": "number"}}}
        original = copy.deepcopy(binding)
        effective = catalog.resolve_binding(self.CAP, binding)
        self.assertEqual(effective.drift, ())
        schema = effective.input_schema
        self.assertEqual(binding, original)
        self.assertNotEqual(validate({}, schema), [])                                    # class required
        self.assertNotEqual(validate({"target_temperature": 20, "rate": -5}, schema), [])  # class minimum 0
        self.assertNotEqual(validate({"target_temperature": 20, "bogus": 1}, schema), [])  # class is closed
        self.assertNotEqual(validate({"target_temperature": 20, "wait": "yes"}, schema), [])  # class-only property
        self.assertEqual(validate({"target_temperature": 20, "rate": 2, "wait": True}, schema), [])
        self.assertEqual(schema["required"], ["target_temperature"])
        self.assertEqual(schema["properties"]["target_temperature"]["x-mhs-unit"], "Cel")
        self.assertEqual(schema["properties"]["rate"]["x-mhs-unit"], "K/min")
        self.assertEqual(_uncovered(schema, effective.class_input_schema), [])

    def test_the_reference_file_publishes_the_class_contract(self):
        from mhs.reference_file import render

        manifest = load_json(VALID / "device.thermal-bath.json")
        binding = next(item for item in manifest["capabilities"] if item["capability_id"] == self.CAP)
        binding["input_schema"] = {"type": "object", "properties": {"target_temperature": {"type": "number"},
                                                                    "rate": {"type": "number"}}}
        action = next(item for item in render(manifest)["actions"] if item["cap_id"] == self.CAP)
        inputs = {item["name"]: item for item in action["inputs"]}
        self.assertTrue(inputs["target_temperature"]["required"])
        self.assertEqual(inputs["target_temperature"]["unit"], "Cel")
        self.assertEqual(inputs["rate"]["unit"], "K/min")
        self.assertFalse(inputs["rate"]["required"])
        self.assertEqual(sorted(inputs), ["rate", "target_temperature", "tolerance", "wait"])

    def test_a_closed_binding_narrows_the_property_set(self):
        closed = {"type": "object", "properties": {"target_temperature": {"type": "number"}},
                  "additionalProperties": False}
        effective = catalog.resolve_binding(self.CAP, closed)
        self.assertEqual(effective.drift, ())
        self.assertNotEqual(validate({"target_temperature": 20, "wait": True}, effective.input_schema), [])
        self.assertEqual(validate({"target_temperature": 20}, effective.input_schema), [])
        # a closed binding that leaves out a class-required property drifts, and still has to accept it
        partial = {"type": "object", "properties": {"rate": {"type": "number"}}, "additionalProperties": False}
        effective = catalog.resolve_binding(self.CAP, partial)
        self.assertEqual(_kinds(effective), ["required-missing"])
        self.assertNotEqual(validate({"rate": 1}, effective.input_schema), [])
        self.assertEqual(validate({"target_temperature": 20, "rate": 1}, effective.input_schema), [])

    def test_stated_keywords_are_kept_and_reported(self):
        effective = catalog.resolve_binding(self.CAP, {"type": "object", "properties": {
            "target_temperature": {"type": "number"}, "rate": {"type": "number", "minimum": -1}}})
        self.assertEqual([(item.kind, item.path) for item in effective.drift], [("widens", "input.rate")])
        self.assertEqual(effective.input_schema["properties"]["rate"]["minimum"], -1)   # compatibility mode
        self.assertNotEqual(validate({"target_temperature": 20, "rate": -0.5}, effective.class_input_schema), [])

    def test_nested_objects_items_and_prefix_items(self):
        pose = catalog.resolve_binding("cap.motion.cartesian_pose.v1", {"type": "object", "properties": {
            "position": {"type": "object", "properties": {"x": {"type": "number"}}}}})
        self.assertEqual(pose.drift, ())
        position = pose.input_schema["properties"]["position"]
        self.assertEqual(position["required"], ["x", "y", "z"])
        self.assertEqual(position["properties"]["x"]["x-mhs-unit"], "mm")
        self.assertNotEqual(validate({"position": {"x": 1, "y": 2}}, pose.input_schema), [])
        self.assertNotEqual(validate({"position": {"x": 1, "y": 2, "z": 3, "w": 4}}, pose.input_schema), [])
        self.assertEqual(validate({"position": {"x": 1, "y": 2, "z": 3}}, pose.input_schema), [])
        joints = catalog.resolve_binding("cap.motion.joint_position.v1", {"type": "object", "properties": {
            "joint_positions": {"type": "array", "minItems": 6, "maxItems": 6}}})
        self.assertEqual(joints.drift, ())
        field = joints.input_schema["properties"]["joint_positions"]
        self.assertEqual(field["items"], {"type": "number", "x-mhs-unit": "rad"})
        self.assertNotEqual(validate({"joint_positions": ["a"] * 6}, joints.input_schema), [])
        compiled = limits.compile_limits(joints.input_schema, [("binding", {"joint_positions": {"max": [1] * 6,
                                                                                               "unit": "rad"}})])
        self.assertEqual(compiled.rules["joint_positions"].unit, "rad")
        prefix = catalog.resolve_binding("cap.motion.joint_position.v1", {"type": "object", "properties": {
            "joint_positions": {"type": "array", "prefixItems": [{}, {}], "items": False}}})
        elements = prefix.input_schema["properties"]["joint_positions"]
        self.assertEqual(elements["prefixItems"], [{"type": "number", "x-mhs-unit": "rad"}] * 2)
        self.assertIs(elements["items"], False)
        self.assertNotEqual(validate({"joint_positions": [0, "a"]}, prefix.input_schema), [])

    def test_incomparable_keywords_both_apply(self):
        local = catalog.Catalog({"capabilities": [{
            "capability_id": "cap.demo.tag.v1", "verb": "invoke",
            "input_schema": {"type": "object", "properties": {"tag": {"type": "string", "pattern": "^a"},
                                                              "mode": {"const": "safe"}},
                             "additionalProperties": False}}]})
        effective = local.resolve_binding("cap.demo.tag.v1", {"properties": {"tag": {"pattern": "b$"},
                                                                             "mode": {"type": "string"}}})
        self.assertEqual(effective.drift, ())
        schema = effective.input_schema
        self.assertEqual(schema["properties"]["tag"]["allOf"], [{"pattern": "^a"}])
        self.assertEqual(validate({"tag": "ab"}, schema), [])
        self.assertNotEqual(validate({"tag": "xb"}, schema), [])
        self.assertNotEqual(validate({"tag": "ax"}, schema), [])
        self.assertNotEqual(validate({"mode": "fast"}, schema), [])   # the class const is inherited
        self.assertEqual(validate({"mode": "safe"}, schema), [])

    def test_bare_bindings_of_every_class_cover_the_class(self):
        # a binding that lists every class property without any keyword omits everything: no drift,
        # and the effective schema states every class constraint
        for capability_id in CAT.ids():
            if capability_id == CONFIGURE_CLASS:
                continue
            cls = catalog.get(capability_id)

            def bare(schema):
                return {"type": "object", "properties": {name: {"description": "bare"}
                                                         for name in schema.get("properties") or {}}}

            if not cls["input_schema"].get("properties") or not cls["output_schema"].get("properties"):
                continue
            with self.subTest(capability_id=capability_id):
                effective = catalog.resolve_binding(capability_id, bare(cls["input_schema"]),
                                                    bare(cls["output_schema"]))
                self.assertEqual(effective.drift, ())
                self.assertEqual(_uncovered(effective.input_schema, cls["input_schema"]), [])
                self.assertEqual(_uncovered(effective.output_schema, cls["output_schema"], "output"), [])
                for example in cls["examples"]:
                    self.assertEqual(validate(example, effective.input_schema), [])

    def test_reference_and_example_bindings_cover_their_class(self):
        from mhs.reference import build_endpoint

        devices = [device for name in ("conveyor", "arm", "lab") for device in build_endpoint(name).devices]
        devices += list(valid_manifests().values())
        checked = 0
        for device in devices:
            resources = {item["resource_id"]: item for item in device["resources"]}
            for binding in device["capabilities"]:
                capability_id = binding["capability_id"]
                if catalog.is_extension(capability_id) or capability_id == CONFIGURE_CLASS:
                    continue
                resource = resources[binding["resource"]]
                effective = catalog.resolve_binding(capability_id, binding.get("input_schema"),
                                                    binding.get("output_schema"), resource["kind"], device["mode"],
                                                    state_schema=resource.get("state_schema"))
                if effective.drift:
                    continue
                with self.subTest(device=device["device_id"], capability_id=capability_id):
                    checked += 1
                    self.assertEqual(_uncovered(effective.input_schema, effective.class_input_schema), [])
                    self.assertEqual(_uncovered(effective.output_schema, effective.class_output_schema, "output"), [])
        self.assertGreater(checked, 10)

    def test_merge_schema_directly(self):
        cls = {"type": "object", "properties": {"a": {"type": "integer", "maximum": 5}}, "required": ["a"],
               "additionalProperties": False}
        self.assertEqual(catalog.merge_schema(None, cls), cls)
        self.assertEqual(catalog.merge_schema(True, cls), cls)
        self.assertEqual(catalog.merge_schema({"properties": {"a": {"maximum": 3}}}, cls),
                         {"type": "object", "properties": {"a": {"type": "integer", "maximum": 3}}, "required": ["a"],
                          "additionalProperties": False})
        self.assertEqual(catalog.merge_schema({"properties": {"a": False}}, cls)["properties"]["a"], False)
        self.assertEqual(catalog.merge_schema({"title": "x"}, None), {"title": "x"})


class ManifestLimitsTests(unittest.TestCase):
    def test_valid_examples_compile(self):
        overlay = load_json(VALID / "site-limits.example-lab.json")
        for device_id, manifest in valid_manifests().items():
            with self.subTest(device=device_id):
                plain = catalog.compile_manifest_limits(manifest)
                narrowed = catalog.compile_manifest_limits(manifest, overlay)
                self.assertEqual(len(plain.bindings), len(manifest["capabilities"]))
                self.assertEqual(plain.unused_envelope, ())
                self.assertTrue(narrowed.narrowed)

    def test_thermal_bath_overlay(self):
        manifest = load_json(VALID / "device.thermal-bath.json")
        overlay = load_json(VALID / "site-limits.example-lab.json")
        plain = catalog.compile_manifest_limits(manifest)
        self.assertEqual(plain.unset, ((CONFIGURE_CLASS, "bath", "pump_speed"),))
        compiled = catalog.compile_manifest_limits(manifest, overlay)
        self.assertEqual(compiled.unset, ())
        configure = compiled.get(CONFIGURE_CLASS).limits
        self.assertEqual(configure.rules["setpoint"].max.value, 95)
        self.assertEqual(configure.rules["setpoint"].min.value, -20)
        setpoint = compiled.get("cap.thermal.setpoint.v1").limits
        self.assertEqual(setpoint.rules["target_temperature"].max.value, 95)
        self.assertEqual(setpoint.rules["target_temperature"].min.value, -20)
        self.assertIn("setpoint.max: 150 -> 95", compiled.narrowed)
        self.assertIn("cap.thermal.setpoint.v1 target_temperature.max: 120 -> 95", compiled.narrowed)
        found = limits.check({"target_temperature": 100}, setpoint)
        self.assertEqual([(v.kind, v.bound, v.source) for v in found], [("max", 95, "overlay")])
        self.assertEqual(limits.check({"setpoint": 96}, configure)[0].source, "overlay")
        self.assertEqual(compiled.by_capability()[(CONFIGURE_CLASS, "bath")], configure)

    def test_semantic_invalid_examples(self):
        manifests = valid_manifests()
        checked = set()
        for case in expected_failures():
            if case["check"] != "semantic":
                continue
            document = load_json(INVALID / case["file"])
            tokens = pointer_tokens(case["pointer"])
            with self.subTest(file=case["file"], rule=case["rule"]):
                checked.add(case["rule"])
                if case["rule"] == "verb-matches-class":
                    index = int(tokens[1])
                    binding = document["capabilities"][index]
                    effective = catalog.resolve_binding(binding["capability_id"], binding.get("input_schema"),
                                                        binding.get("output_schema"), binding_verb=binding["verb"])
                    self.assertIn("verb-differs", _kinds(effective))
                    compiled = catalog.compile_manifest_limits(document)   # drift is reported, not raised
                    self.assertIn("verb-differs", _kinds(compiled.bindings[index].effective))
                    continue
                if case["file"].startswith("site-limits."):
                    device_id = tokens[1]
                    with self.assertRaises(LimitConfigError) as caught:
                        catalog.compile_manifest_limits(manifests[device_id], document)
                    self.assertEqual(caught.exception.rule, case["rule"])
                    self.assertEqual(caught.exception.source, "overlay")
                    self.assertEqual(caught.exception.member, tokens[-1])
                    continue
                with self.assertRaises(LimitConfigError) as caught:
                    catalog.compile_manifest_limits(document)
                self.assertEqual(caught.exception.rule, case["rule"])
                self.assertEqual(caught.exception.path, tokens[3])
                self.assertEqual(caught.exception.source, "binding")
                if len(tokens) > 4:
                    self.assertEqual(caught.exception.member, tokens[4])
        self.assertEqual(checked, {"limit-path-resolves", "array-bound-length", "limit-unit-matches-field",
                                   "verb-matches-class", "overlay-narrows"})

    def test_schema_invalid_limit_examples_are_refused_by_the_engine_too(self):
        for name, rule in (("device.limit-key-typo.json", "unknown-rule-member"),
                           ("device.unknown-rule-member.json", "unknown-rule-member"),
                           ("device.limit-path-grammar.json", "limit-path-grammar")):
            with self.subTest(file=name):
                with self.assertRaises(LimitConfigError) as caught:
                    catalog.compile_manifest_limits(load_json(INVALID / name))
                self.assertEqual(caught.exception.rule, rule)

    def test_envelope_pattern_and_unused_entries(self):
        manifest = copy.deepcopy(load_json(VALID / "device.thermal-bath.json"))
        manifest["safety"]["envelope"]["cap.*"] = {"target_temperature": {"max": 1000}}
        compiled = catalog.compile_manifest_limits(manifest)
        rule = compiled.get("cap.thermal.setpoint.v1").limits.rules["target_temperature"]
        self.assertEqual(rule.max.value, 120)   # the wider pattern never widens
        manifest["safety"]["envelope"]["cap.*"] = {"target_temprature": {"max": 1000}}
        with self.assertRaises(LimitConfigError) as caught:
            catalog.compile_manifest_limits(manifest)
        self.assertEqual(caught.exception.rule, "limit-path-resolves")
        del manifest["safety"]["envelope"]["cap.*"]
        manifest["safety"]["envelope"]["cap.motion.stop.v1"] = {"deceleration": {"max": 1}}
        self.assertEqual(catalog.compile_manifest_limits(manifest).unused_envelope, ("cap.motion.stop.v1",))

    def test_overlay_targets_must_exist(self):
        manifest = load_json(VALID / "device.thermal-bath.json")
        device_id = manifest["device_id"]
        for entry, rule in (({"cap.motion.stop.v1": {"deceleration": {"max": 1}}}, "overlay-binding-known"),
                            ({"setpiont": {"max": 1}}, "limit-path-resolves"),
                            ({"temperature": {"max": 1}}, "limit-path-resolves")):
            with self.subTest(entry=entry):
                with self.assertRaises(LimitConfigError) as caught:
                    catalog.compile_manifest_limits(manifest, {"devices": {device_id: entry}})
                self.assertEqual(caught.exception.rule, rule)

    def test_manifest_defects(self):
        manifest = copy.deepcopy(load_json(VALID / "device.thermal-bath.json"))
        manifest["capabilities"][1]["resource"] = "ghost"
        with self.assertRaises(CatalogError):
            catalog.compile_manifest_limits(manifest)
        manifest = copy.deepcopy(load_json(VALID / "device.thermal-bath.json"))
        manifest["capabilities"][1]["capability_id"] = "cap.thermal.setpointt.v1"
        with self.assertRaises(UnknownCapabilityError):
            catalog.compile_manifest_limits(manifest)

    def test_reference_endpoints_compile(self):
        from mhs.reference import build_endpoint

        for name in ("conveyor", "arm", "lab"):
            for device in build_endpoint(name).devices:
                with self.subTest(device=device["device_id"]):
                    compiled = catalog.compile_manifest_limits(device)
                    self.assertEqual(len(compiled.bindings), len(device["capabilities"]))
        conveyor = catalog.compile_manifest_limits(build_endpoint("conveyor").devices[0])
        # WP-06 06c: the conveyor declares the test-profile delay's envelope only in its test profile.
        self.assertIn(conveyor.unused_envelope, ((), ("x-cap.mhs-test.delay.v1",)))
        found = limits.check({"ticks": 20000}, conveyor.get("cap.world.step.v1").limits)
        self.assertEqual([(v.kind, v.bound) for v in found], [("max", 10000)])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

"""The capability catalogue (MHS/spec/capabilities.json) is binding, typed and self-consistent."""

from __future__ import annotations

import json
import unittest

from mhs.schema import SchemaStore, validate

from . import _semantics
from ._support import CAPABILITIES, SCHEMA_DIR, load_json

STORE = SchemaStore(root=SCHEMA_DIR)
CATALOGUE = load_json(CAPABILITIES)
CLASSES = CATALOGUE["capabilities"]
BY_ID = {entry["capability_id"]: entry for entry in CLASSES}

DEPRECATED = {
    "cap.device.describe.v1": "mhs.devices.get",
    "cap.world.state.v1": "mhs.resource.read",
    "cap.world.snapshot.v1": "mhs.snapshot",
    "cap.world.restore.v1": "mhs.restore",
    "cap.motion.estop.v1": "mhs.safety.estop",
    "cap.compute.cancel.v1": "mhs.operations.cancel",
}
#: The 15 classes no registry manifest bound at review time (SC-05).  Two of
#: them also duplicate protocol methods; deprecated takes precedence.
UNUSED = {
    "cap.compute.cancel.v1", "cap.fluid.level.v1", "cap.fluid.mix.v1", "cap.fluid.wash.v1",
    "cap.manipulation.release.v1", "cap.motion.cartesian_twist.v1", "cap.motion.estop.v1",
    "cap.motion.home.v1", "cap.motion.joint_torque.v1", "cap.optics.align.v1",
    "cap.optics.set_power.v1", "cap.optics.shutter.v1", "cap.sample.seal.v1",
    "cap.sample.store.v1", "cap.sample.unseal.v1",
}


def _walk(schema, path=""):
    """Yield (field path, field schema) for every property, items included."""
    if not isinstance(schema, dict):
        return
    if path:
        yield path, schema
    if isinstance(schema.get("items"), dict):
        yield from _walk(schema["items"], path + "[*]")
    for name, sub in (schema.get("properties") or {}).items():
        yield from _walk(sub, f"{path}.{name}" if path else name)


def _unit_map(entry):
    units = {}
    for section in ("input_schema", "output_schema"):
        for path, field in _walk(entry[section]):
            if isinstance(field.get("x-mhs-unit"), str):
                units[path.replace("[*]", "")] = field["x-mhs-unit"]
    return units


class CatalogueShapeTests(unittest.TestCase):
    def test_every_class_validates_against_capability_schema(self):
        for entry in CLASSES:
            with self.subTest(cls=entry["capability_id"]):
                self.assertEqual(STORE.validate(entry, "capability.schema.json"), [])

    def test_count_and_ids_are_consistent(self):
        ids = [entry["capability_id"] for entry in CLASSES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(CATALOGUE["capability_count"], len(CLASSES))
        self.assertEqual(CATALOGUE["spec_version"], "0.9")

    def test_every_class_has_status_and_profile(self):
        for entry in CLASSES:
            with self.subTest(cls=entry["capability_id"]):
                self.assertIn(entry.get("status"), ("stable", "experimental", "deprecated"))
                self.assertIn(entry.get("profile"), ("core", "sim"))
                self.assertEqual(entry["profile"] == "sim", entry["capability_id"].startswith("cap.world."))

    def test_deprecated_classes_name_their_protocol_method(self):
        deprecated = {e["capability_id"]: e.get("x-mhs-replaced-by") for e in CLASSES if e["status"] == "deprecated"}
        self.assertEqual(deprecated, DEPRECATED)

    def test_unused_classes_are_experimental_unless_deprecated(self):
        experimental = {e["capability_id"] for e in CLASSES if e["status"] == "experimental"}
        self.assertEqual(experimental, UNUSED - set(DEPRECATED))

    def test_no_class_input_carries_expected_revision(self):
        for entry in CLASSES:
            with self.subTest(cls=entry["capability_id"]):
                self.assertNotIn("expected_revision", json.dumps(entry["input_schema"]))

    def test_resource_kinds_list_is_the_union_of_class_kinds(self):
        listed = [item["kind"] for item in CATALOGUE["resource_kinds"]]
        self.assertEqual(listed, sorted(set(listed)))
        used = {kind for entry in CLASSES for kind in entry["resource_kinds"] if kind != "*"}
        self.assertEqual(set(listed), used)
        for item in CATALOGUE["resource_kinds"]:
            for other in item.get("see_also", []):
                self.assertIn(other, listed)
        wildcard = [e["capability_id"] for e in CLASSES if "*" in e["resource_kinds"]]
        self.assertEqual(wildcard, ["cap.device.configure.v1"])


class ConfigureClassTests(unittest.TestCase):
    def test_configure_class_exists_with_the_frozen_contract(self):
        entry = BY_ID["cap.device.configure.v1"]
        self.assertEqual(entry["verb"], "write")
        self.assertEqual(entry["risk_class"], "R1")
        self.assertEqual(entry["status"], "stable")
        self.assertEqual(entry["profile"], "core")
        self.assertEqual(entry["resource_kinds"], ["*"])
        self.assertIs(entry["input_schema"].get("x-mhs-open"), True)
        self.assertEqual(sorted(entry["output_schema"]["required"]), ["applied", "revision"])

    def test_configure_input_is_derived_from_writable_state(self):
        manifest = {"resources": [{"resource_id": "bath", "kind": "thermal.zone", "state_schema": {
            "type": "object", "properties": {
                "temperature": {"type": "number", "x-mhs-unit": "Cel", "readOnly": True},
                "setpoint": {"type": "number", "x-mhs-unit": "Cel", "minimum": -20, "maximum": 150}}}}]}
        binding = {"capability_id": "cap.device.configure.v1", "resource": "bath"}
        schema = _semantics.effective_input(binding, manifest, BY_ID)
        self.assertEqual(set(schema["properties"]), {"setpoint"})
        self.assertEqual(validate({"setpoint": 37}, schema), [])
        self.assertTrue(validate({"temperature": 20}, schema))
        self.assertTrue(validate({"setpoint": 400}, schema))


class ExampleAndUnitTests(unittest.TestCase):
    def test_every_class_example_validates_against_its_input_schema(self):
        for entry in CLASSES:
            with self.subTest(cls=entry["capability_id"]):
                self.assertGreaterEqual(len(entry.get("examples") or []), 1)
                for example in entry["examples"]:
                    self.assertEqual(validate(example, entry["input_schema"]), [])

    def test_examples_respect_class_limits(self):
        for entry in CLASSES:
            for path, rule in (entry.get("limits") or {}).items():
                for example in entry["examples"]:
                    value = example
                    for token in _semantics.path_tokens(path):
                        value = value.get(token) if isinstance(value, dict) else None
                    if not isinstance(value, (int, float)) or isinstance(value, bool):
                        continue
                    with self.subTest(cls=entry["capability_id"], path=path):
                        if isinstance(rule.get("max"), (int, float)):
                            self.assertLessEqual(value, rule["max"])
                        if isinstance(rule.get("min"), (int, float)):
                            self.assertGreaterEqual(value, rule["min"])

    def test_units_map_equals_the_x_mhs_unit_annotations(self):
        # CAP-044, array fields included.
        for entry in CLASSES:
            with self.subTest(cls=entry["capability_id"]):
                self.assertEqual(entry["units"], _unit_map(entry))

    def test_rotation_rates_use_per_minute(self):
        centrifuge = BY_ID["cap.sample.centrifuge.v1"]
        self.assertEqual(centrifuge["input_schema"]["properties"]["rpm"]["x-mhs-unit"], "/min")
        self.assertEqual(centrifuge["output_schema"]["properties"]["rpm_actual"]["x-mhs-unit"], "/min")
        self.assertEqual(centrifuge["limits"]["rpm"]["unit"], "/min")
        self.assertEqual(BY_ID["cap.fluid.mix.v1"]["input_schema"]["properties"]["speed"]["x-mhs-unit"], "/min")

    def test_class_limits_resolve_and_match_field_units(self):
        for entry in CLASSES:
            for path, rule in (entry.get("limits") or {}).items():
                with self.subTest(cls=entry["capability_id"], path=path):
                    field = _semantics.resolve(entry["input_schema"], path)
                    self.assertIsNotNone(field, "class limit path does not resolve")
                    self.assertEqual(_semantics.check_rule("", rule, field), [])

    def test_input_bounds_never_exceed_class_limits(self):
        for entry in CLASSES:
            for path, rule in (entry.get("limits") or {}).items():
                field = _semantics.resolve(entry["input_schema"], path) or {}
                with self.subTest(cls=entry["capability_id"], path=path):
                    if isinstance(rule.get("max"), (int, float)) and "maximum" in field:
                        self.assertLessEqual(field["maximum"], rule["max"])
                    if isinstance(rule.get("min"), (int, float)) and "minimum" in field:
                        self.assertGreaterEqual(field["minimum"], rule["min"])

    def test_aspirate_and_centrifuge_bounds_were_aligned(self):
        self.assertEqual(BY_ID["cap.fluid.aspirate.v1"]["input_schema"]["properties"]["volume"]["maximum"], 1000)
        self.assertEqual(BY_ID["cap.sample.centrifuge.v1"]["input_schema"]["properties"]["rpm"]["maximum"], 15000)


if __name__ == "__main__":
    unittest.main()

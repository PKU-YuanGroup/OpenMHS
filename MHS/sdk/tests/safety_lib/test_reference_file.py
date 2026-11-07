"""mhs.reference_file: deterministic, schema-valid reference files and REFERENCE.md."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from mhs import canonical, catalog, limits, reference_file
from mhs.reference_file import ReferenceFileError, dump, render, render_markdown

from ._support import VALID, load_json

SECTIONS = ("## Measures", "## Adjusts", "## Actions", "## Safety", "## Facts")


def _reference_devices():
    from mhs.reference import build_endpoint

    for name in ("conveyor", "arm", "lab"):
        yield from build_endpoint(name).devices


class ConveyorAcceptanceTests(unittest.TestCase):
    def test_conveyor_renders_byte_identically_and_validates(self):
        from mhs.reference import build_endpoint

        first = dump(render(build_endpoint("conveyor").devices[0]))
        second = dump(render(build_endpoint("conveyor").devices[0]))
        self.assertEqual(first, second)
        document = json.loads(first)
        self.assertEqual(reference_file.validate(document), [])
        self.assertEqual(first, canonical.jcs(document))
        self.assertEqual(document["openmhs"], "0.9")
        self.assertIs(document["safety"]["not_certified"], True)
        step = next(action for action in document["actions"] if action["cap_id"] == "cap.world.step.v1")
        ticks = next(field for field in step["inputs"] if field["name"] == "ticks")
        # WP-06 06c raised the minimum to the class's 1 (it was 0).
        self.assertIn((ticks["limit"]["min"], ticks["limit"]["max"]), ((0, 10000), (1, 10000)))

    def test_markdown_is_deterministic_and_complete(self):
        from mhs.reference import build_endpoint

        reference = render(build_endpoint("conveyor").devices[0])
        text = render_markdown(reference)
        self.assertEqual(text, render_markdown(copy.deepcopy(reference)))
        positions = [text.index(section) for section in SECTIONS]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("`world.step`", text)
        self.assertTrue("0 .. 10000" in text or "1 .. 10000" in text, text)  # minimum 1 since WP-06 06c
        self.assertIn("not a safety certification", text)
        self.assertTrue(text.endswith("\n"))

    def test_every_reference_endpoint_renders(self):
        for device in _reference_devices():
            with self.subTest(device=device["device_id"]):
                before = copy.deepcopy(device)
                reference = render(device)
                self.assertEqual(reference_file.validate(reference), [])
                self.assertEqual(device, before)   # the manifest is never modified
                self.assertEqual(dump(render(device)), dump(reference))
                for section in SECTIONS:
                    self.assertIn(section, render_markdown(reference))


class ThermalBathTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_json(VALID / "device.thermal-bath.json")
        self.overlay = load_json(VALID / "site-limits.example-lab.json")
        self.example = load_json(VALID / "reference.thermal-bath.json")

    def test_without_overlay_the_operator_bound_is_unset(self):
        reference = render(self.manifest)
        adjusts = {item["name"]: item for item in reference["adjusts"]}
        self.assertEqual(sorted(adjusts), ["pump_speed", "setpoint"])
        self.assertEqual(adjusts["pump_speed"]["limit"], "operator_required")
        self.assertEqual(adjusts["setpoint"]["limit"]["max"], 150)
        self.assertEqual(adjusts["setpoint"]["limit"]["source"], "vendor_doc")
        self.assertEqual(reference["safety"]["operator_required"], [{"name": "pump_speed"}])
        self.assertIsNone(reference["overlay"])
        measures = {item["name"]: item for item in reference["measures"]}
        # readOnly state, plus the read binding that needs no input (as in the example file),
        # named by the binding's x-mhs-name
        self.assertEqual(sorted(measures), ["circulating", "measure_temperature", "temperature"])
        expected = next(item for item in self.example["measures"] if item.get("cap_id"))
        served = measures["measure_temperature"]
        for key in ("type", "unit", "cap_id", "resource", "inputs"):
            self.assertEqual(served[key], expected[key], key)
        self.assertNotIn("cap.measure.temperature.v1", [item["cap_id"] for item in reference["actions"]])
        self.assertIn("LIMITS_UNSET", render_markdown(reference))

    def test_reads_that_need_input_stay_actions(self):
        manifest = copy.deepcopy(self.manifest)
        binding = next(item for item in manifest["capabilities"] if item["capability_id"] == "cap.measure.temperature.v1")
        binding["input_schema"] = {"type": "object", "properties": {"probe": {"type": "string"}}, "required": ["probe"]}
        reference = render(manifest)
        self.assertNotIn("measure_temperature", [item["name"] for item in reference["measures"]])
        action = next(item for item in reference["actions"] if item["cap_id"] == "cap.measure.temperature.v1")
        self.assertEqual([(item["name"], item["required"]) for item in action["inputs"]],
                         [("probe", True), ("location", False)])
        gated = copy.deepcopy(self.manifest)
        next(item for item in gated["capabilities"]
             if item["capability_id"] == "cap.measure.temperature.v1")["requires_permit"] = True
        action = next(item for item in render(gated)["actions"] if item["cap_id"] == "cap.measure.temperature.v1")
        self.assertTrue(action["requires_permit"])

    def test_overlay_narrowing_matches_the_example(self):
        reference = render(self.manifest, overlay=self.overlay, tags=self.example["tags"],
                           facts=self.example["facts"])
        self.assertEqual(reference_file.validate(reference), [])
        adjusts = {item["name"]: item for item in reference["adjusts"]}
        expected = {item["name"]: item for item in self.example["adjusts"]}
        for name in ("setpoint", "pump_speed"):
            for key in ("min", "max", "unit", "source"):
                self.assertEqual(adjusts[name]["limit"][key], expected[name]["limit"][key], (name, key))
        self.assertEqual(reference["safety"]["operator_required"], [])
        self.assertEqual(reference["overlay"]["digest"], self.example["overlay"]["digest"])
        for line in self.example["overlay"]["narrowed"]:
            self.assertIn(line, reference["overlay"]["narrowed"])
        action = next(item for item in reference["actions"] if item["cap_id"] == "cap.thermal.setpoint.v1")
        target = next(item for item in action["inputs"] if item["name"] == "target_temperature")
        self.assertEqual((target["limit"]["min"], target["limit"]["max"]), (-20, 95))
        self.assertTrue(action["long_running"])
        self.assertEqual(action["risk"], "R2")
        self.assertEqual(reference["device"]["risk"], "R2")
        # the manifest's safety.estop.native, as the example shows
        self.assertEqual(reference["safety"]["estop"], {"kind": "both", "latching": True, "native": "stop",
                                                        "latency_ms": 200,
                                                        "physical_ref": "red stop switch on the front panel"})
        self.assertEqual(reference["safety"]["estop"], self.example["safety"]["estop"])
        self.assertIn("native stop `stop`", render_markdown(reference))
        self.assertEqual(reference["safety"]["watchdog_ms"], 5000)
        heater = next(item for item in reference["actions"] if item["cap_id"].startswith("x-cap."))
        self.assertEqual(heater["status"], "extension")
        self.assertEqual(heater["name"], "heater_off")
        self.assertEqual(reference["facts"], self.example["facts"])

    def test_the_example_is_the_renderer_output(self):
        # reference.thermal-bath.json is render(device.thermal-bath.json, site-limits.json, facts, tags,
        # provenance) without the two provenance digests, which change with every catalogue edit
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "site-limits.json"
            path.write_text(json.dumps(self.overlay), encoding="utf-8")
            reference = render(self.manifest, overlay=path, facts=self.example["facts"], tags=self.example["tags"],
                               provenance={key: self.example["provenance"][key]
                                           for key in reference_file.PROVENANCE_KEYS})
        self.assertEqual(reference["provenance"].pop("catalogue_digest"), catalog.default_catalog().digest)
        self.assertTrue(reference["provenance"].pop("manifest_digest").startswith("sha256:"))
        self.assertEqual(reference, self.example)
        # without x-mhs-name a binding is named after its capability id
        plain = copy.deepcopy(self.manifest)
        for binding in plain["capabilities"]:
            binding.pop("x-mhs-name", None)
        names = {item.get("cap_id"): item["name"] for item in render(plain)["measures"] + render(plain)["actions"]}
        self.assertEqual((names["cap.measure.temperature.v1"], names["cap.thermal.setpoint.v1"],
                          names["x-cap.example.heater_off.v1"]),
                         ("measure.temperature", "thermal.setpoint", "example.heater_off"))

    def test_overlay_given_as_a_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "site-limits.json"
            path.write_text(json.dumps(self.overlay), encoding="utf-8")
            reference = render(self.manifest, overlay=path)
        self.assertEqual(reference["overlay"]["file"], "site-limits.json")
        self.assertEqual(reference["overlay"]["digest"], canonical.digest(self.overlay))
        with self.assertRaises(ReferenceFileError):
            render(self.manifest, overlay=Path("/nonexistent/site-limits.json"))

    def test_widening_overlay_is_refused(self):
        widening = copy.deepcopy(self.overlay)
        widening["devices"][self.manifest["device_id"]]["setpoint"]["max"] = 200
        with self.assertRaises(limits.LimitConfigError):
            render(self.manifest, overlay=widening)

    def test_estop_native(self):
        software = render(self.manifest, estop_native=None)
        self.assertIsNone(software["safety"]["estop"]["native"])
        self.assertIn("no native stop", render_markdown(software))
        self.assertEqual(render(self.manifest)["safety"]["estop"]["native"], "stop")   # device.schema safety.estop
        bare = copy.deepcopy(self.manifest)
        del bare["safety"]["estop"]["native"]
        self.assertNotIn("native", render(bare)["safety"]["estop"])
        manifest = copy.deepcopy(self.manifest)
        manifest["safety"]["estop"]["native"] = "emergency_stop"
        self.assertEqual(render(manifest)["safety"]["estop"]["native"], "emergency_stop")
        self.assertEqual(render(manifest, estop_native="halt")["safety"]["estop"]["native"], "halt")
        manifest["safety"]["estop"]["native"] = None
        self.assertIsNone(render(manifest)["safety"]["estop"]["native"])
        for bad in ("", "  ", 3):
            with self.subTest(native=bad):
                with self.assertRaises(ReferenceFileError):
                    render(self.manifest, estop_native=bad)

    def test_a_partial_limits_mapping_still_applies_the_overlay(self):
        compiled = catalog.compile_manifest_limits(self.manifest, self.overlay)
        partial = {"cap.thermal.setpoint.v1": compiled.get("cap.thermal.setpoint.v1").limits}
        reference = render(self.manifest, partial, overlay=self.overlay)
        self.assertEqual(dump(reference), dump(render(self.manifest, overlay=self.overlay)))
        adjusts = {item["name"]: item for item in reference["adjusts"]}
        self.assertEqual(adjusts["setpoint"]["limit"]["max"], 95)
        self.assertEqual(adjusts["pump_speed"]["limit"]["max"], 1200)
        self.assertIn("setpoint.max: 150 -> 95", reference["overlay"]["narrowed"])

    def test_given_effective_limits_are_used(self):
        compiled = catalog.compile_manifest_limits(self.manifest, self.overlay)
        from_object = render(self.manifest, compiled, overlay=self.overlay)
        self.assertEqual(dump(from_object), dump(render(self.manifest, overlay=self.overlay)))
        narrower = limits.compile_limits(
            compiled.get("cap.thermal.setpoint.v1").effective.input_schema,
            [("binding", {"target_temperature": {"min": 10, "max": 40, "unit": "Cel"}})])
        reference = render(self.manifest, {"cap.thermal.setpoint.v1": narrower})
        action = next(item for item in reference["actions"] if item["cap_id"] == "cap.thermal.setpoint.v1")
        target = next(item for item in action["inputs"] if item["name"] == "target_temperature")
        self.assertEqual((target["limit"]["min"], target["limit"]["max"]), (10, 40))
        with self.assertRaises(ReferenceFileError):
            render(self.manifest, {"cap.thermal.setpoint.v1": {"target_temperature": {"max": 1}}})

    def test_provenance(self):
        reference = render(self.manifest, provenance={"authored_by": {"kind": "human", "name": "A. Author"},
                                                      "reviewed_by": None})
        record = reference["provenance"]
        self.assertEqual(record["generated_by"], reference_file.GENERATED_BY)
        self.assertEqual(record["catalogue_digest"], catalog.default_catalog().digest)
        self.assertEqual(record["authored_by"], {"kind": "human", "name": "A. Author"})
        embedded = dict(self.manifest, reference=reference)
        self.assertEqual(render(embedded)["provenance"]["manifest_digest"], record["manifest_digest"])
        with self.assertRaises(ReferenceFileError):
            render(self.manifest, provenance={"authored_by": {"kind": "model"}})   # model needs model_id
        # the generated members can never be overwritten by the caller
        for key, value in (("generated_by", "hand"), ("sdk_version", "9.9.9"),
                           ("catalogue_digest", "sha256:" + "0" * 64), ("manifest_digest", "sha256:" + "1" * 64)):
            with self.subTest(key=key):
                with self.assertRaises(ReferenceFileError):
                    render(self.manifest, provenance={key: value})
        with self.assertRaises(ReferenceFileError):
            render(self.manifest, provenance=["authored_by"])

    def test_upstream(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["provenance"] = {"source_repo": "https://example.invalid/acme/bath", "source_commit": "a" * 40}
        self.assertEqual(render(manifest)["device"]["upstream"],
                         {"repo": "https://example.invalid/acme/bath", "commit": "a" * 40})
        manifest["provenance"]["source_commit"] = "main"
        self.assertNotIn("upstream", render(manifest)["device"])
        with self.assertRaises(ReferenceFileError):
            render(self.manifest, upstream={"repo": "x", "commit": "main"})


class InputValidationTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_json(VALID / "device.thermal-bath.json")

    def test_facts(self):
        class Fact:
            def __init__(self, text, source, ref=None):
                self.text, self.source, self.ref, self.reviewed_by = text, source, ref, None

        reference = render(self.manifest, facts=[Fact("Holds 20 L", "upstream_code", "bath.py:12"),
                                                 {"text": "Lab note", "source": "operator"}])
        self.assertEqual(reference["facts"], [
            {"text": "Holds 20 L", "source": "upstream_code", "ref": "bath.py:12", "reviewed_by": None},
            {"text": "Lab note", "source": "operator"},
        ])
        for fact in ({"text": "x", "source": "vendor_doc"}, {"text": "x", "source": "guess"}):
            with self.subTest(fact=fact):
                with self.assertRaises(ReferenceFileError):
                    render(self.manifest, facts=[fact])

    def test_tags(self):
        manifest = dict(self.manifest, profile={"tags": ["bath", "circulator"]})
        self.assertEqual(render(manifest, tags=["circulator", "thermal"])["tags"], ["circulator", "thermal", "bath"])
        with self.assertRaises(ReferenceFileError):
            render(self.manifest, tags=["Not A Tag!"])

    def test_bad_names_are_refused(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["resources"][0]["state_schema"]["properties"]["pump speed"] = {"type": "number"}
        with self.assertRaises(ReferenceFileError):
            render(manifest)
        with self.assertRaises(ReferenceFileError):
            render(["not", "a", "manifest"])

    def test_action_names(self):
        manifest = copy.deepcopy(load_json(VALID / "device.arm-6dof.json"))
        manifest["capabilities"][0]["x-mhs-name"] = "move_joints"
        extra = copy.deepcopy(manifest["capabilities"][3])
        manifest["resources"].append({"resource_id": "gripper", "kind": "robot.arm",
                                      "state_schema": {"type": "object", "properties": {}}})
        extra["resource"] = "gripper"
        manifest["capabilities"].append(extra)
        reference = render(manifest)
        names = [item["name"] for item in reference["actions"]]
        self.assertIn("move_joints", names)
        self.assertIn("motion.stop.arm", names)
        self.assertIn("motion.stop.gripper", names)
        self.assertEqual(len(names), len(set(names)))

    def test_per_element_limits_and_names(self):
        reference = render(load_json(VALID / "device.arm-6dof.json"))
        move = next(item for item in reference["actions"] if item["cap_id"] == "cap.motion.joint_position.v1")
        joints = next(item for item in move["inputs"] if item["name"] == "joint_positions")
        self.assertEqual(joints["names"], ["j1", "j2", "j3", "j4", "j5", "j6"])
        self.assertEqual(joints["limit"]["max"], [6.28, 2.09, 0.19, 6.28, 3.14, 6.28])
        self.assertEqual(joints["length"], 6)
        velocity = next(item for item in reference["actions"] if item["cap_id"] == "cap.motion.joint_velocity.v1")
        base = next(item for item in velocity["inputs"] if item["name"] == "joint_velocities[0]")
        self.assertEqual((base["limit"]["min"], base["limit"]["max"]), (-0.5, 0.5))
        pose = next(item for item in reference["actions"] if item["cap_id"] == "cap.motion.cartesian_pose.v1")
        height = next(item for item in pose["inputs"] if item["name"] == "position.z")["limit"]
        # binding 50..900 (vendor_doc) intersected with the envelope's table clearance min 100 (operator)
        self.assertEqual((height["min"], height["max"]), (100, 900))
        markdown = render_markdown(reference)
        self.assertIn("elements j1, j2", markdown)

    def test_an_unsourced_bound_says_so_and_shows_its_ref(self):
        # The bounds a Gymnasium driver derives from its fake backend's action space carry a ref, no source.
        reference = render(load_json(VALID / "device.arm-6dof.json"))
        pose = next(item for item in reference["actions"] if item["cap_id"] == "cap.motion.cartesian_pose.v1")
        height = next(item for item in pose["inputs"] if item["name"] == "position.z")
        sourced = render_markdown(reference)
        height["limit"] = {"min": 100, "max": 900, "ref": "action_space of the fake backend .fake:FakeArm"}
        self.assertIn("100 .. 900 mm; (no source: action_space of the fake backend .fake:FakeArm)",
                      render_markdown(reference))
        height["limit"] = {"min": 100, "max": 900, "reason": "a rationale is not a provenance"}
        self.assertIn("100 .. 900 mm; (no source) |", render_markdown(reference))
        self.assertNotIn("(no source", sourced)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

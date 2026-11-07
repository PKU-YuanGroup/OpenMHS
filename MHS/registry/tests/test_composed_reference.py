#!/usr/bin/env python3
"""Package composition: the validator checks each reference action against its own resource's kind."""
from __future__ import annotations

import copy
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.abspath(os.path.join(HERE, ".."))
MHS = os.path.abspath(os.path.join(REG, ".."))
sys.path.insert(0, REG)
sys.path.insert(0, os.path.join(MHS, "sdk", "src"))
sys.path.insert(0, HERE)

import overlays as OV  # noqa: E402
import validate as V  # noqa: E402
from mhs.driver import Action, RosDriver  # noqa: E402
from mhs.driver.build import build_reference  # noqa: E402
from test_build_pipeline import run  # noqa: E402
from test_overlays_index_validate import DIGEST, STORE, lock_doc, write  # noqa: E402


class Composed(RosDriver):
    device_id, device_kind, mode, risk = "composed", "sensor.camera", "hardware", "R0"
    resource_id = "camera"
    ros_version = 2
    extra_resources = {"depth": {"kind": "sensor.depth"}}
    commands = {
        "cap.sensing.image.v1": {"topic": "/image", "type": "sensor_msgs/msg/Image", "operation": "subscribe",
                                 "image": {}},
        "cap.sensing.point_cloud.v1": {"topic": "/points", "type": "sensor_msgs/msg/PointCloud2",
                                       "operation": "subscribe", "point_cloud": {}},
    }
    actions = {"cap.sensing.point_cloud.v1": Action(resource="depth")}


class ComposedReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "drivers")
        self.pkg = os.path.join(self.root, "labs", "acme__bath")
        self.reference = build_reference(Composed)

    def errors(self, reference):
        rec, card, _d, _lock = run()
        write(os.path.join(self.pkg, "driver.lock.json"), lock_doc())
        write(os.path.join(self.pkg, "RESULT.json"), {"status": "pass", "gate": {"digest": DIGEST, "failed": []}})
        write(os.path.join(self.pkg, "reference.json"), reference)
        return V.check_overlays(OV.load(self.root), {card["package_id"]: card}, {"labs/acme__bath": rec}, STORE,
                                stale=[])

    def test_the_composed_reference_lists_its_resources(self):
        self.assertEqual(self.reference["device"]["resources"],
                         [{"id": "camera", "kind": "sensor.camera"}, {"id": "depth", "kind": "sensor.depth"}])
        self.assertEqual({a["cap_id"]: a["resource"] for a in self.reference["actions"]},
                         {"cap.sensing.image.v1": "camera", "cap.sensing.point_cloud.v1": "depth"})

    def test_each_action_binds_its_own_resource_kind(self):
        self.assertEqual([e for e in self.errors(self.reference) if "KIND_MISMATCH" in e], [])

    def test_without_the_resource_list_every_action_binds_device_kind_as_before(self):
        reference = copy.deepcopy(self.reference)
        del reference["device"]["resources"]
        mismatches = [e for e in self.errors(reference) if "KIND_MISMATCH" in e]
        self.assertEqual(len(mismatches), 1, mismatches)
        self.assertIn("cap.sensing.point_cloud.v1 cannot bind a 'sensor.camera' resource", mismatches[0])

    def test_a_wrong_listed_kind_is_still_a_mismatch(self):
        reference = copy.deepcopy(self.reference)
        reference["device"]["resources"][1]["kind"] = "sensor.camera"
        mismatches = [e for e in self.errors(reference) if "KIND_MISMATCH" in e]
        self.assertEqual(len(mismatches), 1, mismatches)

    def test_the_schema_bounds_the_resource_list(self):
        reference = copy.deepcopy(self.reference)
        reference["device"]["resources"] = reference["device"]["resources"][:1]
        self.assertTrue(any("reference.json" in e for e in self.errors(reference)))

    def test_the_composed_reference_is_consistent(self):
        self.assertEqual([e for e in self.errors(self.reference) if "device.resources" in e], [])

    def test_the_first_listed_resource_must_be_the_main_kind(self):
        reference = copy.deepcopy(self.reference)
        reference["device"]["resources"][0]["kind"] = "sensor.depth"
        errors = [e for e in self.errors(reference) if "device.resources[0].kind" in e]
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("'sensor.depth' is not device.kind 'sensor.camera'", errors[0])

    def test_listed_resource_ids_must_be_unique(self):
        reference = copy.deepcopy(self.reference)
        reference["device"]["resources"][1]["id"] = "camera"
        self.assertTrue(any("device.resources ids are not unique" in e for e in self.errors(reference)))

    def test_every_entry_must_name_a_listed_resource(self):
        reference = copy.deepcopy(self.reference)
        cloud = next(a for a in reference["actions"] if a["cap_id"] == "cap.sensing.point_cloud.v1")
        cloud["resource"] = "lidar"
        errors = [e for e in self.errors(reference) if "which device.resources does not list" in e]
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("names resource 'lidar'", errors[0])


if __name__ == "__main__":
    unittest.main()

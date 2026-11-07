"""Strict mode at runtime: contract, outputs and operations (WP-04 step 4b).

Ports: tests-run ``thermo.py`` (a skeleton binding accepted anything,
TESTS-02), schema-catalog ``exp2.py`` (class ``requires_permit`` ignored,
SC-01), fit-robots-ros FIT-ROS-08 / driver-authoring DRV-06 (outputs never
validated), a NaN in a native result (the completed receipt was lost and the
revision bumped twice), SDK-08 (operations of another principal).
"""

from __future__ import annotations

import json
import math
import unittest

from mhs.schema import SchemaStore
from mhs.server import Capability, Resource

from ._strict_support import (DESCRIBE, EXT, JOINTS, STOP, TORQUE, ArmBridge, RecordWarnings,
                              arm_capabilities, arm_device, arm_safety, arm_server, strict_warnings)
from ._support import error_code, open_session, release_retry

STORE = SchemaStore()


def _thermo(strict, **device_kwargs):
    caps = [Capability("cap.thermal.setpoint.v1", "zone", input_schema={"type": "object"})]
    device = arm_device(capabilities=caps, safety=arm_safety(risk="R2", achieved_by=()),
                        resources=[Resource("zone", "thermal.zone", state_schema={"type": "object"})],
                        **device_kwargs)
    return arm_server(device, strict=strict)


class ResolvedContractTests(unittest.TestCase):
    def test_a_skeleton_binding_inherits_the_class_input_schema(self) -> None:
        server, rpc, device, bridge = _thermo(True)
        session = open_session(rpc, device)
        for bad in ({}, {"target_temperature": "hot"}, {"target_temperature": 20, "colour": "red"}):
            with self.subTest(input=bad):
                receipt = rpc("mhs.command", session_id=session, capability_id="cap.thermal.setpoint.v1",
                              input=bad, deadline_ms=2000)
                self.assertEqual(receipt["status"], "rejected", receipt)
                self.assertEqual(error_code(receipt), "MHS.CAPABILITY.INPUT_INVALID")
        self.assertEqual(bridge.count("cap.thermal.setpoint.v1"), 0)
        receipt = rpc("mhs.command", session_id=session, capability_id="cap.thermal.setpoint.v1",
                      input={"target_temperature": 37.0}, deadline_ms=2000)
        self.assertEqual(receipt["status"], "completed", receipt)
        published = rpc("mhs.devices.get", device_id=device.device_id)["capabilities"][0]
        self.assertEqual(published["verb"], "write")
        self.assertEqual(published["input_schema"]["properties"]["target_temperature"]["x-mhs-unit"], "Cel")
        self.assertEqual(published["input_schema"]["required"], ["target_temperature"])

    def test_strict_manifests_stay_schema_valid(self) -> None:
        for device in (arm_device(torque=True, risk="R2"), arm_device(mode="hardware", torque=True, risk="R2")):
            with self.subTest(mode=device.mode):
                server, rpc, device, bridge = arm_server(device, strict=True, armed=True)
                manifest = rpc("mhs.devices.get", device_id=device.device_id)
                self.assertEqual(STORE.validate(manifest, "device.schema.json"), [])
                self.assertEqual({item["verb"] for item in manifest["capabilities"]}, {"invoke", "read"})

    def test_compatibility_mode_keeps_the_binding_schema(self) -> None:
        server, rpc, device, bridge = _thermo(None)
        session = open_session(rpc, device)
        receipt = rpc("mhs.command", session_id=session, capability_id="cap.thermal.setpoint.v1",
                      input={"target_temperature": 20, "colour": "red"}, deadline_ms=2000)
        self.assertEqual(receipt["status"], "completed", "0.9 compatibility: the binding schema only")
        # The class limits are enforced in both modes (WP-04 4c, plan 3.5): a
        # value that cannot be compared with the class bound never passes it.
        receipt = rpc("mhs.command", session_id=session, capability_id="cap.thermal.setpoint.v1",
                      input={"target_temperature": "hot"}, deadline_ms=2000)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.ENVELOPE_VIOLATION", receipt)
        self.assertEqual(receipt["error"]["details"]["kind"], "type")

    def test_the_class_permit_flag_applies_in_strict_mode(self) -> None:
        server, rpc, device, bridge = arm_server(arm_device(torque=True, risk="R2"), strict=True)
        session = open_session(rpc, device)
        receipt = rpc("mhs.command", session_id=session, capability_id=TORQUE,
                      input={"joint_torques": [0.1], "duration_s": 0.1}, deadline_ms=2000)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.PERMIT_INVALID")
        self.assertEqual(bridge.count(TORQUE), 0)
        self.assertTrue(device._by_capability[TORQUE].requires_permit)  # noqa: SLF001

    def test_compatibility_mode_warns_about_the_class_permit_flag(self) -> None:
        with RecordWarnings() as warned:
            server, rpc, device, bridge = arm_server(arm_device(torque=True, risk="R2"), strict=None)
        self.assertTrue(any("class-requires-permit" in text for text in strict_warnings(warned)))
        session = open_session(rpc, device)
        receipt = rpc("mhs.command", session_id=session, capability_id=TORQUE,
                      input={"joint_torques": [0.1], "duration_s": 0.1}, deadline_ms=2000)
        self.assertEqual(receipt["status"], "completed", receipt)

    def test_a_catalogued_read_stays_callable_while_latched_only_in_strict_mode(self) -> None:
        for strict, expected in ((True, "completed"), (None, "rejected")):
            with self.subTest(strict=strict):
                server, rpc, device, bridge = arm_server(strict=strict)
                session = open_session(rpc, device)
                rpc("mhs.safety.estop", session_id=session, reason="test", deadline_ms=1000)
                receipt = rpc("mhs.command", session_id=session, capability_id=DESCRIBE, input={},
                              deadline_ms=2000)
                self.assertEqual(receipt["status"], expected, receipt)
                release_retry(server, rpc, device, session)


class OutputValidationTests(unittest.TestCase):
    def test_strict_mode_fails_an_output_that_does_not_match_its_schema(self) -> None:
        server, rpc, device, bridge = arm_server(strict=True)
        bridge.outputs[JOINTS] = {"reached": "yes"}
        session = open_session(rpc, device)
        receipt = rpc("mhs.command", session_id=session, capability_id=JOINTS,
                      input={"joint_positions": [0.1]}, deadline_ms=2000)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(error_code(receipt), "MHS.CAPABILITY.OUTPUT_INVALID")
        self.assertIsNone(receipt["output"])
        self.assertTrue(receipt["error"]["details"]["errors"])
        self.assertEqual(bridge.count(JOINTS), 1, "the native call ran; its effect may have happened")
        self.assertEqual(STORE.validate(receipt, "receipt.schema.json"), [])

    def test_an_extension_is_checked_against_its_own_output_schema(self) -> None:
        server, rpc, device, bridge = arm_server(strict=True)
        bridge.outputs[EXT] = {"ping": 1}
        session = open_session(rpc, device)
        receipt = rpc("mhs.command", session_id=session, capability_id=EXT, input={}, deadline_ms=2000)
        self.assertEqual(error_code(receipt), "MHS.CAPABILITY.OUTPUT_INVALID")
        bridge.outputs[EXT] = {"pong": True}
        receipt = rpc("mhs.command", session_id=session, capability_id=EXT, input={}, deadline_ms=2000)
        self.assertEqual(receipt["status"], "completed", receipt)

    def test_compatibility_mode_warns_once_per_capability_and_completes(self) -> None:
        server, rpc, device, bridge = arm_server(strict=None)
        bridge.outputs[JOINTS] = {"reached": "yes"}
        session = open_session(rpc, device)
        with RecordWarnings() as warned:
            for _ in range(3):
                receipt = rpc("mhs.command", session_id=session, capability_id=JOINTS,
                              input={"joint_positions": [0.1]}, deadline_ms=2000)
                self.assertEqual(receipt["status"], "completed", receipt)
        texts = [text for text in strict_warnings(warned) if "OUTPUT_INVALID" in text]
        self.assertEqual(len(texts), 1, texts)
        self.assertIn(JOINTS, texts[0])

    def test_non_finite_floats_become_null_and_are_listed(self) -> None:
        for strict in (True, None):
            with self.subTest(strict=strict):
                server, rpc, device, bridge = arm_server(strict=strict)
                bridge.outputs[JOINTS] = {"reached": True, "joint_positions": [math.nan, 1.0],
                                          "tolerance_rad": math.inf}
                session = open_session(rpc, device)
                before = rpc("mhs.resource.read", session_id=session, deadline_ms=1000)["revision"]
                receipt = rpc("mhs.command", session_id=session, capability_id=JOINTS,
                              input={"joint_positions": [0.1]}, deadline_ms=2000)
                json.dumps(receipt, allow_nan=False)  # the receipt is JSON
                self.assertEqual(receipt["x-vendor"]["non_finite_output"],
                                 ["/joint_positions/0", "/tolerance_rad"])
                if strict:
                    self.assertEqual(receipt["status"], "failed", receipt)
                    self.assertEqual(error_code(receipt), "MHS.CAPABILITY.OUTPUT_INVALID")
                    self.assertEqual(receipt["error"]["details"]["non_finite"],
                                     ["/joint_positions/0", "/tolerance_rad"])
                else:
                    self.assertEqual(receipt["status"], "completed", receipt)
                    self.assertEqual(receipt["output"]["joint_positions"], [None, 1.0])
                    self.assertIsNone(receipt["output"]["tolerance_rad"])
                # WP-04 4d (plan 3.7): the bridge changed no state, so the
                # revision stays (before 4b it was bumped twice; 4b once).
                self.assertEqual(receipt["state_revision_after"], before, "no state change: no bump")
                verified = rpc("mhs.evidence.verify")
                self.assertTrue(verified["valid"], verified)
                exported = rpc("mhs.evidence.export")
                self.assertIn(receipt["receipt_id"], json.dumps(exported))

    def test_a_cancelled_or_valid_output_is_not_touched(self) -> None:
        server, rpc, device, bridge = arm_server(strict=True)
        session = open_session(rpc, device)
        receipt = rpc("mhs.command", session_id=session, capability_id=JOINTS,
                      input={"joint_positions": [0.5, 0.25]}, deadline_ms=2000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"reached": True, "joint_positions": [0.5, 0.25]})
        self.assertNotIn("non_finite_output", receipt.get("x-vendor") or {})


class HybridAuthorityTests(unittest.TestCase):
    """4a1 follow-up: strict mode does not trust a declared verb on a hardware-authority resource."""

    def _hybrid(self, strict):
        peek = Capability("x-cap.test.peek.v1", "arm", verb="read", input_schema={"type": "object"},
                          output_schema={"type": "object"})
        device = arm_device(mode="hybrid", capabilities=arm_capabilities(extra=[peek]))
        return arm_server(device, strict=strict)

    def test_an_extension_declared_read_cannot_touch_hardware_authority(self) -> None:
        server, rpc, device, bridge = self._hybrid(True)
        session = open_session(rpc, device)
        receipt = rpc("mhs.command", session_id=session, capability_id="x-cap.test.peek.v1", input={},
                      deadline_ms=2000)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(bridge.count("x-cap.test.peek.v1"), 0)
        receipt = rpc("mhs.command", session_id=session, capability_id=DESCRIBE, input={}, deadline_ms=2000)
        self.assertEqual(receipt["status"], "completed", "a catalogued read class may")

    def test_compatibility_mode_keeps_the_declared_verb(self) -> None:
        server, rpc, device, bridge = self._hybrid(None)
        session = open_session(rpc, device)
        receipt = rpc("mhs.command", session_id=session, capability_id="x-cap.test.peek.v1", input={},
                      deadline_ms=2000)
        self.assertEqual(receipt["status"], "completed", receipt)


class OperationOwnershipTests(unittest.TestCase):
    """SDK-08: operations.get / cancel must not reveal another principal's operations."""

    def _run(self, strict):
        server, rpc, device, bridge = arm_server(strict=strict)
        alice = open_session(rpc, device, principal={"id": "agent:alice", "kind": "agent"})
        alice2 = open_session(rpc, device, principal={"id": "agent:alice", "kind": "agent"})
        mallory = open_session(rpc, device, principal={"id": "agent:mallory", "kind": "agent"})
        receipt = rpc("mhs.command", session_id=alice, capability_id=JOINTS,
                      input={"joint_positions": [0.1]}, deadline_ms=2000)
        operation_id = receipt["operation_id"]
        return rpc, operation_id, alice2, mallory

    def test_strict_mode_hides_another_principals_operation(self) -> None:
        rpc, operation_id, alice2, mallory = self._run(True)
        self.assertEqual(rpc("mhs.operations.get", session_id=alice2, operation_id=operation_id,
                             deadline_ms=1000)["operation_id"], operation_id)
        for method in ("mhs.operations.get", "mhs.operations.cancel"):
            response = rpc.raw(method, session_id=mallory, operation_id=operation_id, deadline_ms=1000)
            self.assertEqual(error_code(response), "MHS.OPERATION.UNKNOWN", response)

    def test_compatibility_mode_is_unchanged(self) -> None:
        rpc, operation_id, alice2, mallory = self._run(None)
        self.assertEqual(rpc("mhs.operations.get", session_id=mallory, operation_id=operation_id,
                             deadline_ms=1000)["operation_id"], operation_id)


if __name__ == "__main__":
    unittest.main()

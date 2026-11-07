"""Blocked ALOHA package: preserve the gate and test explicit safety refusal.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = str(HERE / "site-limits.example.json")
STEP = "x-cap.tonyzhaozh.step.v1"
RESET = "x-cap.tonyzhaozh.reset.v1"
HOLD = "x-cap.tonyzhaozh.hold.v1"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


def _step_payload(left_first=0.1):
    return {
        "left_arm": [left_first, -0.2, 0.3, 0.0, -0.1, 0.0],
        "left_gripper": 0.8,
        "right_arm": [0.0, -0.3, 0.4, 0.0, -0.1, 0.0],
        "right_gripper": 0.2,
    }


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        # This is deliberately not an accepted package. The gate must expose
        # the missing native stop instead of treating a cached-position
        # publication as proof of stopping.
        self.assertIn("G3", report["failed"], report)


class AlohaCases(unittest.TestCase):
    def serve(self, overlay=True):
        server = load(HERE, backend="fake", site_limits=OVERLAY if overlay else None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_step_action_moves_both_arms_and_returns_the_observation(self) -> None:
        client = self.serve()
        before = self.state(client)
        receipt = client.invoke(STEP, _step_payload(), **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(len(receipt["output"]["qpos"]), 14)
        self.assertEqual(len(receipt["output"]["qvel"]), 14)
        self.assertEqual(receipt["output"]["step_type"], "MID")
        after = self.state(client)
        self.assertNotEqual(before["left_arm_qpos"], after["left_arm_qpos"])
        self.assertEqual(after["gripper_pose"], [0.8, 0.2])

    def test_the_step_action_is_refused_until_the_operator_supplies_the_arm_envelope(self) -> None:
        client = self.serve(overlay=False)
        before = self.state(client)
        receipt = client.invoke(STEP, _step_payload(), **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["left_arm_qpos"], before["left_arm_qpos"])

    def test_an_arm_value_outside_the_example_envelope_is_refused(self) -> None:
        client = self.serve()
        before = self.state(client)
        receipt = client.invoke(STEP, _step_payload(left_first=1.6), **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["left_arm_qpos"], before["left_arm_qpos"])

    def test_the_gripper_pose_write_moves_both_grippers(self) -> None:
        client = self.serve()
        written = client.write("main", {"gripper_pose": [0.0, 1.0]}, **self.ids)
        self.assertEqual(written["status"], "completed", written)
        self.assertEqual(self.state(client)["gripper_pose"], [0.0, 1.0])

    def test_a_gripper_pose_above_one_is_refused(self) -> None:
        client = self.serve()
        written = client.write("main", {"gripper_pose": [1.1, 0.5]}, **self.ids)
        self.assertEqual(written["status"], "rejected", written)
        self.assertEqual(written["error"]["mhs_code"], ENVELOPE)

    def test_the_reset_action_returns_the_first_observation(self) -> None:
        client = self.serve()
        client.invoke(STEP, _step_payload(), **self.ids)
        reset = client.invoke(RESET, {}, **self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(reset["output"]["step_type"], "FIRST")
        self.assertEqual(len(reset["output"]["qpos"]), 14)

    def test_the_hold_action_reports_unavailable_without_claiming_success(self) -> None:
        client = self.serve()
        before = self.state(client)
        held = client.invoke(HOLD, {}, **self.ids)
        self.assertEqual(held["status"], "failed", held)
        self.assertEqual(held["error"]["mhs_code"], UNREACHED)
        self.assertEqual(self.state(client), before)
        moved = client.invoke(STEP, _step_payload(), **self.ids)
        self.assertEqual(moved["status"], "completed", moved)

    def test_the_fake_estop_is_software_only_with_no_declared_safe_state(self) -> None:
        client = self.serve()
        estop = client.estop("test", **self.ids)
        # The SDK serves backend=fake as simulated: a software latch suffices
        # for that fake view. This receipt proves no native/hardware stopping.
        self.assertEqual(estop["status"], "completed", estop)
        self.assertEqual(estop["output"]["estop"], "software_only")
        self.assertTrue(estop["output"]["latched"])
        self.assertEqual(estop["output"]["safe_state"]["achieved_by"], [])
        self.assertEqual(estop["output"]["safe_state"]["description"], "no declared safe state")
        refused = client.invoke(STEP, _step_payload(), **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        # The unavailable hold is not a safe-state exemption from the latch.
        refused_hold = client.invoke(HOLD, {}, **self.ids)
        self.assertEqual(refused_hold["status"], "rejected", refused_hold)
        self.assertEqual(refused_hold["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()

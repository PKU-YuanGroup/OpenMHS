"""Acceptance run of the Yahboom M3 Pro package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  Everything runs on the fake backend in fake.py; nothing here ran on
a robot.  The fake's ``_last_arm_deg`` and ``_last_twist`` are test data recorded by the fake.
"""

import json
import math
import tempfile
import unittest
from pathlib import Path

from mhs.adapter import LoadError, load_driver
from mhs.driver import build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
HOME_DEG = (90, 120, 0, 0, 90, 180)
VALID = [0.0, 0.0, 0.0, 0.0, 0.0, -0.5]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class YahboomCases(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        self.fake = driver.native
        self.client = client_for(server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return self.client

    def move_joints(self, values):
        return self.client.invoke("cap.motion.joint_position.v1", {"joint_positions": values}, **self.ids)

    def gripper(self, open_value):
        return self.client.invoke("x-cap.strands-labs.gripper.v1", {"open": open_value}, **self.ids)

    def home(self):
        return self.client.invoke("x-cap.strands-labs.home.v1", {}, **self.ids)

    def drive(self, linear_x=0.1, linear_y=0.0, angular_z=0.0, duration_s=0.2):
        return self.client.invoke("x-cap.strands-labs.mobile-base.v1",
                                  {"linear_x": linear_x, "linear_y": linear_y,
                                   "angular_z": angular_z, "duration_s": duration_s}, **self.ids)

    def stop(self):
        return self.client.invoke("cap.motion.stop.v1", {}, **self.ids)

    def state(self):
        return self.client.read("main", **self.ids)["state"]

    # -- arm -----------------------------------------------------------------------------------------------------
    def test_a_joint_move_is_converted_to_servo_degrees_and_observable(self) -> None:
        self.serve()
        receipt = self.move_joints(VALID)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["reached"])
        for got, want in zip(receipt["output"]["joint_positions"][:5], VALID[:5], strict=True):
            self.assertAlmostEqual(got, want, places=9)
        self.assertAlmostEqual(receipt["output"]["joint_positions"][5], VALID[5], places=2)
        self.assertEqual(self.fake._last_arm_deg[:5], (90, 90, 90, 90, 90))
        self.assertEqual(self.fake._last_arm_deg[5], 131)
        pose = self.state()["commanded_arm_pose"]
        self.assertAlmostEqual(pose["arm1.pos"], 0.0, places=6)
        self.assertAlmostEqual(pose["gripper.pos"], -0.5, places=2)

    def test_the_joint_limits_are_per_joint_and_refuse_before_the_fake(self) -> None:
        self.serve()
        too_high = list(VALID)
        too_high[1] = 1.7
        refused = self.move_joints(too_high)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE))
        self.assertEqual(refused["error"]["details"]["path"], "joint_positions[1]")
        self.assertEqual(refused["error"]["details"]["element_name"], "joint2")
        closed_too_far = list(VALID)
        closed_too_far[5] = 0.5
        refused = self.move_joints(closed_too_far)
        self.assertEqual(refused["error"]["details"]["path"], "joint_positions[5]")
        self.assertIsNone(self.fake._last_arm_deg)

    def test_the_gripper_and_home_use_the_upstream_servo_endpoints(self) -> None:
        self.serve()
        self.assertEqual(self.gripper(False)["output"], {"open": False})
        self.assertEqual(self.fake._last_arm_deg[5], 30)
        self.assertEqual(self.gripper(True)["output"], {"open": True})
        self.assertEqual(self.fake._last_arm_deg[5], 180)
        self.assertEqual(self.home()["status"], "completed")
        self.assertEqual(self.fake._last_arm_deg, HOME_DEG)

    # -- base ----------------------------------------------------------------------------------------------------
    def test_a_base_move_holds_the_twist_and_sends_the_zero_twist(self) -> None:
        self.serve()
        receipt = self.drive()
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["held_s"], 0.2)
        self.assertTrue(receipt["output"]["stopped"])
        self.assertEqual(self.fake._last_twist, {"linear.x": 0.0, "linear.y": 0.0, "angular.z": 0.0})

    def test_the_base_ceilings_are_refused_before_the_fake(self) -> None:
        self.serve()
        for kwargs in ({"linear_x": 1.1}, {"linear_y": -1.1}, {"angular_z": 5.1}):
            receipt = self.drive(**kwargs)
            self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("rejected", ENVELOPE), kwargs)
        self.assertIsNone(self.fake._last_twist)
        self.assertEqual(self.stop()["status"], "completed")
        self.assertTrue(self.stop()["output"]["stopped"])

    def test_a_deceleration_profile_is_refused_because_the_upstream_stop_is_immediate(self) -> None:
        self.serve()
        receipt = self.client.invoke("cap.motion.stop.v1", {"deceleration": 2.0}, **self.ids)
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]),
                         ("failed", "MHS.DEVICE.PRECONDITION_UNMET"))
        self.assertEqual(self.fake._stop_calls, 0)

    # -- safety --------------------------------------------------------------------------------------------------
    def test_the_estop_reaches_the_native_stop_and_latches(self) -> None:
        self.serve()
        before = self.fake._stop_calls
        self.assertEqual(self.client.estop("test", **self.ids)["status"], "completed")
        self.assertGreaterEqual(self.fake._stop_calls, before + 1)
        refused = self.move_joints(VALID)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ESTOP))
        self.assertEqual(self.client.reset(**self.ids)["status"], "completed")
        self.assertEqual(self.move_joints(VALID)["status"], "completed")

    # -- reference and loader ------------------------------------------------------------------------------------
    def test_the_reference_declares_the_safe_state_and_the_stop(self) -> None:
        reference = json.loads((HERE / "reference.json").read_text(encoding="utf-8"))
        safety = reference["safety"]
        self.assertEqual(reference["device"]["risk"], "R2")
        self.assertEqual(safety["estop"]["native"], "stop_task")
        self.assertEqual(safety["safe_state"]["achieved_by"], ["cap.motion.stop.v1"])
        self.assertEqual(safety["operator_required"], [])
        self.assertNotIn("physical_ref", safety["estop"])

    def test_the_hardware_backend_is_refused_until_a_human_signs_the_review(self) -> None:
        with tempfile.TemporaryDirectory() as state_dir:
            with self.assertRaises(LoadError) as caught:
                load_driver(HERE, backend="hardware", allow_hardware=True, state_dir=state_dir)
        self.assertEqual(caught.exception.reason, "review_required")


if __name__ == "__main__":
    unittest.main()

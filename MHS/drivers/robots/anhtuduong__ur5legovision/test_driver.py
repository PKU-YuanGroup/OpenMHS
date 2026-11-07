"""Acceptance run of the UR5LegoVision ROS 1 package: the gate plus repository cases.

The cases exercise the pinned wire shapes: the six-joint ``MoveJoints``
service call, the gripper ``generic_float`` call, the two explicit observation
subscriptions, the Gazebo pause/resume calls, the failure paths through the
actual native stop, and the latch.  Service acknowledgements are not measured
arrival, grasp or quiescence.  Add cases, never remove ``check_driver``.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import DriverFailed, OutcomeUnknown, build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
MOVE_JOINTS = "x-cap.anhtuduong.move_joints.v1"
MOVE_GRIPPER = "x-cap.anhtuduong.move_gripper.v1"
PAUSE = "x-cap.anhtuduong.pause.v1"
RESUME = "x-cap.anhtuduong.resume.v1"
JOINT_STATE = "x-cap.anhtuduong.joint_state.v1"
EE_POSE = "x-cap.anhtuduong.ee_pose.v1"

_GRIPPER_OVERLAY = {
    "openmhs": "0.9",
    "site": "test-only gripper envelope; not a device limit",
    "devices": {
        "mhs://localhost/ur5legovision": {
            MOVE_GRIPPER: {
                "diameter_mm": {"min": 0, "max": 100, "source": "operator"},
            },
        },
    },
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Ur5LegoVisionCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def serve(self, site_limits=None):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    @staticmethod
    def calls(driver):
        return [message for message in driver.native.sent if message.get("op") == "call_service"]

    def test_move_joints_maps_six_positions_to_the_upstream_service(self):
        driver = self.driver()
        target = [0.0, -0.5, 1.0, 0.0, 0.0, 0.0]
        receipt = driver.call(MOVE_JOINTS, {"joint_positions": target})
        self.assertEqual(receipt, {"success": True})
        call = self.calls(driver)[-1]
        self.assertEqual(call["service"], "/ur5/move_joints")
        self.assertEqual(call["type"], "ros_impedance_controller/MoveJoints")
        self.assertEqual(call["args"]["q_des"], target)
        self.assertEqual(call["args"]["dt"], 0.001)
        self.assertEqual(call["args"]["v_des"], 0.6)

    def test_joint_state_observation_subscribes_and_maps_the_message(self):
        driver = self.driver()
        receipt = driver.call(JOINT_STATE, {})
        self.assertEqual(len(receipt["joint_names"]), 6)
        self.assertEqual(len(receipt["joint_positions"]), 6)
        self.assertEqual(len(receipt["joint_velocities"]), 6)
        self.assertEqual(len(receipt["joint_efforts"]), 6)
        subscriptions = [message for message in driver.native.sent if message.get("op") == "subscribe"]
        self.assertEqual(subscriptions[-1]["topic"], "/ur5/joint_states")
        self.assertEqual(subscriptions[-1]["type"], "sensor_msgs/JointState")

    def test_end_effector_pose_observation_subscribes_and_maps_the_message(self):
        driver = self.driver()
        receipt = driver.call(EE_POSE, {})
        self.assertEqual(set(receipt["position"]), {"x", "y", "z"})
        self.assertEqual(set(receipt["orientation"]), {"x", "y", "z", "w"})
        subscriptions = [message for message in driver.native.sent if message.get("op") == "subscribe"]
        self.assertEqual(subscriptions[-1]["topic"], "/ur5/ee_pose")
        self.assertEqual(subscriptions[-1]["type"], "geometry_msgs/Pose")

    def test_pause_and_resume_reach_the_gazebo_services(self):
        driver = self.driver()
        self.assertEqual(driver.call(PAUSE, {}), {"paused": True})
        self.assertTrue(driver.native.paused)
        self.assertEqual(driver.call(RESUME, {}), {"resumed": True})
        self.assertFalse(driver.native.paused)
        self.assertEqual([call["service"] for call in self.calls(driver)],
                         ["/gazebo/pause_physics", "/gazebo/unpause_physics"])

    def test_gripper_requires_an_operator_envelope(self):
        driver, client = self.serve()
        refused = client.invoke(MOVE_GRIPPER, {"diameter_mm": 30.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(driver.native.gripper_calls, [])

    def test_gripper_with_operator_envelope_reaches_the_service(self):
        driver, client = self.serve(_GRIPPER_OVERLAY)
        receipt = client.invoke(MOVE_GRIPPER, {"diameter_mm": 30.0}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"moved": True, "diameter_mm": 30.0})
        self.assertEqual([call["service"] for call in self.calls(driver)], ["/ur5/move_gripper"])
        self.assertEqual(self.calls(driver)[0]["args"], {"data": 30.0})

    def test_out_of_envelope_joint_is_refused_before_the_service(self):
        driver, client = self.serve()
        receipt = client.invoke(MOVE_JOINTS, {"joint_positions": [7.0, 0.0, 0.0, 0.0, 0.0, 0.0]},
                                **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(driver.native.move_joint_calls, [])

    def test_failed_service_response_is_a_failure(self):
        driver = self.driver()
        driver.native.fail_move_service = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call(MOVE_JOINTS, {"joint_positions": [0.0, -0.5, 1.0, 0.0, 0.0, 0.0]})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_rejected_application_response_is_a_failure(self):
        driver = self.driver()
        driver.native.reject_move_application = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call(MOVE_JOINTS, {"joint_positions": [0.0, -0.5, 1.0, 0.0, 0.0, 0.0]})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_malformed_service_response_is_an_unknown_outcome(self):
        driver = self.driver()
        driver.native.malformed_move_response = True
        with self.assertRaises(OutcomeUnknown) as caught:
            driver.call(MOVE_JOINTS, {"joint_positions": [0.0, -0.5, 1.0, 0.0, 0.0, 0.0]})
        self.assertEqual(caught.exception.code, "MHS.OUTCOME.UNKNOWN")

    def test_native_estop_reaches_pause_and_reports_engaged(self):
        driver = self.driver()
        receipt = driver.estop("test")
        self.assertEqual(receipt["estop"], "engaged")
        self.assertEqual(receipt["performed"], ["/gazebo/pause_physics"])
        self.assertTrue(driver.native.paused)
        self.assertEqual([call["service"] for call in self.calls(driver)], ["/gazebo/pause_physics"])

    def test_native_estop_refuses_failed_refused_and_malformed_pause_replies(self):
        for failure in ("fail_pause_service", "reject_pause_application", "malformed_pause_response"):
            with self.subTest(failure=failure):
                driver = self.driver()
                setattr(driver.native, failure, True)
                with self.assertRaises(DriverFailed) as caught:
                    driver.estop("negative-path test")
                self.assertEqual(caught.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_server_estop_latches_and_reset_allows_an_explicit_resume(self):
        driver, client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        refused = client.invoke(MOVE_JOINTS, {"joint_positions": [0.0, -0.5, 1.0, 0.0, 0.0, 0.0]},
                                **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertIn("/gazebo/pause_physics", [call["service"] for call in self.calls(driver)])
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        # SAFE-042: the reset releases only the latch.  Unpausing would let an interrupted upstream
        # motion loop continue, so Gazebo stays paused until the explicit resume command.
        self.assertTrue(driver.native.paused)
        self.assertNotIn("/gazebo/unpause_physics", [call["service"] for call in self.calls(driver)])
        resumed = client.invoke(RESUME, {}, **self.ids)
        self.assertEqual(resumed["status"], "completed", resumed)
        self.assertFalse(driver.native.paused)
        self.assertEqual([call["service"] for call in self.calls(driver)][-1], "/gazebo/unpause_physics")


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the OpenMANIPULATOR ROS package: the gate plus repository cases.

Add cases, never remove the check_driver call.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, OutcomeUnknown
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ARM = "x-cap.robotis-git.arm_trajectory.v1"
GRIPPER = "x-cap.robotis-git.gripper_command.v1"
JOINT_STATE = "x-cap.robotis-git.joint_state.v1"
TORQUE_OFF = "x-cap.robotis-git.torque_off.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ARM_ACTION = "/arm_controller/follow_joint_trajectory"
GRIPPER_ACTION = "/gripper_controller/gripper_cmd"
TORQUE_SERVICE = "/dynamixel_hardware_interface/set_dxl_torque"


def arm_payload(x: float = 0.0) -> dict:
    return {"points": [{"positions": [x, 0.0, 0.0, 0.0, 0.0]}]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        # The selected native stop/lifecycle is unproven. Keep running the
        # full stock gate and require its specific safety refusal.
        self.assertEqual(report["failed"], ["G3"], report)
        codes = {f["code"] for g in report["gates"] for f in g["findings"]}
        self.assertIn("G3.NO_ESTOP", codes)
        self.assertIn("G3.NO_SAFE_STATE", codes)


class OpenManipulatorCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def serve(self, overlay=None):
        server = load(HERE, backend="fake", site_limits=overlay)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    @staticmethod
    def example_overlay() -> dict:
        return json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))

    def test_arm_goal_reaches_the_controller_and_changes_joint_state(self) -> None:
        driver = self.driver()
        before = driver.read("main")["joint_positions"]
        output = driver.call(ARM, arm_payload(0.25))
        self.assertEqual(output["error_code"], 0)
        self.assertEqual(output["error_string"], "")
        after = driver.read("main")["joint_positions"]
        self.assertNotEqual(before, after)
        sent = [message for message in driver.native.sent
                if message.get("op") == "send_action_goal" and message.get("action") == ARM_ACTION]
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["action_type"], "control_msgs/action/FollowJointTrajectory")
        self.assertEqual(sent[0]["args"]["trajectory"]["joint_names"],
                         ["joint1", "joint2", "joint3", "joint4", "joint5"])
        self.assertEqual(sent[0]["args"]["trajectory"]["points"][0]["positions"],
                         [0.25, 0.0, 0.0, 0.0, 0.0])

    def test_joint_state_observation_returns_the_three_reported_arrays(self) -> None:
        driver = self.driver()
        output = driver.call(JOINT_STATE, {})
        self.assertEqual(output["name"][:5],
                         ["joint1", "joint2", "joint3", "joint4", "joint5"])
        self.assertEqual(len(output["name"]), len(output["position"]))
        self.assertEqual(len(output["name"]), len(output["velocity"]))

    def test_gripper_wire_carries_position_and_max_effort(self) -> None:
        driver = self.driver()
        output = driver.call(GRIPPER, {"position": 0.5, "max_effort": 5.0})
        self.assertTrue(output["reached_goal"])
        self.assertFalse(output["stalled"])
        sent = [message for message in driver.native.sent
                if message.get("op") == "send_action_goal" and message.get("action") == GRIPPER_ACTION]
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["action_type"], "control_msgs/action/GripperCommand")
        self.assertEqual(sent[0]["args"]["command"], {"position": 0.5, "max_effort": 5.0})

    def test_gripper_is_refused_until_the_operator_overlay_fills_its_limits(self) -> None:
        client = self.serve()
        receipt = client.invoke(GRIPPER, {"position": 0.5, "max_effort": 5.0}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)

    def test_example_overlay_admits_the_gripper_and_refuses_out_of_range_values(self) -> None:
        client = self.serve(self.example_overlay())
        accepted = client.invoke(GRIPPER, {"position": 0.5, "max_effort": 5.0}, **self.ids)
        self.assertEqual(accepted["status"], "completed", accepted)
        self.assertTrue(accepted["output"]["reached_goal"])
        position = client.invoke(GRIPPER, {"position": 2.0, "max_effort": 5.0}, **self.ids)
        self.assertEqual(position["status"], "rejected", position)
        self.assertEqual(position["error"]["mhs_code"], ENVELOPE)
        effort = client.invoke(GRIPPER, {"position": 0.5, "max_effort": 11.0}, **self.ids)
        self.assertEqual(effort["status"], "rejected", effort)
        self.assertEqual(effort["error"]["mhs_code"], ENVELOPE)

    def test_failed_torque_service_is_not_an_acknowledged_request(self) -> None:
        driver = self.driver()
        driver.native.fail_torque_service = True
        with self.assertRaises(DriverFailed):
            driver.call(TORQUE_OFF, {})

    def test_torque_application_rejection_is_not_reported_as_acknowledged(self) -> None:
        driver = self.driver()
        driver.native.fail_torque_application = True
        with self.assertRaises(DriverFailed):
            driver.call(TORQUE_OFF, {})
        sent = [message for message in driver.native.sent
                if message.get("op") == "call_service" and message.get("service") == TORQUE_SERVICE]
        self.assertTrue(sent)
        self.assertIs(sent[-1]["args"]["data"], False)

    def test_arm_terminal_failure_is_not_reported_as_completed(self) -> None:
        driver = self.driver()
        driver.native.fail_arm_result = True
        with self.assertRaises(OutcomeUnknown) as caught:
            driver.call(ARM, arm_payload())
        self.assertEqual(caught.exception.code, "MHS.OUTCOME.UNKNOWN")

    def test_unproven_estop_does_not_send_torque_off_or_exempt_ordinary_control(self) -> None:
        driver = self.driver()
        result = driver.estop("unproven stop")
        self.assertNotEqual(result.get("estop"), "engaged")
        self.assertFalse(any(m.get("service") == TORQUE_SERVICE for m in driver.native.sent))
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["output"]["estop"], "software_only", receipt)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertIs(receipt["output"]["safe_state_achieved"], False, receipt)
        for cap, args in ((ARM, arm_payload()), (TORQUE_OFF, {})):
            refused = client.invoke(cap, args, **self.ids)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_arm_nonzero_application_code_is_rejected_after_valid_transport_result(self):
        driver = self.driver()
        driver.native.fail_arm_application = True
        with self.assertRaises(DriverFailed):
            driver.call(ARM, arm_payload())
        self.assertEqual(len(driver.native.arm_goals), 1)

    def test_gripper_false_reached_goal_is_rejected_after_valid_transport_result(self):
        driver = self.driver()
        driver.native.fail_gripper_application = True
        with self.assertRaises(DriverFailed):
            driver.call(GRIPPER, {"position": 0.5, "max_effort": 5.0})
        self.assertEqual(len(driver.native.gripper_goals), 1)


if __name__ == "__main__":
    unittest.main()

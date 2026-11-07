"""Acceptance run of the Franka Hand ROS 1 package: the gate plus repository-specific cases.

The cases exercise the actionlib wire shapes cited in ``driver.py``: the
generated goal/result wrappers, the application success predicate, a failed
application result and a malformed terminal result. The private candidate binds
StopAction as a native safety action while retaining unknown outcomes and the
unchanged hardware-review requirement.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import DriverFailed, OutcomeUnknown
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FrankaGripperCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_finger_positions_are_read_from_joint_states(self):
        driver = self.driver()
        state = driver.read("main", ["finger_positions"])
        self.assertEqual(state, {"finger_positions": [0.02, 0.02]})
        sent = [message for message in driver.native.sent if message.get("op") == "subscribe"]
        self.assertIn("/franka_gripper/joint_states", [message["topic"] for message in sent])

    def test_grasp_maps_millimetres_to_metres_and_force_newtons(self):
        driver = self.driver()
        receipt = driver.call("cap.manipulation.grasp.v1", {"width": 30.0, "force": 5.0})
        self.assertEqual(receipt, {"grasped": True})
        self.assertEqual(driver.native.goals[-1]["action"], "/franka_gripper/grasp")
        self.assertEqual(driver.native.goals[-1]["goal"], {
            "width": 0.03, "force": 5.0, "speed": 0.1,
            "epsilon": {"inner": 0.005, "outer": 0.005},
        })
        self.assertAlmostEqual(driver.native.force_applied, 5.0)

    def test_move_maps_width_to_the_upstream_metre_goal(self):
        driver = self.driver()
        receipt = driver.call("x-cap.frankarobotics.move.v1", {"width": 40.0, "speed": 0.1})
        self.assertEqual(receipt, {"success": True, "error": "", "requested_speed_m_s": 0.1})
        self.assertEqual(driver.native.goals[-1]["goal"], {"width": 0.04, "speed": 0.1})
        self.assertEqual(driver.native.finger_positions, [0.02, 0.02])

    def test_homing_and_stop_use_their_own_action_endpoints(self):
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.frankarobotics.home.v1", {}),
                         {"success": True, "error": ""})
        self.assertEqual(driver.call("x-cap.frankarobotics.stop.v1", {}),
                         {"success": True, "error": ""})
        self.assertEqual([goal["action"] for goal in driver.native.goals],
                         ["/franka_gripper/homing", "/franka_gripper/stop"])
        self.assertEqual(driver.native.force_applied, 0.0)

    def test_unsuccessful_grasp_is_a_completed_false_result(self):
        driver = self.driver()
        driver.native.fail_grasp_application = True
        self.assertEqual(driver.call("cap.manipulation.grasp.v1", {"width": 30.0, "force": 5.0}),
                         {"grasped": False})

    def test_failed_move_application_is_a_failed_receipt(self):
        driver = self.driver()
        driver.native.fail_move_service = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.frankarobotics.move.v1", {"width": 40.0, "speed": 0.1})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_malformed_stop_result_is_an_unknown_outcome(self):
        driver = self.driver()
        driver.native.malformed_stop_result = True
        with self.assertRaises(OutcomeUnknown) as caught:
            driver.call("x-cap.frankarobotics.stop.v1", {})
        self.assertEqual(caught.exception.code, "MHS.OUTCOME.UNKNOWN")

    def test_native_stop_action_has_no_fabricated_physical_estop(self):
        driver = self.driver()
        self.assertEqual(type(driver).safety_bindings["estop"]["action"], "/franka_gripper/stop")
        self.assertIsNone(type(driver).estop_physical_ref)
        self.assertEqual(type(driver).backends, {"fake": ".fake:FakeFrankaGripper"})


if __name__ == "__main__":
    unittest.main()

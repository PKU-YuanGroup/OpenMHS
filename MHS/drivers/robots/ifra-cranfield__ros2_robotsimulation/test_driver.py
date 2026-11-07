"""Acceptance run and repository-specific cases for the IFRA ROS 2 actions.

The cases exercise the four pinned ROS 2 native action wire shapes through the
package's ROS-free recording fake.  They are fake-only contract checks; no ROS
graph, Gazebo world, MoveIt planner or hardware is contacted.  The stock gate
also reports the package's blocked condition: the pinned action servers expose
no acknowledged stop, so the G6 e-stop check fails even though the action
terminals are exercised here.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import DriverFailed, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
MOVE_J = "x-cap.ifra-cranfield.move-j.v1"
MOVE_JS = "x-cap.ifra-cranfield.move-js.v1"
MOVE_XYZ = "x-cap.ifra-cranfield.move-xyz.v1"
MOVE_G = "x-cap.ifra-cranfield.move-g.v1"


def _joints(count):
    return {f"joint{index}": 0.0 for index in range(1, count + 1)}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ActionCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def goals(self, driver):
        return [message for message in driver.native.sent
                if message.get("op") == "send_action_goal"]

    def test_move_j_sends_the_pinned_goal_and_succeeds(self) -> None:
        driver = self.driver()
        receipt = driver.call(MOVE_J, {**_joints(6), "speed": 0.5})
        self.assertEqual(receipt["result"], "MoveJ:SUCCESS")
        goal = self.goals(driver)[-1]
        self.assertEqual(goal["action"], "/MoveJ")
        self.assertEqual(goal["action_type"], "ros2_data/action/MoveJ")
        self.assertEqual(goal["args"]["goal"], _joints(6))
        self.assertEqual(goal["args"]["speed"], 0.5)

    def test_move_js_sends_seven_joint_goal(self) -> None:
        driver = self.driver()
        receipt = driver.call(MOVE_JS, {**_joints(7), "speed": 1.0})
        self.assertEqual(receipt["result"], "MoveJs:SUCCESS")
        goal = self.goals(driver)[-1]
        self.assertEqual(goal["action"], "/MoveJs")
        self.assertEqual(goal["action_type"], "ros2_data/action/MoveJs")
        self.assertEqual(goal["args"]["goal"], _joints(7))

    def test_move_xyz_sends_position_and_speed(self) -> None:
        driver = self.driver()
        receipt = driver.call(MOVE_XYZ, {
            "positionx": 0.4, "positiony": -0.1, "positionz": 0.8, "speed": 0.25,
        })
        self.assertEqual(receipt["result"], "MoveXYZ:SUCCESS")
        goal = self.goals(driver)[-1]
        self.assertEqual(goal["action"], "/MoveXYZ")
        self.assertEqual(goal["action_type"], "ros2_data/action/MoveXYZ")
        self.assertEqual(
            {key: goal["args"][key] for key in ("positionx", "positiony", "positionz", "speed")},
            {"positionx": 0.4, "positiony": -0.1, "positionz": 0.8, "speed": 0.25},
        )

    def test_move_g_sends_finger_opening(self) -> None:
        driver = self.driver()
        receipt = driver.call(MOVE_G, {"goal": 0.02})
        self.assertEqual(receipt["result"], "MoveG:SUCCESS")
        goal = self.goals(driver)[-1]
        self.assertEqual(goal["action"], "/MoveG")
        self.assertEqual(goal["action_type"], "ros2_data/action/MoveG")
        self.assertEqual(goal["args"]["goal"], 0.02)

    def test_application_failure_is_not_hidden(self) -> None:
        driver = self.driver()
        driver.native.fail_application.add("/MoveJ")
        with self.assertRaises(DriverFailed):
            driver.call(MOVE_J, {**_joints(6), "speed": 1.0})

    def test_protocol_error_is_not_hidden(self) -> None:
        driver = self.driver()
        driver.native.fail_protocol.add("/MoveXYZ")
        with self.assertRaises(Exception):
            driver.call(MOVE_XYZ, {"positionx": 0.0, "positiony": 0.0, "positionz": 0.0, "speed": 1.0})

    def test_speed_above_the_documented_maximum_is_refused(self) -> None:
        driver = self.driver()
        server = build_server(driver)
        self.addCleanup(server.close)
        client = client_for(server)
        device = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device])["session_id"]
        receipt = client.invoke(MOVE_J, {**_joints(6), "speed": 1.5},
                                device_id=device, session_id=session)
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(self.goals(driver), [])


if __name__ == "__main__":
    unittest.main()

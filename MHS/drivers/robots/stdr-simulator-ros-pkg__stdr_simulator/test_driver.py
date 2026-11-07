"""Acceptance run of the STDR simulator package: the gate plus actionlib cases.

The cases exercise the pinned ROS 1 actionlib wrapper shapes, the spawn
application predicate, the latched active-robot observation and the failed
terminal path through the fake transport.  They are fake-only contract
checks; no ROS graph, simulator, nodelet or hardware is contacted.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent
SPAWN = "x-cap.stdr-simulator-ros-pkg.spawn-robot.v1"
ACTIVE = "x-cap.stdr-simulator-ros-pkg.active-robots.v1"

#: Placeholder RobotMsg input for the fake-backed wire checks.
_ROBOT = {
    "initialPose": {"x": 1.0, "y": 2.0, "theta": 0.0},
    "footprint": {"radius": 0.2},
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class StdrCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_spawn_sends_the_pinned_actionlib_goal(self) -> None:
        driver = self.driver()
        receipt = driver.call(SPAWN, {"description": _ROBOT})
        self.assertEqual(receipt["robot"], _ROBOT)
        self.assertIn(receipt["name"], driver.native.assigned_names)
        goal = [message for message in driver.native.sent
                if message.get("op") == "publish"
                and message.get("topic") == "/stdr_server/spawn_robot/goal"][-1]
        self.assertEqual(goal["msg"]["goal"]["description"], _ROBOT)
        self.assertTrue(goal["msg"]["goal_id"]["id"])
        advertised = {message["topic"]: message["type"] for message in driver.native.sent
                      if message.get("op") == "advertise"}
        self.assertEqual(advertised["/stdr_server/spawn_robot/goal"],
                         "stdr_msgs/SpawnRobotActionGoal")
        subscribed = {message["topic"]: message["type"] for message in driver.native.sent
                      if message.get("op") == "subscribe"}
        self.assertEqual(subscribed["/stdr_server/spawn_robot/result"],
                         "stdr_msgs/SpawnRobotActionResult")
        self.assertEqual(subscribed["/stdr_server/spawn_robot/status"],
                         "actionlib_msgs/GoalStatusArray")

    def test_active_robots_is_a_fresh_subscription(self) -> None:
        driver = self.driver()
        spawned = driver.call(SPAWN, {"description": _ROBOT})
        receipt = driver.call(ACTIVE, {})
        self.assertIn(spawned["name"], [entry["name"] for entry in receipt["robots"]])
        subscribes = [message for message in driver.native.sent
                      if message.get("op") == "subscribe"
                      and message.get("topic") == "/stdr_server/active_robots"]
        self.assertTrue(subscribes)
        self.assertEqual(subscribes[-1]["type"], "stdr_msgs/RobotIndexedVectorMsg")

    def test_each_spawn_adds_a_distinct_registry_entry(self) -> None:
        driver = self.driver()
        first = driver.call(SPAWN, {"description": _ROBOT})
        second = driver.call(SPAWN, {"description": _ROBOT})
        self.assertNotEqual(first["name"], second["name"])
        robots = driver.call(ACTIVE, {})["robots"]
        names = [entry["name"] for entry in robots]
        self.assertIn(first["name"], names)
        self.assertIn(second["name"], names)

    def test_failed_spawn_aborts_the_goal(self) -> None:
        driver = self.driver()
        driver.native.fail_spawn = True
        with self.assertRaises(DriverFailed):
            driver.call(SPAWN, {"description": _ROBOT})


if __name__ == "__main__":
    unittest.main()

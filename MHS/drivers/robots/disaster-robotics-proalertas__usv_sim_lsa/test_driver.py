"""Acceptance run of this driver package (generated): add cases, never remove the harness call."""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FakeTransportContract(unittest.TestCase):
    """Repository-specific checks of the ROS-free recording fake."""

    def setUp(self) -> None:
        self.driver = load_driver(HERE, backend="fake")
        self.fake = self.driver.native

    def tearDown(self) -> None:
        self.driver.close()

    def _call(self, service: str) -> dict:
        self.fake.send({
            "op": "call_service",
            "service": service,
            "type": "std_srvs/Empty",
            "args": {},
            "id": "service-request",
        })
        return self.fake.recv()

    def test_pause_unpause_reset_acknowledgements(self) -> None:
        reply = self._call("/gazebo/pause_physics")
        self.assertEqual(reply["result"], True)
        self.assertTrue(self.fake.paused)

        reply = self._call("/gazebo/unpause_physics")
        self.assertEqual(reply["result"], True)
        self.assertFalse(self.fake.paused)

        self.fake.paused = True
        reply = self._call("/gazebo/reset_simulation")
        self.assertEqual(reply["result"], True)
        self.assertTrue(self.fake.paused, "reset must not resume physics by itself")

    def test_service_negative_paths(self) -> None:
        self.fake.fail_pause_service = True
        reply = self._call("/gazebo/pause_physics")
        self.assertEqual(reply["result"], False)

        self.fake.fail_pause_service = False
        self.fake.fail_pause_application = True
        reply = self._call("/gazebo/pause_physics")
        self.assertEqual(reply["result"], True)
        self.assertEqual(reply["values"], {"rejected": True})

        reply = self._call("/gazebo/not_a_service")
        self.assertEqual(reply["result"], False)

    def test_topic_observations_and_goal_recording(self) -> None:
        for topic, msg_type in (("/diffboat/state", "nav_msgs/Odometry"),
                                ("/diffboat/move_usv/result", "std_msgs/Float64"),
                                ("/diffboat/thruster_command", "sensor_msgs/JointState")):
            self.fake.send({"op": "subscribe", "topic": topic, "type": msg_type, "id": topic})
            reply = self.fake.recv()
            self.assertEqual(reply["op"], "publish")
            self.assertEqual(reply["topic"], topic)
            self.assertEqual(reply["id"], topic)

        self.fake.send({"op": "advertise", "topic": "/diffboat/move_usv/goal",
                        "type": "nav_msgs/Odometry", "id": "advertise"})
        self.fake.send({"op": "publish", "topic": "/diffboat/move_usv/goal", "id": "publish",
                        "msg": {"pose": {"pose": {"position": {"x": 240.0, "y": 95.0}}}}})
        self.assertEqual(self.fake.goal_x, 240.0)
        self.assertEqual(self.fake.goal_y, 95.0)


if __name__ == "__main__":
    unittest.main()

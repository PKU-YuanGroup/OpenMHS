"""Acceptance and blocker checks for the Unitree A1 Gazebo package.

The generated ``check_driver`` harness call is retained unchanged.  The
package is blocked on the upstream stop path, so that harness is expected to
report G3.DEFINITION and G7.ROS_ENDPOINT_NOT_UPSTREAM; the additional cases
below reproduce the two concrete findings without contacting ROS or hardware.
"""

import importlib.util
import unittest
from pathlib import Path

from mhs.bridge.ros import RosBridge
from mhs.bridge.ros_transport import RecordingRosTransport
from mhs.errors import MHSError
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent
CLONE = HERE.parents[3] / "robots" / "unitreerobotics" / "unitree_ros"


def _fake_class():
    spec = importlib.util.spec_from_file_location("unitree_fake", HERE / "fake.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FakeUnitreeRos


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FakeEcho(unittest.TestCase):
    def test_publish_is_echoed_in_low_state(self) -> None:
        fake = _fake_class()()
        fake.send({
            "op": "publish",
            "topic": "/a1_gazebo/FR_hip_controller/command",
            "msg": {"mode": 10, "q": 0.5, "dq": 0.0, "tau": 1.0, "Kp": 0.0, "Kd": 0.0,
                    "reserve": [0, 0, 0]},
        })
        fake.send({"op": "subscribe", "topic": "/a1_gazebo/lowState/state", "id": "probe"})
        event = fake.recv(timeout_s=0.5)
        self.assertEqual(event["op"], "publish")
        self.assertEqual(event["msg"]["motorState"][0]["q"], 0.5)
        self.assertEqual(event["msg"]["motorState"][0]["tauEst"], 1.0)
        self.assertEqual(fake.published[0]["topic"], "/a1_gazebo/FR_hip_controller/command")


class StopBlocker(unittest.TestCase):
    def test_topic_safe_state_is_refused(self) -> None:
        config = {
            "commands": {
                "x-cap.unitreerobotics.brake.v1": {
                    "topic": "/a1_gazebo/FR_hip_controller/command",
                    "type": "unitree_legged_msgs/MotorCmd",
                    "operation": "publish",
                    "safe_state": True,
                    "message": {"mode": 0, "q": 0.0, "dq": 0.0, "tau": 0.0,
                                "Kp": 0.0, "Kd": 0.0, "reserve": [0, 0, 0]},
                }
            }
        }
        with self.assertRaises(MHSError) as caught:
            RosBridge(config, transport=RecordingRosTransport())
        self.assertIn("service or action", str(caught.exception))


class PinnedSource(unittest.TestCase):
    def test_command_and_low_state_lines_exist(self) -> None:
        servo = (CLONE / "unitree_controller" / "src" / "servo.cpp").read_text()
        controller = (CLONE / "unitree_legged_control" / "src" / "joint_controller.cpp").read_text()
        urdf = (CLONE / "robots" / "a1_description" / "urdf" / "a1.urdf").read_text()
        self.assertIn("_gazebo/lowState/state", servo.splitlines()[222])
        self.assertIn('n.subscribe("command"', controller.splitlines()[89])
        self.assertIn('lower="-0.802851455917"', urdf.splitlines()[368])

    def test_composed_low_state_name_has_no_exact_literal(self) -> None:
        servo = (CLONE / "unitree_controller" / "src" / "servo.cpp").read_text()
        self.assertNotIn('"lowState/state"', servo)
        self.assertIn('"_gazebo/lowState/state"', servo)


if __name__ == "__main__":
    unittest.main()

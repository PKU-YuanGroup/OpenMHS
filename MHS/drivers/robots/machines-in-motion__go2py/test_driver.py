"""Acceptance run of the Go2 package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): its command lists are what reached the "robot".  Nothing here ran on a
real Go2.
"""

import tempfile
import unittest
from pathlib import Path

from mhs.adapter import LoadError, load_driver
from mhs.driver import build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = str(HERE / "site-limits.example.json")
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
BODY = "x-cap.machines-in-motion.go2_body_velocity.v1"
JOINTS = "x-cap.machines-in-motion.go2_joint_command.v1"
POSE = [0.0, 0.8, -1.5, 0.0, 0.8, -1.5, 0.0, 0.8, -1.5, 0.0, 0.8, -1.5]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Go2Cases(unittest.TestCase):
    def serve(self, site_limits=None):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        self.fake = driver.native
        self.client = client_for(server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return self.client

    def state(self):
        return self.client.read("main", **self.ids)["state"]

    def test_the_state_reads_what_the_interface_returns(self) -> None:
        self.serve()
        state = self.state()
        self.assertEqual(state["joint_positions"], [0.0] * 12)
        self.assertEqual(state["imu_acceleration"], [0.0, 0.0, 9.81])
        self.assertEqual(state["imu_orientation"], {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0})
        self.assertEqual(state["foot_contact_forces"], [0.0] * 4)
        self.assertEqual(state["battery_soc"], 100.0)

    def test_the_body_velocity_waits_for_the_site(self) -> None:
        self.serve()
        refused = self.client.invoke(BODY, {"forward_velocity": 0.1, "lateral_velocity": 0.0, "yaw_rate": 0.0},
                                     **self.ids)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", LIMITS_UNSET))
        self.assertEqual(self.fake._high_commands, [])

    def test_the_body_velocity_reaches_setcommands_high(self) -> None:
        self.serve(OVERLAY)
        receipt = self.client.invoke(BODY, {"forward_velocity": 0.1, "lateral_velocity": -0.2, "yaw_rate": 0.3},
                                     **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"applied": True, "forward_velocity": 0.1, "lateral_velocity": -0.2,
                                             "yaw_rate": 0.3})
        self.assertEqual(self.fake._high_commands[-1], (0.1, -0.2, 0.3))
        out = self.client.invoke(BODY, {"forward_velocity": 0.6, "lateral_velocity": 0.0, "yaw_rate": 0.0},
                                 **self.ids)
        self.assertEqual((out["status"], out["error"]["mhs_code"]), ("rejected", ENVELOPE))
        self.assertEqual(len(self.fake._high_commands), 1)

    def test_the_joint_command_is_per_joint_and_updates_the_state(self) -> None:
        self.serve()
        receipt = self.client.invoke(JOINTS, {"joint_positions": POSE, "feedforward_torques": [0.0] * 12},
                                     **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"applied": True})
        sent = self.fake._low_commands[-1]
        self.assertEqual(sent[0], POSE)
        self.assertEqual(sent[2], [150.0] * 12)
        self.assertEqual(sent[3], [3.0] * 12)
        self.assertEqual(self.state()["joint_positions"], POSE)
        too_far = list(POSE)
        too_far[2] = -2.9  # below the URDF lower bound of the calf
        refused = self.client.invoke(JOINTS, {"joint_positions": too_far, "feedforward_torques": [0.0] * 12},
                                     **self.ids)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE))
        self.assertEqual(refused["error"]["details"]["path"], "joint_positions[2]")
        self.assertEqual(len(self.fake._low_commands), 1)

    def test_the_stop_action_ends_a_velocity_command_and_damps(self) -> None:
        self.serve(OVERLAY)
        moving = self.client.invoke(BODY, {"forward_velocity": 0.1, "lateral_velocity": 0.0, "yaw_rate": 0.0},
                                    **self.ids)
        self.assertEqual(moving["status"], "completed")
        receipt = self.client.invoke("cap.motion.stop.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self.fake._high_commands[-1], (0.0, 0.0, 0.0))
        self.assertEqual(self.fake._low_commands[-1][2:4], ([0.0] * 12, [3.0] * 12))

    def test_the_estop_latches_and_reaches_the_native_stop(self) -> None:
        self.serve()
        receipt = self.client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self.fake._high_commands[-1], (0.0, 0.0, 0.0))
        self.assertEqual(self.fake._low_commands[-1][3], [3.0] * 12)
        before = (len(self.fake._high_commands), len(self.fake._low_commands))
        refused = self.client.invoke(BODY, {"forward_velocity": 0.1, "lateral_velocity": 0.0, "yaw_rate": 0.0},
                                     **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual((len(self.fake._high_commands), len(self.fake._low_commands)), before)

    def test_the_hardware_backend_is_refused_until_a_human_signs_the_review(self) -> None:
        with tempfile.TemporaryDirectory() as state_dir:
            with self.assertRaises(LoadError) as caught:
                load_driver(HERE, backend="hardware", allow_hardware=True, state_dir=state_dir)
        self.assertEqual(caught.exception.reason, "review_required")


if __name__ == "__main__":
    unittest.main()

"""Acceptance run for the evronix quadruped sim2sim package: the gate plus repository cases.

The cases exercise the velocity publication and the two observations, the companion-cited stop (the Gazebo world
pause confirmed by the E1 stall read-back of get_model_list), its failure paths, a reset that leaves the world paused
and that the package offers no unpause.  Add cases; never remove the check_driver call.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))
VELOCITY = "x-cap.evronix.velocity_command.v1"
JOINTS = "x-cap.evronix.joint_states.v1"
IMU = "x-cap.evronix.imu.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class QuadrupedCases(unittest.TestCase):
    def serve(self, *, overlay=True):
        driver = load_driver(HERE, "fake")
        server = build_server(driver, site_limits=OVERLAY if overlay else None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return driver, client, {"device_id": device_id, "session_id": session}

    def test_velocity_publication_reaches_the_declared_wire_endpoint(self) -> None:
        driver, client, ids = self.serve()
        receipt = client.invoke(VELOCITY, {
            "forward_velocity": 0.2,
            "lateral_velocity": -0.1,
            "yaw_rate": 0.3,
        }, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["published"])
        self.assertFalse(receipt["output"]["confirmed"])
        self.assertAlmostEqual(receipt["output"]["forward_velocity"], 0.2)
        self.assertAlmostEqual(receipt["output"]["lateral_velocity"], -0.1)
        self.assertAlmostEqual(receipt["output"]["yaw_rate"], 0.3)
        publishes = [item for item in driver.native.sent
                     if item.get("op") == "publish" and item.get("topic") == "/robot_velocity_command"]
        self.assertEqual(len(publishes), 1, publishes)
        position = publishes[0]["msg"]["pose"]["position"]
        self.assertAlmostEqual(position["x"], 0.2)
        self.assertAlmostEqual(position["y"], -0.1)
        self.assertAlmostEqual(position["z"], 0.3)
        subscribes = [item for item in driver.native.sent if item.get("op") == "subscribe"]
        self.assertEqual(subscribes, [])

    def test_joint_state_observation_returns_names_and_arrays(self) -> None:
        driver, client, ids = self.serve()
        receipt = client.invoke(JOINTS, {}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(len(output["name"]), 12)
        self.assertEqual(len(output["position"]), 12)
        self.assertEqual(len(output["velocity"]), 12)
        self.assertEqual(len(output["effort"]), 12)
        self.assertIn("FL_hip_joint", output["name"])
        subscribes = [item for item in driver.native.sent if item.get("op") == "subscribe"]
        self.assertEqual(subscribes[0]["type"], "sensor_msgs/msg/JointState")
        self.assertEqual(subscribes[0]["topic"], "/joint_states")

    def test_imu_observation_returns_the_published_vectors_and_header(self) -> None:
        driver, client, ids = self.serve()
        receipt = client.invoke(IMU, {}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["orientation"], {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0})
        self.assertEqual(output["angular_velocity"], {"x": 0.0, "y": 0.0, "z": 0.0})
        self.assertEqual(output["linear_acceleration"], {"x": 0.0, "y": 0.0, "z": 0.0})
        self.assertEqual(output["stamp"], {"sec": 12, "nanosec": 340000000})
        self.assertEqual(output["frame_id"], "base")
        subscribes = [item for item in driver.native.sent if item.get("op") == "subscribe"]
        self.assertEqual(subscribes[0]["type"], "sensor_msgs/msg/Imu")
        self.assertEqual(subscribes[0]["topic"], "/imu_plugin/out")

    def test_a_silent_observation_is_a_failure_not_a_cached_value(self) -> None:
        driver, client, ids = self.serve()
        driver.native.silent = True
        receipt = client.invoke(JOINTS, {}, deadline_ms=300, **ids)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIsNone(receipt.get("output"))
        self.assertIn(receipt["error"]["mhs_code"], {"MHS.DEVICE.NOT_READY", "MHS.OUTCOME.TIMEOUT"})

    def test_an_event_with_another_subscription_id_is_not_accepted(self) -> None:
        driver, client, ids = self.serve()
        driver.native.wrong_id = True
        receipt = client.invoke(IMU, {}, deadline_ms=300, **ids)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIsNone(receipt.get("output"))

    def test_a_malformed_imu_reply_fails_output_validation(self) -> None:
        driver, client, ids = self.serve()
        driver.native.malformed = "missing_orientation"
        receipt = client.invoke(IMU, {}, **ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertIsNone(receipt.get("output"))
        self.assertTrue(receipt["error"]["mhs_code"].startswith("MHS."), receipt)

    def test_a_failed_publication_is_not_reported_completed(self) -> None:
        driver, client, ids = self.serve()
        driver.native.fail_publish = True
        receipt = client.invoke(VELOCITY, {
            "forward_velocity": 0.2,
            "lateral_velocity": 0.0,
            "yaw_rate": 0.0,
        }, **ids)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIsNone(receipt.get("output"))
        self.assertEqual(driver.native.published, [])

    def test_operator_required_limits_refuse_until_an_overlay_is_supplied(self) -> None:
        driver, client, ids = self.serve(overlay=False)
        receipt = client.invoke(VELOCITY, {
            "forward_velocity": 0.2,
            "lateral_velocity": 0.0,
            "yaw_rate": 0.0,
        }, **ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")
        self.assertEqual(driver.native.published, [])

    @staticmethod
    def services(native):
        return [message.get("service") for message in native.sent if message.get("op") == "call_service"]

    def test_the_estop_pauses_and_confirms_a_frozen_sim_time(self) -> None:
        driver, client, ids = self.serve()
        receipt = client.estop("repository test", **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertEqual(self.services(driver.native), ["/pause_physics", "/get_model_list", "/get_model_list"])

    def test_a_running_world_or_a_failed_call_leaves_the_estop_unconfirmed(self) -> None:
        for switch in ("ignore_pause", "fail_pause", "fail_model_list"):
            with self.subTest(switch=switch):
                driver, client, ids = self.serve()
                setattr(driver.native, switch, True)
                receipt = client.estop("repository test", **ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
                self.assertTrue(receipt["output"]["latched"], receipt)

    def test_the_reset_keeps_the_world_paused_and_offers_no_unpause(self) -> None:
        driver, client, ids = self.serve()
        self.assertEqual(client.estop("repository test", **ids)["status"], "completed")
        self.assertEqual(client.reset(**ids)["status"], "completed")
        self.assertTrue(driver.native.paused)
        self.assertNotIn("/unpause_physics", self.services(driver.native))
        self.assertIsNone(driver._model.reenable)
        silent = client.invoke(JOINTS, {}, **ids)
        self.assertNotEqual(silent["status"], "completed", silent)  # a paused world publishes no joint states

    def test_a_latched_estop_refuses_publications(self) -> None:
        driver, client, ids = self.serve()
        receipt = client.estop("repository test", **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        before = len(driver.native.published)
        refused = client.invoke(VELOCITY, {
            "forward_velocity": 0.2,
            "lateral_velocity": 0.0,
            "yaw_rate": 0.0,
        }, **ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(len(driver.native.published), before)


if __name__ == "__main__":
    unittest.main()

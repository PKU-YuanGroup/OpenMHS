"""Acceptance run of the RoboMaster simulator package: the gate, plus cases specific to this simulator.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RobomasterSimulatorCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_the_referee_observation_returns_the_mapped_fields(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.yizhengzhang1.referee_state.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(set(output), {"game_time", "robot_health", "remain_bullet", "robot_shoot",
                                       "robot_move", "cell_state_number", "cell_x", "cell_y",
                                       "robot_pose"})
        self.assertEqual(len(output["robot_pose"]), 4)
        self.assertEqual(set(output["robot_pose"][0]), {"x", "y", "yaw"})

    def test_pause_and_unpause_reach_the_upstream_services(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(driver.call("x-cap.yizhengzhang1.pause_physics.v1", {}),
                         {"acknowledged": True})
        self.assertTrue(driver.native.paused)
        self.assertEqual(driver.call("x-cap.yizhengzhang1.unpause_physics.v1", {}),
                         {"acknowledged": True})
        self.assertFalse(driver.native.paused)
        services = [message.get("service") for message in driver.native.sent
                    if message.get("op") == "call_service"]
        self.assertEqual(services, ["/gazebo/pause_physics", "/gazebo/unpause_physics"])

    def test_turret_command_is_published_and_out_of_limit_is_refused(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.yizhengzhang1.turret_position.v1",
                                 {"position": 0.5}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["published"])
        self.assertFalse(receipt["output"]["confirmed"])
        refused = client.invoke("x-cap.yizhengzhang1.turret_position.v1",
                                 {"position": 2.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_base_velocity_needs_an_operator_overlay(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.yizhengzhang1.cmd_vel.v1",
                                 {"linear_x": 0.0, "linear_y": 0.0, "angular_z": 0.0},
                                 **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)

    def test_a_rejected_start_game_application_response_is_a_failure(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_start_application = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.yizhengzhang1.start_game.v1", {"start": True})

    def test_a_failed_pause_service_does_not_report_stop_success(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_pause_service = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.yizhengzhang1.pause_physics.v1", {})
        self.assertFalse(driver.native.paused)

    def test_a_silent_referee_topic_is_an_explicit_observation_failure(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.silent_referee = True
        with self.assertRaises(Exception):
            driver.call("x-cap.yizhengzhang1.referee_state.v1", {})
        subscribes = [message for message in driver.native.sent
                      if message.get("op") == "subscribe"
                      and message.get("topic") == "/refer_system_info"]
        self.assertEqual(len(subscribes), 1)

    def test_the_simulator_stop_pauses_and_latches(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        refused = client.invoke("x-cap.yizhengzhang1.unpause_physics.v1", {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the Smart Grasping Sandbox ROS package: the gate, plus cases for this simulator.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"

HOME_POSITIONS = [1.2, 0.3, -1.5, -0.5, -1.5, 0.0,
                  0.0, -0.3, 0.0, 0.0, -0.3, 0.0, 0.0, -0.3, 0.0]
HAND_OPEN = [0.0, -0.3, 0.0, 0.0, -0.3, 0.0, 0.0, -0.3, 0.0]
HAND_CLOSE = [0.0, 0.25, 0.4, 0.0, 0.25, 0.4, 0.0, 0.25, 0.4]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SandboxCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_pause_and_unpause_reach_the_gazebo_services(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.shadow-robot.pause_physics.v1", {}),
                         {"acknowledged": True})
        self.assertTrue(driver.native.paused)
        self.assertEqual(driver.call("x-cap.shadow-robot.unpause_physics.v1", {}),
                         {"acknowledged": True})
        self.assertFalse(driver.native.paused)
        services = [message.get("service") for message in driver.native.sent
                    if message.get("op") == "call_service"]
        self.assertEqual(services, ["/gazebo/pause_physics", "/gazebo/unpause_physics"])

    def test_reset_world_reaches_the_gazebo_service(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.shadow-robot.reset_world.v1", {}),
                         {"acknowledged": True})
        self.assertEqual(driver.native.reset_count, 1)

    def test_joint_states_observation_returns_a_fresh_sample(self) -> None:
        driver = self.driver()
        output = driver.call("x-cap.shadow-robot.joint_states.v1", {})
        self.assertEqual(output["names"], driver.native.joint_names)
        self.assertEqual(output["positions"], driver.native.joint_positions)
        self.assertEqual(output["velocities"], driver.native.joint_velocities)
        self.assertEqual(output["efforts"], driver.native.joint_efforts)
        operations = [(message.get("op"), message.get("topic")) for message in driver.native.sent]
        self.assertIn(("subscribe", "/joint_states"), operations)
        self.assertIn(("unsubscribe", "/joint_states"), operations)

    def test_object_pose_observation_maps_the_pose(self) -> None:
        driver = self.driver()
        output = driver.call("x-cap.shadow-robot.object_pose.v1", {})
        self.assertEqual(output["position"]["x"], driver.native.object_pose["position"]["x"])
        self.assertEqual(output["position"]["z"], driver.native.object_pose["position"]["z"])
        self.assertEqual(output["orientation"]["w"], 1.0)

    def test_home_configuration_sends_the_upstream_reset_values(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.shadow-robot.home_configuration.v1", {}),
                         {"applied": True})
        configuration = driver.native.last_configuration
        self.assertEqual(configuration["model_name"], "smart_grasping_sandbox")
        self.assertEqual(configuration["urdf_param_name"], "robot_description")
        self.assertEqual(len(configuration["joint_names"]), 15)
        self.assertEqual(configuration["joint_positions"], HOME_POSITIONS)

    def test_hand_open_and_close_send_the_srdf_group_states(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.shadow-robot.hand_open.v1", {}), {"applied": True})
        self.assertEqual(driver.native.last_configuration["joint_positions"], HAND_OPEN)
        self.assertEqual(len(driver.native.last_configuration["joint_names"]), 9)
        self.assertEqual(driver.call("x-cap.shadow-robot.hand_close.v1", {}), {"applied": True})
        self.assertEqual(driver.native.last_configuration["joint_positions"], HAND_CLOSE)

    def test_a_failed_pause_service_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.fail_pause_service = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.shadow-robot.pause_physics.v1", {})
        self.assertFalse(driver.native.paused)

    def test_a_rejected_pause_application_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.fail_pause_application = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.shadow-robot.pause_physics.v1", {})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_a_rejected_pose_application_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.fail_pose_application = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.shadow-robot.object_pose.v1", {})

    def test_a_rejected_configuration_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.fail_configuration = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.shadow-robot.hand_close.v1", {})

    def test_the_simulator_stop_pauses_and_latches(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        refused = client.invoke("x-cap.shadow-robot.unpause_physics.v1", {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_normal_safe_state_invocation_does_not_latch(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("x-cap.shadow-robot.pause_physics.v1", {},
                                       **self.ids)["status"], "completed")
        self.assertEqual(client.invoke("x-cap.shadow-robot.unpause_physics.v1", {},
                                       **self.ids)["status"], "completed")

    def test_a_failed_estop_reports_the_unreached_safe_state(self) -> None:
        driver = self.driver()
        driver.native.fail_pause_service = True
        with self.assertRaises(DriverFailed) as caught:
            driver.estop("test")
        self.assertEqual(caught.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_a_malformed_estop_reply_reports_the_unreached_safe_state(self) -> None:
        driver = self.driver()
        driver.native.malformed_pause_response = True
        with self.assertRaises(DriverFailed) as caught:
            driver.estop("test")
        self.assertEqual(caught.exception.code, "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_observational_extension_actions_remain_latched(self) -> None:
        client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        for capability_id in ("x-cap.shadow-robot.joint_states.v1",
                              "x-cap.shadow-robot.object_pose.v1"):
            receipt = client.invoke(capability_id, {}, **self.ids)
            self.assertEqual(receipt["status"], "rejected", receipt)
            self.assertEqual(receipt["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()

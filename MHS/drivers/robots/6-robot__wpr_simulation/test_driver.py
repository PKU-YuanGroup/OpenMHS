"""Acceptance run of the WPR Gazebo simulation package: the gate plus local cases.

The cases exercise the declared wire contract, the companion-cited stop (the Gazebo world pause confirmed by the
get_physics_properties read-back), its failure paths, the latch, the declared resume after a reset (a zero Twist
before the unpause) and the silence of world-update topics while paused.  Add cases, never remove the check_driver
call.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
CMD_VEL = "x-cap.6-robot.cmd_vel.v1"
ODOMETRY = "x-cap.6-robot.odometry.v1"
RESUME = "x-cap.6-robot.resume.v1"
PAUSE = "/gazebo/pause_physics"
READBACK = "/gazebo/get_physics_properties"
UNPAUSE = "/gazebo/unpause_physics"
MOVE = {"linear_x": 0.1, "linear_y": 0.0, "angular_z": 0.2}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WprSimulationCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def serve(self, site_limits=HERE / "site-limits.example.json"):
        driver = self.driver()
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    def test_the_odometry_observation_returns_pose_and_twist(self) -> None:
        driver = self.driver()
        output = driver.call(ODOMETRY, {})
        self.assertEqual(set(output["pose"]), {"position", "orientation"})
        self.assertEqual(set(output["twist"]), {"linear", "angular"})

    def test_the_pose_difference_observation_returns_all_components(self) -> None:
        driver = self.driver()
        output = driver.call("x-cap.6-robot.pose_diff.v1", {})
        self.assertEqual(set(output), {"x", "y", "theta"})

    def test_cmd_vel_publication_reaches_the_plugin_topic_and_reports_what_it_sent(self) -> None:
        driver = self.driver()
        output = driver.call(CMD_VEL, MOVE)
        self.assertEqual(output, {"published": True, "confirmed": False, "sent_linear_x": 0.1,
                                  "sent_linear_y": 0.0, "sent_angular_z": 0.2})
        self.assertEqual(driver.native.last_cmd_vel["linear"]["x"], 0.1)
        self.assertEqual(driver.native.last_cmd_vel["angular"]["z"], 0.2)
        published = [message for message in driver.native.sent
                     if message.get("op") == "publish" and message.get("topic") == "/cmd_vel"]
        self.assertEqual(len(published), 1)

    def test_cmd_vel_is_refused_until_the_operator_supplies_bounds(self) -> None:
        _driver, client = self.serve(site_limits=None)
        receipt = client.invoke(CMD_VEL, MOVE, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_e_stop_pauses_the_world_and_confirms_it_by_the_read_back(self) -> None:
        driver, client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertTrue(driver.native.paused)
        self.assertEqual(driver.native.service_calls[:2], [PAUSE, READBACK])

    def test_a_read_back_other_than_pause_true_leaves_the_e_stop_unconfirmed_and_latched(self) -> None:
        for switch in ("unpaused_by_other_client", "fail_readback", "fail_pause"):
            with self.subTest(switch=switch):
                driver, client = self.serve()
                setattr(driver.native, switch, True)
                receipt = client.estop("test", **self.ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], UNREACHED)
                refused = client.invoke(CMD_VEL, MOVE, **self.ids)
                self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_the_latched_command_and_the_resume_are_refused_until_the_reset(self) -> None:
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        for capability, payload in ((CMD_VEL, MOVE), (RESUME, {})):
            receipt = client.invoke(capability, payload, **self.ids)
            self.assertEqual(receipt["status"], "rejected", receipt)
            self.assertEqual(receipt["error"]["mhs_code"], ESTOP)
        self.assertNotIn(UNPAUSE, driver.native.service_calls)
        self.assertTrue(driver.native.paused)

    def test_the_reset_releases_the_latch_only_and_the_resume_zeroes_then_unpauses(self) -> None:
        driver, client = self.serve()
        self.assertEqual(client.invoke(CMD_VEL, MOVE, **self.ids)["status"], "completed")
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(reset["output"]["reenable"], RESUME)
        self.assertTrue(driver.native.paused)  # the reset never unpauses (SAFE-042)
        self.assertEqual(driver.native.last_cmd_vel["linear"]["x"], 0.1)  # the plugin still holds the command
        mark = len(driver.native.sent)
        receipt = client.invoke(RESUME, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"acknowledged": True, "zero_command_published": True})
        after = [(message.get("op"), message.get("topic") or message.get("service"))
                 for message in driver.native.sent[mark:] if message.get("op") in ("publish", "call_service")]
        self.assertEqual(after, [("publish", "/cmd_vel"), ("call_service", UNPAUSE)])
        self.assertFalse(driver.native.paused)
        self.assertEqual(driver.native.last_cmd_vel["linear"], {"x": 0.0, "y": 0.0, "z": 0.0})
        self.assertEqual(driver.native.odom_linear["x"], 0.0)

    def test_without_the_zero_an_unpause_would_resume_the_stored_command(self) -> None:
        # The hazard the resume guards against (SAFE-042): the plugin applies its stored command when the world runs.
        driver = self.driver()
        driver.call(CMD_VEL, MOVE)
        driver.native.paused = True
        driver.native.odom_linear = {"x": 0.0, "y": 0.0, "z": 0.0}
        # Another client's bare unpause (no zero first) on the fake transport itself.
        driver.native.send({"op": "call_service", "service": UNPAUSE, "type": "std_srvs/Empty", "args": {},
                            "id": "other-client"})
        self.assertFalse(driver.native.paused)
        self.assertEqual(driver.native.odom_linear["x"], 0.1)

    def test_a_failed_zero_or_unpause_fails_the_resume_and_keeps_the_world_paused(self) -> None:
        driver, client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        driver.native.fail_resume = True
        receipt = client.invoke(RESUME, {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertTrue(driver.native.paused)

    def test_world_update_topics_are_silent_while_paused(self) -> None:
        driver = self.driver()
        driver.native.paused = True
        with self.assertRaises(Exception) as caught:
            driver.call(ODOMETRY, {})
        self.assertIn("MHS.", str(caught.exception))

    def test_the_resource_reads_no_topic_and_answers_while_paused(self) -> None:
        driver = self.driver()
        driver.native.paused = True
        driver.native.withhold_pose_diff = True
        self.assertEqual(driver.read("main"), {})

    def test_a_missing_odometry_sample_is_an_observation_timeout_not_a_hold(self) -> None:
        driver = self.driver()
        driver.native.withhold_odom = True
        with self.assertRaises(Exception) as caught:
            driver.call(ODOMETRY, {})
        self.assertIn("MHS.", str(caught.exception))


if __name__ == "__main__":
    unittest.main()

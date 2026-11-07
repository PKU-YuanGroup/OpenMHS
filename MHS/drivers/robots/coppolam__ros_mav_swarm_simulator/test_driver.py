"""Acceptance run of the Coppolam ROS MAV swarm simulator package.

The cases exercise the odometry read, the cmd_vel publication (receipt reports the values sent), the
enable_motors service, the ordinary landing action, the operator limits, and the companion-cited stop
(the Gazebo world pause confirmed by the get_physics_properties read-back), its failure paths, the latch,
a reset that leaves the world paused, and that the package offers no unpause.  Add cases, never remove
the check_driver call.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, OutcomeUnknown, build_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
PAUSE = "/gazebo/pause_physics"
READBACK = "/gazebo/get_physics_properties"
CMD = "x-cap.coppolam.cmd_vel.v1"
ARM = "x-cap.coppolam.arm.v1"
LAND = "x-cap.coppolam.land.v1"
ODOM = "x-cap.coppolam.odometry.v1"
SAMPLE = {"linear_x": 0.2, "linear_y": -0.2, "linear_z": 0.1, "angular_z": 0.1}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MavSwarmCases(unittest.TestCase):
    def serve(self, **options):
        server = load(HERE, backend="fake", **options)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def example_overlay(self):
        return json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))

    @staticmethod
    def services(native):
        return [message.get("service") for message in native.sent if message.get("op") == "call_service"]

    def test_the_odometry_observation_returns_pose_and_twist(self) -> None:
        client = self.serve()
        receipt = client.invoke(ODOM, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertIn("frame_id", output)
        self.assertEqual(set(output["pose"]["position"]), {"x", "y", "z"})
        self.assertEqual(set(output["twist"]["linear"]), {"x", "y", "z"})

    def test_the_resource_reads_no_topic(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(driver.read("main"), {})
        driver.native.paused = True
        self.assertEqual(driver.read("main"), {})

    def test_arm_and_cmd_vel_reach_the_fake_endpoints(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(driver.call(ARM, {}), {"success": True})
        output = driver.call(CMD, dict(SAMPLE))
        self.assertEqual(output, {
            "published": True, "confirmed": False,
            "sent_linear_x": 0.2, "sent_linear_y": -0.2, "sent_linear_z": 0.1, "sent_angular_z": 0.1,
        })
        messages = list(driver.native.sent)
        services = [item for item in messages if item.get("op") == "call_service"]
        self.assertEqual([item.get("service") for item in services], ["/uav1/enable_motors"])
        published = [item for item in messages
                     if item.get("op") == "publish" and item.get("topic") == "/uav1/cmd_vel"]
        self.assertEqual(len(published), 1)
        self.assertEqual(published[0]["msg"]["linear"]["x"], 0.2)
        self.assertEqual(published[0]["msg"]["angular"]["z"], 0.1)

    def test_the_landing_action_reaches_the_fake_and_disables_motors(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(driver.call(ARM, {}), {"success": True})
        self.assertTrue(driver.native.motors_enabled)
        self.assertEqual(driver.call(LAND, {}), {"landed": True})
        self.assertTrue(driver.native.landed)
        self.assertFalse(driver.native.motors_enabled)
        goals = [item for item in driver.native.sent
                 if item.get("op") == "publish" and item.get("topic") == "/uav1/action/landing/goal"]
        self.assertEqual(len(goals), 1)

    def test_cmd_vel_without_an_operator_overlay_is_refused(self) -> None:
        # No source states a cmd_vel envelope: every input is operator_required.
        client = self.serve()
        receipt = client.invoke(CMD, dict(SAMPLE), **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)

    def test_cmd_vel_out_of_the_example_envelope_is_refused(self) -> None:
        client = self.serve(site_limits=self.example_overlay())
        receipt = client.invoke(CMD, {
            "linear_x": 20.0, "linear_y": -0.2, "linear_z": 0.1, "angular_z": 0.1,
        }, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)

    def test_cmd_vel_completes_under_the_example_overlay(self) -> None:
        client = self.serve(site_limits=self.example_overlay())
        receipt = client.invoke(CMD, dict(SAMPLE), **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {
            "published": True, "confirmed": False,
            "sent_linear_x": 0.2, "sent_linear_y": -0.2, "sent_linear_z": 0.1, "sent_angular_z": 0.1,
        })

    def test_a_failed_arm_service_is_a_failure(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_arm_service = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.coppolam.arm.v1", {})

    def test_a_rejected_arm_application_is_a_failure(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_arm_application = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.coppolam.arm.v1", {})

    def test_an_aborted_landing_action_is_a_failure(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_landing = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.coppolam.land.v1", {})

    def test_a_malformed_landing_result_is_not_completed(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.malformed_landing = True
        with self.assertRaises(OutcomeUnknown):
            driver.call("x-cap.coppolam.land.v1", {})

    def test_missing_odometry_is_not_a_stale_read(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.omit_odometry = True
        with self.assertRaises((DriverFailed, OutcomeUnknown, MHSError)):
            driver.call(ODOM, {})

    def test_the_estop_pauses_the_world_and_confirms_it_by_the_read_back(self) -> None:
        # The landing action re-enables the motors (pose_action.cpp:56-58), so it is not the stop.
        # The e-stop is the companion world pause, confirmed when pause reads true.
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        server = build_server(driver, site_limits=self.example_overlay())
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        ids = {"device_id": device_id,
               "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        receipt = client.estop("test", **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertEqual(self.services(driver.native), [PAUSE, READBACK])
        self.assertTrue(driver.native.paused)
        self.assertNotIn("/gazebo/unpause_physics", self.services(driver.native))
        # safety_status is the cached confirmation. An external unpause is not a fresh read-back.
        sent = len(driver.native.sent)
        driver.native.paused = False
        status = client.safety_status(device_id)
        self.assertTrue(status["estop"]["confirmed"], status)
        self.assertTrue(status["status"]["safe_state"]["achieved"], status)
        self.assertEqual(len(driver.native.sent), sent)
        self.assertFalse(driver.native.paused)
        for capability in (LAND, ARM, CMD):
            refused = client.invoke(capability, dict(SAMPLE) if capability == CMD else {}, **ids)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_a_failed_pause_or_read_back_leaves_the_e_stop_unconfirmed_and_latched(self) -> None:
        for switch in ("fail_pause", "fail_readback", "ignore_pause"):
            with self.subTest(switch=switch):
                driver = load_driver(HERE, "fake")
                self.addCleanup(driver.close)
                setattr(driver.native, switch, True)
                server = build_server(driver, site_limits=self.example_overlay())
                self.addCleanup(close_server, server)
                client = client_for(server)
                device_id = client.hello()["devices"][0]["device_id"]
                ids = {"device_id": device_id,
                       "session_id": client.open_session(device_ids=[device_id])["session_id"]}
                receipt = client.estop("test", **ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
                refused = client.invoke(LAND, {}, **ids)
                self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_the_reset_keeps_the_world_paused_and_a_stored_command_moves_nothing(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        server = build_server(driver, site_limits=self.example_overlay())
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        ids = {"device_id": device_id,
               "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        self.assertEqual(client.estop("test", **ids)["status"], "completed")
        self.assertEqual(client.reset(**ids)["status"], "completed")
        self.assertTrue(driver.native.paused)
        before = dict(driver.native.odom_position)
        receipt = client.invoke(CMD, dict(SAMPLE), **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["sent_linear_x"], 0.2)
        self.assertEqual(driver.native.stored_twist["linear"]["x"], 0.2)
        self.assertEqual(driver.native.odom_position, before)
        self.assertNotIn("/gazebo/unpause_physics", self.services(driver.native))
        odometry = client.invoke(ODOM, {}, **ids)
        self.assertNotEqual(odometry["status"], "completed", odometry)

    def test_enable_motors_is_answered_while_paused_and_landing_is_not(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.paused = True
        self.assertEqual(driver.call(ARM, {}), {"success": True})
        self.assertTrue(driver.native.motors_enabled)
        with self.assertRaises(DriverFailed):
            driver.call(LAND, {})
        self.assertFalse(driver.native.landed)
        with self.assertRaises((DriverFailed, OutcomeUnknown, MHSError)):
            driver.call(ODOM, {})

    def test_the_package_offers_no_unpause(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertIsNone(driver._model.reenable)
        for spec in type(driver).commands.values():
            self.assertNotIn("unpause", str(spec.get("service", "")))
            self.assertNotIn("unpause", str(spec.get("action", "")))


if __name__ == "__main__":
    unittest.main()

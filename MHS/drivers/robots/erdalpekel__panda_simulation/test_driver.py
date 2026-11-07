"""Acceptance run of the panda_simulation ROS package: the gate plus repository cases.

The cases exercise the joint-state read, the joint-position command and the ordinary /robot_control_stop request,
the companion-cited stop (the Gazebo world pause confirmed by the get_physics_properties read-back), its failure
paths, the latch, a reset that leaves the world paused, and that the package offers no unpause.  Add cases, never
remove the check_driver call.
"""

import json
import unittest
from pathlib import Path

from mhs import MHSError
from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
COMMAND = "x-cap.erdalpekel.joint_position_command.v1"
STOP = "x-cap.erdalpekel.robot_stop.v1"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
LATCHED = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
JOINT_STATES = "x-cap.erdalpekel.joint_states.v1"
PAUSE = "/gazebo/pause_physics"
READBACK = "/gazebo/get_physics_properties"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PandaCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session_id = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session_id}
        return client

    def serve_driver(self, site_limits=None):
        driver = load_driver(HERE, "fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session_id = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session_id}
        return driver, client

    @staticmethod
    def example_overlay():
        return json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))

    def test_the_joint_state_read_returns_the_published_shape(self) -> None:
        client = self.serve()
        receipt = client.invoke(JOINT_STATES, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        positions = receipt["output"]["joint_positions"]
        self.assertEqual(len(positions), 9)  # placeholder shape: two fingers plus seven arm joints
        self.assertTrue(all(isinstance(value, float) for value in positions))

    def test_the_resource_reads_no_topic(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.paused = True
        self.assertEqual(driver.read("main"), {})

    def test_a_joint_command_is_refused_without_the_operator_limit(self) -> None:
        driver, client = self.serve_driver()
        receipt = client.invoke(COMMAND, {"joint_positions": [0.05] * 7}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)
        publishes = [message for message in driver.native.sent
                     if message.get("op") == "publish"
                     and message.get("topic") == "/joint_position_controller/command"]
        self.assertEqual(publishes, [])

    def test_the_example_overlay_admits_the_joint_command_and_reaches_the_fake(self) -> None:
        driver, client = self.serve_driver(site_limits=self.example_overlay())
        receipt = client.invoke(COMMAND, {"joint_positions": [0.05] * 7}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"published": True, "confirmed": False,
                                             "sent_joint_positions": [0.05] * 7})
        self.assertEqual(driver.native.received_commands[-1], [0.05] * 7)
        state = client.invoke(JOINT_STATES, {}, **self.ids)["output"]
        self.assertEqual(state["joint_positions"][2:], [0.05] * 7)  # placeholder finger prefix
        messages = [(message.get("op"), message.get("topic")) for message in driver.native.sent]
        self.assertIn(("advertise", "/joint_position_controller/command"), messages)
        self.assertIn(("publish", "/joint_position_controller/command"), messages)

    def test_an_out_of_overlay_joint_command_is_refused_before_the_fake(self) -> None:
        driver, client = self.serve_driver(site_limits=self.example_overlay())
        before = [message for message in driver.native.sent
                  if message.get("topic") == "/joint_position_controller/command"]
        receipt = client.invoke(COMMAND, {"joint_positions": [0.2] * 7}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        after = [message for message in driver.native.sent
                 if message.get("topic") == "/joint_position_controller/command"]
        self.assertEqual(after, before)

    def test_the_stop_service_is_acknowledged_and_sets_the_fake_stop(self) -> None:
        driver, client = self.serve_driver()
        receipt = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"acknowledged": True})
        self.assertTrue(driver.native.stopped)
        services = [message.get("service") for message in driver.native.sent
                    if message.get("op") == "call_service"]
        self.assertIn("/robot_control_stop", services)

    def test_a_failed_stop_service_does_not_report_success(self) -> None:
        driver, client = self.serve_driver()
        driver.native.fail_stop_service = True
        receipt = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.ADAPTER.SHIM_FAILED")
        self.assertFalse(driver.native.stopped)

    def test_a_rejected_stop_application_does_not_report_success(self) -> None:
        driver, client = self.serve_driver()
        driver.native.fail_stop_application = True
        receipt = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.ADAPTER.SHIM_FAILED")

    def test_a_malformed_stop_reply_does_not_report_success(self) -> None:
        driver, client = self.serve_driver()
        driver.native.malformed_stop_response = True
        receipt = client.invoke(STOP, {}, **self.ids)
        self.assertNotEqual(receipt["status"], "completed", receipt)

    @staticmethod
    def services(native):
        return [message.get("service") for message in native.sent if message.get("op") == "call_service"]

    def test_the_estop_pauses_the_world_and_confirms_it_by_the_read_back(self) -> None:
        # /robot_control_stop acknowledges unconditionally and does not reach the custom joint_position_controller
        # (model review 2026-11-05), so the e-stop is the companion world pause, never that request.
        driver, client = self.serve_driver(site_limits=self.example_overlay())
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertEqual(self.services(driver.native), [PAUSE, READBACK])
        self.assertTrue(driver.native.paused)
        refused = client.invoke(COMMAND, {"joint_positions": [0.05] * 7}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LATCHED)

    def test_a_failed_pause_or_read_back_leaves_the_e_stop_unconfirmed_and_latched(self) -> None:
        for switch in ("fail_pause", "fail_readback", "ignore_pause"):
            with self.subTest(switch=switch):
                driver, client = self.serve_driver(site_limits=self.example_overlay())
                setattr(driver.native, switch, True)
                receipt = client.estop("test", **self.ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
                refused = client.invoke(STOP, {}, **self.ids)
                self.assertEqual(refused["error"]["mhs_code"], LATCHED, refused)

    def test_the_robot_stop_request_is_not_a_safe_state_action(self) -> None:
        driver, client = self.serve_driver()
        client.estop("test", **self.ids)
        refused = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LATCHED)
        self.assertNotIn("/robot_control_stop", self.services(driver.native))

    def test_the_reset_keeps_the_world_paused_and_a_stored_command_moves_nothing(self) -> None:
        driver, client = self.serve_driver(site_limits=self.example_overlay())
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertTrue(driver.native.paused)
        receipt = client.invoke(COMMAND, {"joint_positions": [0.05] * 7}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(driver.native.stored_command, [0.05] * 7)  # command_ acts on the next unpause
        self.assertEqual(driver.native.joint_positions[2:], [0.0] * 7)
        self.assertNotIn("/gazebo/unpause_physics", self.services(driver.native))
        joint_states = client.invoke(JOINT_STATES, {}, **self.ids)
        self.assertEqual(joint_states["status"], "failed", joint_states)  # silent while paused

    def test_the_package_offers_no_unpause(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertIsNone(driver._model.reenable)
        for spec in type(driver).commands.values():
            self.assertNotIn("unpause", str(spec.get("service", "")))

    def test_a_dropped_joint_state_read_is_not_reported_as_state(self) -> None:
        driver, client = self.serve_driver()
        driver.native.drop_joint_state = True
        receipt = client.invoke(JOINT_STATES, {}, **self.ids)
        self.assertNotEqual(receipt["status"], "completed", receipt)

"""Acceptance run of the Scout V2 empty-world package: the gate plus repository cases.

The cases exercise the /cmd_vel publication, the operator limit, the companion world pause and its read-back, the
failure paths, the latch, and a reset that leaves the world paused.  The package offers no unpause.  Add cases,
never remove the check_driver call.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
COMMAND = "x-cap.agilexrobotics.cmd_vel.v1"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
LATCHED = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
PAUSE = "/gazebo/pause_physics"
READBACK = "/gazebo/get_physics_properties"
UNPAUSE = "/gazebo/unpause_physics"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ScoutV2Cases(unittest.TestCase):
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

    @staticmethod
    def services(native):
        return [message.get("service") for message in native.sent if message.get("op") == "call_service"]

    @staticmethod
    def cmd_publishes(native):
        return [message for message in native.sent
                if message.get("op") == "publish" and message.get("topic") == "/cmd_vel"]

    def test_the_resource_reads_no_topic(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.paused = True
        self.assertEqual(driver.read("main"), {})

    def test_a_command_is_refused_without_the_operator_limit(self) -> None:
        driver, client = self.serve_driver()
        receipt = client.invoke(COMMAND, {"linear_x": 0.2, "angular_z": 0.1}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)
        self.assertEqual(self.cmd_publishes(driver.native), [])

    def test_the_example_overlay_admits_the_command_and_reports_what_was_sent(self) -> None:
        driver, client = self.serve_driver(site_limits=self.example_overlay())
        receipt = client.invoke(COMMAND, {"linear_x": 0.2, "angular_z": -0.3}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"published": True, "confirmed": False,
                                             "sent_linear_x": 0.2, "sent_angular_z": -0.3})
        self.assertEqual(driver.native.received[-1], {"linear_x": 0.2, "angular_z": -0.3})
        body = self.cmd_publishes(driver.native)[-1]["msg"]
        self.assertEqual(body["linear"]["y"], 0.0)
        self.assertEqual(body["angular"]["x"], 0.0)

    def test_a_zero_twist_is_what_the_receipt_reports(self) -> None:
        # The in-repo callback publishes four zero Float64 values for a zero Twist.  This fake records the Twist.
        # It does not claim that an external JointVelocityController dropped a held setpoint.
        driver, client = self.serve_driver(site_limits=self.example_overlay())
        receipt = client.invoke(COMMAND, {"linear_x": 0.0, "angular_z": 0.0}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["sent_linear_x"], 0.0)
        self.assertEqual(receipt["output"]["sent_angular_z"], 0.0)
        self.assertEqual(driver.native.received[-1], {"linear_x": 0.0, "angular_z": 0.0})

    def test_an_out_of_overlay_command_is_refused_before_the_fake(self) -> None:
        driver, client = self.serve_driver(site_limits=self.example_overlay())
        before = self.cmd_publishes(driver.native)
        receipt = client.invoke(COMMAND, {"linear_x": 2.0, "angular_z": 0.0}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(self.cmd_publishes(driver.native), before)

    def test_the_estop_pauses_the_world_and_confirms_it_by_the_read_back(self) -> None:
        driver, client = self.serve_driver(site_limits=self.example_overlay())
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["safe_state_achieved"], receipt)
        self.assertEqual(self.services(driver.native), [PAUSE, READBACK])
        self.assertTrue(driver.native.paused)
        refused = client.invoke(COMMAND, {"linear_x": 0.2, "angular_z": 0.0}, **self.ids)
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
                refused = client.invoke(COMMAND, {"linear_x": 0.2, "angular_z": 0.0}, **self.ids)
                self.assertEqual(refused["error"]["mhs_code"], LATCHED, refused)

    def test_the_reset_keeps_the_world_paused_and_calls_no_unpause(self) -> None:
        driver, client = self.serve_driver(site_limits=self.example_overlay())
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertTrue(driver.native.paused)
        self.assertNotIn(UNPAUSE, self.services(driver.native))
        receipt = client.invoke(COMMAND, {"linear_x": 0.2, "angular_z": 0.0}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(driver.native.paused)

    def test_the_package_offers_no_unpause(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertIsNone(driver._model.reenable)
        for spec in type(driver).commands.values():
            self.assertNotIn("unpause", str(spec.get("service", "")))
            self.assertNotIn("unpause", str(spec.get("topic", "")))

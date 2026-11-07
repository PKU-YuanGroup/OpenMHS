"""Acceptance run of the AuNa ROS package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AunaCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.server = server
        self.device = server.devices[device_id]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_source_selection_reaches_the_upstream_service(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.harunteper.velocity_source.v1", {"source": "teleop"}),
                         {"success": True, "message": "Velocity source set to: teleop"})
        self.assertEqual(driver.native.current_source, "teleop")
        calls = [message for message in driver.native.sent if message.get("op") == "call_service"]
        self.assertEqual(calls[-1]["service"], "/robot1/toggle_cmd_vel_source")
        self.assertEqual(calls[-1]["type"], "auna_msgs/srv/SetString")
        self.assertEqual(calls[-1]["args"], {"data": "teleop"})

    def test_teleop_command_encodes_speed_and_steering(self) -> None:
        driver = self.driver()
        output = driver.call("x-cap.harunteper.teleop_velocity.v1",
                             {"speed": 0.5, "steering_angle": 0.1})
        self.assertEqual(output, {"published": True, "confirmed": False})
        self.assertAlmostEqual(driver.native.last_command["linear"]["x"], 0.5)
        self.assertAlmostEqual(driver.native.last_command["angular"]["z"], 0.1)
        messages = [message for message in driver.native.sent
                    if message.get("op") == "publish"]
        self.assertEqual(messages[-1]["topic"], "/robot1/cmd_vel/teleop")
        self.assertEqual(messages[-1]["msg"]["twist"]["linear"]["x"], 0.5)
        self.assertEqual(messages[-1]["msg"]["twist"]["angular"]["z"], 0.1)
        published = [message for message in driver.native.sent if message.get("op") == "advertise"]
        self.assertEqual(published[-1]["topic"], "/robot1/cmd_vel/teleop")
        self.assertEqual(published[-1]["type"], "geometry_msgs/msg/TwistStamped")

    def test_teleop_is_refused_until_the_operator_supplies_the_envelope(self) -> None:
        client = self.serve()
        refused = client.invoke("x-cap.harunteper.teleop_velocity.v1",
                                {"speed": 0.5, "steering_angle": 0.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_example_overlay_admits_and_bounds_teleop(self) -> None:
        client = self.serve(site_limits=str(HERE / "site-limits.example.json"))
        receipt = client.invoke("x-cap.harunteper.teleop_velocity.v1",
                                {"speed": 0.5, "steering_angle": 0.1}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        for values in ({"speed": 2.0, "steering_angle": 0.0}, {"speed": 0.0, "steering_angle": 0.7}):
            refused = client.invoke("x-cap.harunteper.teleop_velocity.v1", values, **self.ids)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, refused)

    def test_source_off_stop_does_not_publish_a_command(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.harunteper.stop.v1", {}), {"source_off": True})
        self.assertEqual(driver.native.current_source, "OFF")
        self.assertFalse([message for message in driver.native.sent if message.get("op") == "publish"])

    def test_rejected_upstream_source_is_a_failure(self) -> None:
        driver = self.driver()
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.harunteper.velocity_source.v1", {"source": "not-a-source"})
        self.assertEqual(driver.native.current_source, "OFF")

    def test_failed_source_service_does_not_report_success(self) -> None:
        driver = self.driver()
        driver.native.fail_source_service = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.harunteper.velocity_source.v1", {"source": "teleop"})
        self.assertEqual(driver.native.current_source, "OFF")

    def test_source_status_reports_the_current_source(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.harunteper.source_status.v1", {}),
                         {"success": True, "message": "Current source: OFF"})
        driver.call("x-cap.harunteper.velocity_source.v1", {"source": "nav2"})
        self.assertEqual(driver.call("x-cap.harunteper.source_status.v1", {}),
                         {"success": True, "message": "Current source: nav2"})

    def test_a_malformed_status_response_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.malformed_status_values = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.harunteper.source_status.v1", {})

    def test_estop_sets_the_source_off_and_latches_actuation(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        refused = client.invoke("x-cap.harunteper.teleop_velocity.v1",
                                {"speed": 0.5, "steering_angle": 0.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_estop_with_a_failed_stop_service_is_not_claimed(self) -> None:
        client = self.serve()
        self.device.bridge.native.fail_source_service = True
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertFalse(receipt["output"]["safe_state_achieved"])

    def test_estop_with_a_malformed_stop_reply_is_not_claimed(self) -> None:
        client = self.serve()
        self.device.bridge.native.malformed_source_values = True
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertFalse(receipt["output"]["safe_state_achieved"])


if __name__ == "__main__":
    unittest.main()

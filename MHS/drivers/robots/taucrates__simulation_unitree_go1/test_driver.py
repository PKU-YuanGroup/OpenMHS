"""Acceptance run of the taucrates Go1 package: the gate plus repository cases.

Add cases, never remove the check_driver call.  While the package is blocked the
stock gate case fails with the two documented source gaps: no fully qualified
ROS message type is declared in the pinned tree (G7) and no acknowledged ROS
stop endpoint exists (G6).  The cases below exercise the ROS-free fake contract,
the operator-required velocity limits and the missing stop.  No ROS graph,
Gazebo process, CHAMP controller or hardware is started.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
CMD_VEL = "x-cap.taucrates.cmd_vel.v1"
SCAN = "x-cap.taucrates.scan.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Go1Cases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def serve(self, *, overlay: bool = False):
        site_limits = None
        if overlay:
            site_limits = json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return server, client, device_id

    @staticmethod
    def sent(server, device_id):
        return server.devices[device_id].bridge.native.sent

    def test_scan_read_returns_the_declared_shape(self) -> None:
        driver = self.driver()
        scan = driver.call(SCAN, {})
        self.assertEqual(set(scan), {"frame_id", "angle_min", "angle_max", "angle_increment",
                                     "time_increment", "scan_time", "range_min", "range_max",
                                     "ranges", "intensities"})
        self.assertEqual(len(scan["ranges"]), 3)  # placeholder size, not the 800-sample device output
        subscribe = [message for message in driver.native.sent if message.get("op") == "subscribe"]
        self.assertEqual(subscribe[-1]["topic"], "/scan")
        self.assertEqual(subscribe[-1]["type"], "sensor_msgs/LaserScan")

    def test_cmd_vel_publication_maps_the_three_axes(self) -> None:
        driver = self.driver()
        receipt = driver.call(CMD_VEL, {"linear_x": 0.2, "linear_y": -0.1, "angular_z": -0.4})
        self.assertEqual(receipt, {"published": True, "confirmed": False})
        advertised = [message for message in driver.native.sent if message.get("op") == "advertise"]
        self.assertEqual(advertised[-1]["topic"], "/cmd_vel")
        self.assertEqual(advertised[-1]["type"], "geometry_msgs/Twist")
        published = [message for message in driver.native.sent if message.get("op") == "publish"]
        self.assertEqual(published[-1]["msg"]["linear"], {"x": 0.2, "y": -0.1, "z": 0.0})
        self.assertEqual(published[-1]["msg"]["angular"], {"x": 0.0, "y": 0.0, "z": -0.4})

    def test_operator_required_limits_refuse_without_an_overlay(self) -> None:
        server, client, device_id = self.serve(overlay=False)
        receipt = client.invoke(CMD_VEL, {"linear_x": 0.1, "linear_y": 0.0, "angular_z": 0.0}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")
        self.assertFalse([message for message in self.sent(server, device_id)
                          if message.get("op") == "publish"])

    def test_operator_overlay_admits_the_publication(self) -> None:
        server, client, device_id = self.serve(overlay=True)
        receipt = client.invoke(CMD_VEL, {"linear_x": 0.2, "linear_y": -0.1, "angular_z": -0.4}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"published": True, "confirmed": False})
        published = [message for message in self.sent(server, device_id)
                     if message.get("op") == "publish"]
        self.assertEqual(published[-1]["msg"]["linear"], {"x": 0.2, "y": -0.1, "z": 0.0})
        self.assertEqual(published[-1]["msg"]["angular"], {"x": 0.0, "y": 0.0, "z": -0.4})

    def test_estop_is_unreached_and_latches(self) -> None:
        server, client, device_id = self.serve(overlay=False)
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED)
        refused = client.invoke(CMD_VEL, {"linear_x": 0.1, "linear_y": 0.0, "angular_z": 0.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_a_non_finite_range_is_refused_not_replaced(self) -> None:
        server, client, device_id = self.serve(overlay=False)
        server.devices[device_id].bridge.native.scan_ranges = [1.0, float("inf"), 3.0]
        receipt = client.invoke(SCAN, {}, **self.ids)
        self.assertIn(receipt["status"], ("failed", "unknown"), receipt)
        self.assertIsNone(receipt.get("output"))

    def test_malformed_scan_is_not_completed(self) -> None:
        driver = self.driver()
        driver.native.malformed_scan = True
        with self.assertRaises(Exception) as caught:  # noqa: BLE001 - the receipt must not be completed
            driver.call(SCAN, {})
        self.assertIn(getattr(caught.exception, "code", None),
                      {"MHS.CAPABILITY.OUTPUT_INVALID", "MHS.DEVICE.NOT_READY"})

    def test_declaration_is_a_simulated_ros1_mobile_base_without_a_stop(self) -> None:
        driver = self.driver()
        self.assertEqual(type(driver).ros_version, 1)
        self.assertEqual(type(driver).mode, "simulated")
        self.assertEqual(type(driver).risk, "R2")
        self.assertEqual(type(driver).device_kind, "robot.mobile_base")
        self.assertEqual(type(driver).backends, {"fake": ".fake:FakeSimulationUnitreeGo1"})
        self.assertEqual(dict(type(driver).safety_bindings), {})
        self.assertIsNone(type(driver).estop_physical_ref)
        self.assertEqual(type(driver).fidelity["fidelity_level"], "F0")


if __name__ == "__main__":
    unittest.main()

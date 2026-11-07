"""Acceptance run of the ENPS-DWA ROS package: the stock gate plus repository cases.

The fake is a ROS-free F0 transport. These cases exercise the declared /odom and
/scan360 subscriptions, the wire endpoint and type, malformed messages, silent
topics, wrong event ids and the software-only e-stop of an observation-only
simulator. No ROS graph, simulator process or hardware is contacted.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.bridge.base import BridgeContext
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ODOM = "x-cap.rgnc.enps_dwa_odometry.v1"
SCAN = "x-cap.rgnc.enps_dwa_scan.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class EnpsDwaCases(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, "fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        self.driver = driver
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_odometry_observation_returns_pose_twist_and_stamp(self) -> None:
        client = self.serve()
        receipt = client.invoke(ODOM, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["frame_id"], "odom")
        self.assertEqual(output["child_frame_id"], "base_link")
        self.assertEqual(output["pose"]["position"], {"x": 10.0, "y": 10.0, "z": 0.0})
        self.assertEqual(output["pose"]["orientation"], {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0})
        self.assertEqual(output["twist"]["linear"], {"x": 0.0, "y": 0.0, "z": 0.0})
        self.assertEqual(output["twist"]["angular"], {"x": 0.0, "y": 0.0, "z": 0.0})
        self.assertEqual(output["stamp"], {"secs": 12, "nsecs": 340000000})

    def test_the_scan_observation_returns_geometry_and_ranges(self) -> None:
        client = self.serve()
        receipt = client.invoke(SCAN, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        scan = receipt["output"]["scan"]
        self.assertEqual(scan["header"]["frame_id"], "base_link")
        self.assertEqual(scan["header"]["seq"], 0)
        self.assertEqual(scan["range_min"], 0.3)
        self.assertEqual(scan["range_max"], 2.5)
        self.assertEqual(scan["ranges"], [2.5, 2.5, 1.2, 0.8, 2.5, 2.5, 1.7, 2.5])
        self.assertEqual(scan["intensities"], [])
        self.assertAlmostEqual(scan["angle_min"], -3.141592653589793, places=12)
        self.assertAlmostEqual(scan["angle_max"], 3.141592653589793, places=12)
        self.assertGreater(scan["angle_increment"], 0.0)
        self.assertEqual(scan["header"]["stamp"], {"secs": 12, "nsecs": 340000000})

    def test_the_wire_subscriptions_use_the_pinned_endpoints_and_types(self) -> None:
        driver = self.driver()
        driver.call(ODOM, {})
        driver.call(SCAN, {})
        subscribes = [message for message in driver.native.sent if message.get("op") == "subscribe"]
        self.assertEqual([message["topic"] for message in subscribes], ["/odom", "/scan360"])
        self.assertEqual([message["type"] for message in subscribes],
                         ["nav_msgs/Odometry", "sensor_msgs/LaserScan"])
        unsubscribes = [message for message in driver.native.sent if message.get("op") == "unsubscribe"]
        self.assertEqual([message["topic"] for message in unsubscribes], ["/odom", "/scan360"])

    def test_a_silent_odom_topic_times_out_without_a_stale_value(self) -> None:
        driver = self.driver()
        driver.native.silent = True
        with self.assertRaises(Exception) as caught:
            driver.call(ODOM, {}, BridgeContext(deadline_ms=50))
        self.assertIn(getattr(caught.exception, "code", ""),
                      {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})

    def test_an_unrelated_event_id_does_not_satisfy_the_read(self) -> None:
        driver = self.driver()
        driver.native.wrong_id = True
        with self.assertRaises(Exception) as caught:
            driver.call(SCAN, {}, BridgeContext(deadline_ms=50))
        self.assertIn(getattr(caught.exception, "code", ""),
                      {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})

    def test_a_rejected_subscription_is_not_reported_as_a_value(self) -> None:
        driver = self.driver()
        driver.native.fail_subscribe = True
        with self.assertRaises(Exception):
            driver.call(ODOM, {}, BridgeContext(deadline_ms=50))
        self.assertEqual(driver.native.subscriptions, 1)

    def test_a_malformed_observation_is_refused(self) -> None:
        for capability, malformed in (
            (ODOM, "missing_pose"),
            (ODOM, "missing_twist"),
            (ODOM, "string_position"),
            (ODOM, "missing_stamp"),
            (SCAN, "missing_ranges"),
            (SCAN, "string_range"),
            (SCAN, "missing_header"),
        ):
            with self.subTest(capability=capability, malformed=malformed):
                client = self.serve()
                self.driver.native.malformed = malformed
                receipt = client.invoke(capability, {}, **self.ids)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID", receipt)
                self.assertIsNone(receipt["output"], receipt)

    def test_the_stock_estop_does_not_claim_a_native_stop(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "software_only", receipt)
        self.assertIs(receipt["output"]["latched"], True, receipt)
        # An extension observation has no catalogue-confirmed read exemption, so
        # it remains refused after the latch. This is a software latch only.
        refused = client.invoke(ODOM, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()

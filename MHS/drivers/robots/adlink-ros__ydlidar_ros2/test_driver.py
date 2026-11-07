"""Acceptance run of the YDLIDAR ROS 2 package: the stock gate plus repository cases.

The fake is a ROS-free F0 contract fake (a canned handler, not a replay of captured traffic).  These cases exercise the
declared /scan subscription, the LaserScan field mapping, the negative
transport paths, malformed messages and the software-only e-stop of a
read-only sensor.  No ROS graph, serial port, lidar or hardware is contacted.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.bridge.base import BridgeContext
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
SCAN = "x-cap.adlink-ros.laserscan.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class YdlidarCases(unittest.TestCase):
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

    def test_the_scan_observation_returns_every_laserscan_field(self) -> None:
        client = self.serve()
        receipt = client.invoke(SCAN, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["frame_id"], "laser_frame")
        self.assertEqual(output["stamp_sec"], 12)
        self.assertEqual(output["stamp_nanosec"], 340000000)
        self.assertEqual(output["ranges"], [1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertEqual(output["intensities"], [0.0, 0.0, 0.0, 0.0, 0.0])
        self.assertEqual(output["angle_min"], -1.5707963267948966)
        self.assertEqual(output["angle_max"], 1.5707963267948966)
        self.assertEqual(output["angle_increment"], 0.7853981633974483)
        self.assertEqual(output["scan_time"], 0.1)
        self.assertEqual(output["time_increment"], 0.0125)
        self.assertEqual(output["range_min"], 0.01)
        self.assertEqual(output["range_max"], 16.0)

    def test_the_wire_subscription_uses_the_pinned_endpoint_and_type(self) -> None:
        driver = self.driver()
        output = driver.call(SCAN, {})
        self.assertEqual(output["frame_id"], "laser_frame")
        subscribes = [message for message in driver.native.sent if message.get("op") == "subscribe"]
        self.assertEqual(len(subscribes), 1)
        self.assertEqual(subscribes[0]["topic"], "/scan")
        self.assertEqual(subscribes[0]["type"], "sensor_msgs/msg/LaserScan")
        self.assertEqual(subscribes[0]["queue_length"], 1)
        unsubscribes = [message for message in driver.native.sent if message.get("op") == "unsubscribe"]
        self.assertEqual([message["topic"] for message in unsubscribes], ["/scan"])

    def test_each_observation_opens_a_fresh_subscription(self) -> None:
        driver = self.driver()
        driver.call(SCAN, {})
        driver.call(SCAN, {})
        self.assertEqual(driver.native.subscriptions, 2)
        self.assertEqual([message.get("op") for message in driver.native.sent],
                         ["subscribe", "unsubscribe", "subscribe", "unsubscribe"])

    def test_the_driver_never_publishes_a_command(self) -> None:
        driver = self.driver()
        driver.call(SCAN, {})
        operations = {message.get("op") for message in driver.native.sent}
        self.assertEqual(operations, {"subscribe", "unsubscribe"})
        self.assertFalse(any(message.get("op") in {"advertise", "publish"} for message in driver.native.sent))

    def test_a_silent_topic_times_out_without_returning_a_stale_value(self) -> None:
        driver = self.driver()
        driver.native.silent = True
        with self.assertRaises(Exception) as caught:
            driver.call(SCAN, {}, BridgeContext(deadline_ms=50))
        self.assertIn(getattr(caught.exception, "code", ""),
                      {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})

    def test_an_unrelated_event_id_does_not_satisfy_the_read(self) -> None:
        driver = self.driver()
        driver.native.wrong_id = True
        with self.assertRaises(Exception) as caught:
            driver.call(SCAN, {}, BridgeContext(deadline_ms=50))
        self.assertIn(getattr(caught.exception, "code", ""),
                      {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})

    def test_a_failed_subscription_is_not_reported_as_a_value(self) -> None:
        driver = self.driver()
        driver.native.fail_subscribe = True
        with self.assertRaises(Exception):
            driver.call(SCAN, {}, BridgeContext(deadline_ms=50))
        self.assertEqual(driver.native.subscriptions, 1)

    def test_a_malformed_message_is_refused(self) -> None:
        for malformed in ("missing_header", "missing_ranges", "missing_intensities",
                          "string_range", "bad_stamp"):
            with self.subTest(malformed=malformed):
                server = load(HERE, backend="fake")
                self.addCleanup(close_server, server)
                client = client_for(server)
                device_id = client.hello()["devices"][0]["device_id"]
                session = client.open_session(device_ids=[device_id])["session_id"]
                fake = server._bridge(server._served_devices()[0]).native
                fake.malformed = malformed
                receipt = client.invoke(SCAN, {}, device_id=device_id, session_id=session)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertIsNone(receipt.get("output"), receipt)

    def test_the_stock_estop_does_not_claim_a_native_stop(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "software_only", receipt)
        self.assertIs(receipt["output"]["latched"], True, receipt)

    def test_the_read_is_refused_after_the_software_latch(self) -> None:
        client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        refused = client.invoke(SCAN, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the sick_scan_xd ROS package: the gate plus repository cases.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, OutcomeUnknown
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
SCAN = "x-cap.sickag.scan.v1"
TOPIC = "/scan"
TYPE = "sensor_msgs/msg/LaserScan"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SickScanCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_the_scan_observation_returns_the_full_laserscan_sample(self) -> None:
        client = self.serve()
        receipt = client.invoke(SCAN, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(set(output), {
            "frame_id", "stamp_sec", "stamp_nanosec", "angle_min", "angle_max",
            "angle_increment", "time_increment", "scan_time", "range_min",
            "range_max", "ranges", "intensities",
        })
        self.assertEqual(output["frame_id"], "fake_scan_frame")  # placeholder
        self.assertEqual(output["ranges"], [0.5, 1.0, 1.5, 2.0, 2.5])  # placeholder
        self.assertEqual(output["intensities"], [10.0, 20.0, 30.0, 40.0, 50.0])  # placeholder
        self.assertAlmostEqual(output["angle_min"] + (len(output["ranges"]) - 1) * output["angle_increment"], output["angle_max"])  # placeholder
        self.assertEqual(output["range_min"], 0.05)  # placeholder
        self.assertEqual(output["range_max"], 100.0)  # placeholder

    def test_the_subscription_names_the_declared_topic_type_and_depth(self) -> None:
        driver = self.driver()
        driver.call(SCAN, {})
        subscriptions = [message for message in driver.native.sent
                         if message.get("op") == "subscribe"]
        self.assertEqual(
            [(message["topic"], message["type"], message["queue_length"]) for message in subscriptions],
            [(TOPIC, TYPE, 1)],
        )
        self.assertTrue(any(message.get("op") == "unsubscribe" and message.get("topic") == TOPIC
                            for message in driver.native.sent), driver.native.sent)

    def test_the_resource_snapshot_is_empty(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.read("scan", []), {})
        self.assertFalse(any(message.get("op") in {"subscribe", "call_service", "advertise", "publish"}
                             for message in driver.native.sent))

    def test_a_message_without_ranges_is_not_reported_as_a_completed_scan(self) -> None:
        driver = self.driver()
        driver.native.omit_ranges = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call(SCAN, {})
        self.assertEqual(caught.exception.code, "MHS.CAPABILITY.OUTPUT_INVALID")

    def test_a_silent_scan_topic_is_not_a_completed_observation(self) -> None:
        driver = self.driver()
        driver.native.silent = True
        with self.assertRaises(MHSError) as caught:
            driver.call(SCAN, {})
        self.assertEqual(caught.exception.code, "MHS.DEVICE.NOT_READY")

    def test_the_scan_arrays_are_returned_as_plain_json_numbers(self) -> None:
        driver = self.driver()
        output = driver.call(SCAN, {})
        self.assertTrue(all(isinstance(value, float) for value in output["ranges"]))
        self.assertTrue(all(isinstance(value, float) for value in output["intensities"]))

    def test_nonfinite_range_is_not_reported_as_a_finite_distance(self) -> None:
        driver = self.driver()
        driver.native.ranges[0] = float("inf")
        with self.assertRaises(OutcomeUnknown):
            driver.call(SCAN, {})


if __name__ == "__main__":
    unittest.main()

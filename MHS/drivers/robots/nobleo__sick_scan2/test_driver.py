"""Acceptance run of the SICK scan2 ROS package: the gate plus package cases.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
SCAN = "x-cap.nobleo.laser_scan.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SickScan2Cases(unittest.TestCase):
    def serve(self, **options):
        server = load(HERE, backend="fake", options=options or None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_a_fresh_scan_observation_carries_native_laserscan_fields(self) -> None:
        client = self.serve()
        receipt = client.invoke(SCAN, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["frame_id"], "world")
        self.assertEqual(len(output["ranges"]), len(output["intensities"]))
        self.assertGreaterEqual(output["angle_max"], output["angle_min"])
        self.assertGreaterEqual(output["range_max"], output["range_min"])
        self.assertEqual(output["ranges"][0], 0.5)
        self.assertEqual(output["intensities"][0], 10.0)

    def test_each_observation_subscribes_again_and_receives_a_new_sample(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        first = driver.call(SCAN, {})
        second = driver.call(SCAN, {})
        self.assertNotEqual(first["stamp_nanosec"], second["stamp_nanosec"])
        subscriptions = [message for message in driver.native.sent
                         if message.get("op") == "subscribe"]
        self.assertEqual(len(subscriptions), 2)
        self.assertEqual(subscriptions[0]["topic"], "/scan")
        self.assertEqual(subscriptions[0]["type"], "sensor_msgs/msg/LaserScan")
        self.assertEqual(subscriptions[0]["queue_length"], 1)

    def test_a_missing_sample_times_out_without_inventing_a_scan(self) -> None:
        client = self.serve(silent=True)
        receipt = client.invoke(SCAN, {}, deadline_ms=80, **self.ids)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIn(receipt["error"]["mhs_code"],
                      {"MHS.DEVICE.NOT_READY", "MHS.OUTCOME.TIMEOUT"})
        self.assertIsNone(receipt.get("output"))

    def test_a_malformed_scan_message_is_not_mapped_into_a_scan(self) -> None:
        client = self.serve(malformed=True)
        receipt = client.invoke(SCAN, {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID")
        self.assertIsNone(receipt.get("output"))

    def test_nonfinite_range_has_no_fabricated_finite_output(self) -> None:
        client = self.serve(nonfinite=True)
        receipt = client.invoke(SCAN, {}, **self.ids)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIsNone(receipt.get("output"))


if __name__ == "__main__":
    unittest.main()

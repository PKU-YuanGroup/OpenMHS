"""Acceptance run of the rbot 2-D LiDAR driver: the gate, plus repository cases.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
CAP = "x-cap.rlxai.scan.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RbotScanCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_the_scan_observation_returns_the_declared_fields(self) -> None:
        client = self.serve()
        receipt = client.invoke(CAP, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["frame_id"], "lidar_2d_link")
        self.assertEqual(len(output["ranges"]), 8)
        self.assertEqual(len(output["intensities"]), 8)
        self.assertIn("stamp", output)
        self.assertLessEqual(output["range_min"], output["range_max"])

    def test_each_observation_opens_a_fresh_scan_subscription(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(driver.call(CAP, {})["frame_id"], "lidar_2d_link")
        self.assertEqual(driver.call(CAP, {})["frame_id"], "lidar_2d_link")
        subscriptions = [message for message in driver.native.sent if message.get("op") == "subscribe"]
        self.assertEqual(len(subscriptions), 2)
        self.assertTrue(all(message.get("topic") == "/scan" for message in subscriptions))
        self.assertTrue(all(message.get("type") == "sensor_msgs/msg/LaserScan"
                            for message in subscriptions))

    def test_a_silent_scan_stream_does_not_invent_a_sample(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.no_scan = True
        with self.assertRaises(MHSError) as caught:
            driver.call(CAP, {})
        self.assertIn(caught.exception.code, {"MHS.DEVICE.NOT_READY", "MHS.OUTCOME.TIMEOUT"})

    def test_a_transport_valid_but_incomplete_scan_is_refused(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.malformed_scan = True
        with self.assertRaises(MHSError) as caught:
            driver.call(CAP, {})
        self.assertEqual(caught.exception.code, "MHS.CAPABILITY.OUTPUT_INVALID")

    def test_a_nonfinite_range_has_no_fabricated_output(self) -> None:
        # Model review 2026-11-05: a non-finite range is refused, never replaced by a number.
        driver = load_driver(HERE, "fake")
        driver.native.nonfinite_scan = True
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.invoke(CAP, {}, device_id=device_id, session_id=session)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIsNone(receipt.get("output"))

    def test_the_stock_estop_is_software_only_for_this_passive_sensor(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "software_only")


if __name__ == "__main__":
    unittest.main()

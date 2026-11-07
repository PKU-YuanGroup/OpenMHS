"""Acceptance run of the URSim ROS 1 observation package: the gate plus repository cases.

The fake is a ROS-free F0 canned transport.  These cases exercise the three
declared subscriptions, the pinned endpoint/type pairs, silent and malformed
replies, a mismatched subscription id and the software-only e-stop of a
read-only simulated device.  No ROS graph, Unity process or hardware is
contacted.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.bridge.base import BridgeContext
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
DEPTH = "x-cap.srmauvsoftware.depth.v1"
HEADING = "x-cap.srmauvsoftware.heading.v1"
IMU = "x-cap.srmauvsoftware.imu.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class UrsimCases(unittest.TestCase):
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

    def test_the_depth_observation_returns_the_float64_data_value(self) -> None:
        client = self.serve()
        receipt = client.invoke(DEPTH, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["depth"], 12.5)  # placeholder fake value

    def test_the_heading_observation_returns_the_float64_data_value(self) -> None:
        client = self.serve()
        receipt = client.invoke(HEADING, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["heading_deg"], 87.0)  # placeholder fake value

    def test_the_imu_observation_returns_the_message_fields(self) -> None:
        client = self.serve()
        receipt = client.invoke(IMU, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["orientation"], {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0})
        self.assertEqual(output["angular_velocity"], {"x": 0.0, "y": 0.0, "z": 0.0})
        self.assertEqual(len(output["orientation_covariance"]), 9)
        self.assertEqual(output["header"]["stamp"], {"secs": 12, "nsecs": 340000000})

    def test_the_wire_subscriptions_use_the_pinned_endpoints_and_types(self) -> None:
        driver = self.driver()
        driver.call(DEPTH, {})
        driver.call(HEADING, {})
        driver.call(IMU, {})
        subscribes = [message for message in driver.native.sent if message.get("op") == "subscribe"]
        pairs = {(message["topic"], message.get("type")) for message in subscribes}
        self.assertEqual(pairs, {
            ("/depth", "std_msgs/Float64"),
            ("/imu/HeadingTrue_degree", "std_msgs/Float64"),
            ("/imu/data", "sensor_msgs/Imu"),
        })

    def test_a_silent_topic_times_out_without_returning_a_stale_value(self) -> None:
        driver = self.driver()
        driver.native.silent = True
        with self.assertRaises(Exception) as caught:
            driver.call(DEPTH, {}, BridgeContext(deadline_ms=50))
        self.assertIn(getattr(caught.exception, "code", ""),
                      {"MHS.DEVICE.NOT_READY", "MHS.OUTCOME.TIMEOUT"})

    def test_a_mismatched_subscription_id_times_out(self) -> None:
        driver = self.driver()
        driver.native.wrong_id = True
        with self.assertRaises(Exception) as caught:
            driver.call(HEADING, {}, BridgeContext(deadline_ms=50))
        self.assertIn(getattr(caught.exception, "code", ""),
                      {"MHS.DEVICE.NOT_READY", "MHS.OUTCOME.TIMEOUT"})

    def test_a_malformed_sample_is_a_failure_not_a_zero_value(self) -> None:
        driver = self.driver()
        driver.native.malformed = True
        with self.assertRaises(Exception) as caught:
            driver.call(IMU, {}, BridgeContext(deadline_ms=500))
        self.assertTrue(getattr(caught.exception, "code", "").startswith("MHS."))

    def test_the_e_stop_is_a_software_latch_and_keeps_extension_reads_latched(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "software_only")
        refused = client.invoke(DEPTH, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")

    def test_no_writable_or_native_stop_binding_is_declared(self) -> None:
        driver = self.driver()
        self.assertEqual(set(driver.commands), {DEPTH, HEADING, IMU})
        self.assertEqual(dict(driver.safety_bindings), {})


if __name__ == "__main__":
    unittest.main()

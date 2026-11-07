"""Acceptance run of the TrackIMU ROS 2 package: the stock gate plus repository cases.

The fake is a ROS-free F0 recording transport.  These cases exercise the
declared /imu subscription, the class output conversion, the body/world frame
choice, malformed messages, a silent topic and the software-only e-stop of a
read-only sensor.  No ROS graph, serial port or hardware is contacted.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.bridge.base import BridgeContext
from mhs.driver import DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
IMU = "cap.sensing.imu.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class TrackImuCases(unittest.TestCase):
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

    def test_the_imu_observation_returns_arrays_and_a_stamp(self) -> None:
        client = self.serve()
        receipt = client.invoke(IMU, {"frame": "body"}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["orientation"], {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0})
        self.assertEqual(output["linear_acceleration"], [0.0, 0.0, 0.0])
        self.assertEqual(output["angular_velocity"], [0.0, 0.0, 0.0])
        self.assertEqual(output["sampled_at"], "1970-01-01T00:00:12.340000000Z")

    def test_the_wire_subscription_uses_the_pinned_endpoint_and_type(self) -> None:
        driver = self.driver()
        output = driver.call(IMU, {"frame": "body"})
        self.assertEqual(output["linear_acceleration"], [0.0, 0.0, 0.0])
        subscribes = [message for message in driver.native.sent if message.get("op") == "subscribe"]
        self.assertEqual(len(subscribes), 1)
        self.assertEqual(subscribes[0]["topic"], "/imu")
        self.assertEqual(subscribes[0]["type"], "sensor_msgs/msg/Imu")
        unsubscribes = [message for message in driver.native.sent if message.get("op") == "unsubscribe"]
        self.assertEqual([message["topic"] for message in unsubscribes], ["/imu"])

    def test_world_frame_rotates_the_reported_vectors(self) -> None:
        driver = self.driver()
        half = math.sqrt(0.5)
        driver.native.orientation = {"x": 0.0, "y": 0.0, "z": half, "w": half}
        driver.native.angular_velocity = {"x": 1.0, "y": 0.0, "z": 0.0}
        body = driver.call(IMU, {"frame": "body"})
        world = driver.call(IMU, {"frame": "world"})
        self.assertEqual(body["angular_velocity"], [1.0, 0.0, 0.0])
        for actual, expected in zip(world["angular_velocity"], [0.0, 1.0, 0.0]):
            self.assertAlmostEqual(actual, expected, places=6)

    def test_a_silent_topic_times_out_without_returning_a_stale_value(self) -> None:
        driver = self.driver()
        driver.native.silent = True
        with self.assertRaises(Exception) as caught:
            driver.call(IMU, {"frame": "body"}, BridgeContext(deadline_ms=50))
        self.assertIn(getattr(caught.exception, "code", ""),
                      {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})

    def test_an_unrelated_event_id_does_not_satisfy_the_read(self) -> None:
        driver = self.driver()
        driver.native.wrong_id = True
        with self.assertRaises(Exception) as caught:
            driver.call(IMU, {"frame": "body"}, BridgeContext(deadline_ms=50))
        self.assertIn(getattr(caught.exception, "code", ""),
                      {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})

    def test_a_rejected_subscription_is_not_reported_as_a_value(self) -> None:
        driver = self.driver()
        driver.native.fail_subscribe = True
        with self.assertRaises(Exception):
            driver.call(IMU, {"frame": "body"}, BridgeContext(deadline_ms=50))
        self.assertEqual(driver.native.subscriptions, 1)

    def test_a_malformed_message_is_refused(self) -> None:
        for malformed in ("missing_orientation", "missing_linear_acceleration",
                          "string_orientation", "bad_stamp"):
            with self.subTest(malformed=malformed):
                driver = self.driver()
                driver.native.malformed = malformed
                with self.assertRaises(DriverFailed) as caught:
                    driver.call(IMU, {"frame": "body"})
                self.assertEqual(caught.exception.code, "MHS.CAPABILITY.OUTPUT_INVALID")

    def test_the_stock_estop_does_not_claim_a_native_stop(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "software_only", receipt)
        # There is no actuating capability to stop, so the SDK records the
        # latch as achieved; this is not a native or physical stop claim.
        self.assertIs(receipt["output"]["latched"], True, receipt)
        # A catalogue-confirmed read class keeps its latch exemption.
        observation = client.invoke(IMU, {"frame": "body"}, **self.ids)
        self.assertEqual(observation["status"], "completed", observation)
        self.assertEqual(observation["output"]["linear_acceleration"], [0.0, 0.0, 0.0])
        refused = client.invoke(IMU, {"frame": "invalid"}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)


if __name__ == "__main__":
    unittest.main()

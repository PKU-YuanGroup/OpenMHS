"""Acceptance run of the Hakoniwa infra-sensor package: the stock gate plus repository cases.

The fake is a ROS-free F0 canned transport.  These cases exercise the declared
``/TB3RoboAvatar_cmd_pos`` subscription, the ``cap.sensing.read.v1`` channel
projection, malformed messages, a silent topic and the software-only e-stop of a
read-only sensor.  No ROS graph, LiDAR or hardware is contacted.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.bridge.base import BridgeContext
from mhs.driver import DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
POSE = "cap.sensing.read.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class HakoniwaInfraSensorCases(unittest.TestCase):
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

    def test_the_pose_observation_returns_six_channels_and_a_stamp(self) -> None:
        client = self.serve()
        receipt = client.invoke(POSE, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(set(output["values"]), {"x", "y", "z", "roll", "pitch", "yaw"})
        self.assertEqual(output["values"]["x"], 0.27)
        self.assertEqual(output["values"]["y"], 0.02)
        self.assertEqual(output["values"]["z"], 0.0)
        self.assertEqual(output["values"]["yaw"], 0.0)
        self.assertTrue(output["sampled_at"].endswith("Z"), output["sampled_at"])

    def test_selecting_fields_filters_the_channels(self) -> None:
        client = self.serve()
        receipt = client.invoke(POSE, {"fields": ["x", "yaw"]}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["values"], {"x": 0.27, "yaw": 0.0})

    def test_an_unknown_channel_is_ignored(self) -> None:
        client = self.serve()
        receipt = client.invoke(POSE, {"fields": ["temperature"]}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["values"], {})

    def test_the_wire_subscription_uses_the_pinned_endpoint_and_type(self) -> None:
        driver = self.driver()
        output = driver.call(POSE, {})
        self.assertEqual(output["values"]["x"], 0.27)
        subscribes = [message for message in driver.native.sent if message.get("op") == "subscribe"]
        self.assertEqual(len(subscribes), 1)
        self.assertEqual(subscribes[0]["topic"], "/TB3RoboAvatar_cmd_pos")
        self.assertEqual(subscribes[0]["type"], "geometry_msgs/msg/Twist")
        unsubscribes = [message for message in driver.native.sent if message.get("op") == "unsubscribe"]
        self.assertEqual([message["topic"] for message in unsubscribes], ["/TB3RoboAvatar_cmd_pos"])

    def test_a_silent_topic_times_out_without_returning_a_stale_value(self) -> None:
        driver = self.driver()
        driver.native.silent = True
        with self.assertRaises(Exception) as caught:
            driver.call(POSE, {}, BridgeContext(deadline_ms=50))
        self.assertIn(getattr(caught.exception, "code", ""),
                      {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})

    def test_an_unrelated_event_id_does_not_satisfy_the_read(self) -> None:
        driver = self.driver()
        driver.native.wrong_id = True
        with self.assertRaises(Exception) as caught:
            driver.call(POSE, {}, BridgeContext(deadline_ms=50))
        self.assertIn(getattr(caught.exception, "code", ""),
                      {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})

    def test_a_rejected_subscription_is_not_reported_as_a_value(self) -> None:
        driver = self.driver()
        driver.native.fail_subscribe = True
        with self.assertRaises(Exception):
            driver.call(POSE, {}, BridgeContext(deadline_ms=50))
        self.assertEqual(driver.native.subscriptions, 1)

    def test_malformed_messages_are_refused(self) -> None:
        for malformed in ("missing_linear", "missing_angular", "string_component", "missing_axis"):
            with self.subTest(malformed=malformed):
                driver = self.driver()
                driver.native.malformed = malformed
                with self.assertRaises(DriverFailed) as caught:
                    driver.call(POSE, {})
                self.assertEqual(caught.exception.code, "MHS.CAPABILITY.OUTPUT_INVALID")

    def test_a_nonfinite_angle_is_not_returned_as_a_value(self) -> None:
        # The node's np.arcsin pitch can be NaN.  The SDK's rosbridge transports refuse non-finite JSON
        # numbers, and the driver refuses any non-finite component that reaches it: no value either way.
        driver = self.driver()
        driver.native.malformed = "nonfinite_pitch"
        with self.assertRaises(Exception) as caught:
            driver.call(POSE, {}, BridgeContext(deadline_ms=50))
        self.assertIn(getattr(caught.exception, "code", ""),
                      {"MHS.OUTCOME.UNKNOWN", "MHS.CAPABILITY.OUTPUT_INVALID"})

    def test_a_non_object_topic_sample_is_not_a_value(self) -> None:
        driver = self.driver()
        driver.native.malformed = "not_an_object"
        with self.assertRaises(Exception) as caught:
            driver.call(POSE, {}, BridgeContext(deadline_ms=50))
        self.assertIn(getattr(caught.exception, "code", ""),
                      {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})

    def test_the_stock_estop_does_not_claim_a_native_stop(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "software_only", receipt)
        self.assertIs(receipt["output"]["latched"], True, receipt)
        # A catalogue-confirmed read class keeps its latch exemption.
        observation = client.invoke(POSE, {}, **self.ids)
        self.assertEqual(observation["status"], "completed", observation)
        self.assertEqual(observation["output"]["values"]["x"], 0.27)


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the quad_sim observation package.

The stock gate is kept; the added cases exercise the two declared
subscriptions, their pinned endpoint/type pairs, malformed and silent
messages, the absence of any actuation operation and the software-only e-stop
of a read-only profile.  No ROS graph, Gazebo process or hardware is used.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.bridge.base import BridgeContext
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent

POSE = "x-cap.rumaisaabdulhai.ground_truth_pose.v1"
STATUS = "x-cap.rumaisaabdulhai.goal_status.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"

ENDPOINTS = {
    POSE: ("/ground_truth_to_tf/pose", "geometry_msgs/PoseStamped"),
    STATUS: ("/move_base/status", "actionlib_msgs/GoalStatusArray"),
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class QuadSimCases(unittest.TestCase):
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

    def test_the_pose_observation_returns_the_fake_pose(self) -> None:
        receipt = self.serve().invoke(POSE, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        message = receipt["output"]["pose"]
        self.assertEqual(message["header"]["frame_id"], "world")
        self.assertEqual(message["header"]["stamp"], {"secs": 12, "nsecs": 340000000})
        self.assertEqual(message["pose"]["position"], {"x": 1.0, "y": 2.0, "z": 0.3})
        self.assertEqual(message["pose"]["orientation"],
                         {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0})

    def test_the_goal_status_observation_returns_the_fake_status_list(self) -> None:
        receipt = self.serve().invoke(STATUS, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        message = receipt["output"]["goal_status"]
        self.assertEqual(message["status_list"][0]["goal_id"]["id"], "goal-1")
        self.assertEqual(message["status_list"][0]["status"], 1)
        self.assertEqual(message["status_list"][0]["text"], "active")

    def test_each_read_subscribes_to_the_pinned_endpoint_and_type(self) -> None:
        for capability, (topic, message_type) in ENDPOINTS.items():
            with self.subTest(capability=capability):
                driver = self.driver()
                driver.call(capability, {})
                subscribes = [message for message in driver.native.sent
                              if message.get("op") == "subscribe"]
                self.assertEqual(len(subscribes), 1)
                self.assertEqual(subscribes[0]["topic"], topic)
                self.assertEqual(subscribes[0]["type"], message_type)
                unsubscribes = [message for message in driver.native.sent
                                if message.get("op") == "unsubscribe"]
                self.assertEqual([message["topic"] for message in unsubscribes], [topic])

    def test_the_profile_sends_no_actuation_operation(self) -> None:
        driver = self.driver()
        for capability in ENDPOINTS:
            driver.call(capability, {})
        operations = {message.get("op") for message in driver.native.sent}
        self.assertEqual(operations, {"subscribe", "unsubscribe"})

    def test_a_silent_topic_is_an_explicit_observation_failure(self) -> None:
        driver = self.driver()
        driver.native.silent_topic = "/ground_truth_to_tf/pose"
        with self.assertRaises(Exception) as caught:
            driver.call(POSE, {}, BridgeContext(deadline_ms=50))
        self.assertIn(getattr(caught.exception, "code", ""),
                      {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})

    def test_an_unrelated_publication_id_does_not_satisfy_the_read(self) -> None:
        driver = self.driver()
        driver.native.wrong_id = True
        with self.assertRaises(Exception) as caught:
            driver.call(STATUS, {}, BridgeContext(deadline_ms=50))
        self.assertIn(getattr(caught.exception, "code", ""),
                      {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})

    def test_a_failed_subscription_is_not_reported_as_a_value(self) -> None:
        driver = self.driver()
        driver.native.fail_subscribe = True
        with self.assertRaises(Exception):
            driver.call(POSE, {}, BridgeContext(deadline_ms=50))
        self.assertEqual(len(driver.native.subscriptions), 1)

    def test_malformed_messages_are_refused(self) -> None:
        for capability, topic in ((POSE, "/ground_truth_to_tf/pose"),
                                  (STATUS, "/move_base/status")):
            with self.subTest(capability=capability):
                driver = load_driver(HERE, "fake")
                driver.native.malformed_topic = topic
                server = build_server(driver)
                self.addCleanup(close_server, server)
                client = client_for(server)
                device_id = client.hello()["devices"][0]["device_id"]
                session = client.open_session(device_ids=[device_id])["session_id"]
                receipt = client.invoke(capability, {}, device_id=device_id, session_id=session)
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID")

    def test_the_stock_estop_is_software_only_and_latches_extension_reads(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "software_only", receipt)
        self.assertIs(receipt["output"]["latched"], True, receipt)
        refused = client.invoke(POSE, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()

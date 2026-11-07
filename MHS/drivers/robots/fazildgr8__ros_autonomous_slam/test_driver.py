"""Acceptance run of the ros_autonomous_slam observation package.

The stock gate is kept; the added cases exercise the five declared
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

MAP = "x-cap.fazildgr8.occupancy_map.v1"
FRONTIERS = "x-cap.fazildgr8.frontiers.v1"
REGION = "x-cap.fazildgr8.exploration_region.v1"
ODOM = "x-cap.fazildgr8.odometry.v1"
SCAN = "x-cap.fazildgr8.scan.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"

ENDPOINTS = {
    MAP: ("/map", "nav_msgs/OccupancyGrid"),
    FRONTIERS: ("/filtered_points", "ros_autonomous_slam/PointArray"),
    REGION: ("/clicked_point", "geometry_msgs/PointStamped"),
    ODOM: ("/odom", "nav_msgs/Odometry"),
    SCAN: ("/scan", "sensor_msgs/LaserScan"),
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RosAutonomousSlamCases(unittest.TestCase):
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

    def test_the_occupancy_map_observation_returns_the_fake_grid(self) -> None:
        receipt = self.serve().invoke(MAP, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        message = receipt["output"]["map"]
        self.assertEqual(message["header"]["frame_id"], "map")
        self.assertEqual(message["info"]["width"], 4)
        self.assertEqual(message["info"]["height"], 3)
        self.assertEqual(message["info"]["resolution"], 0.05)
        self.assertEqual(len(message["data"]), 12)
        self.assertIn(-1, message["data"])
        self.assertEqual(message["header"]["stamp"], {"secs": 12, "nsecs": 340000000})

    def test_the_frontier_observation_returns_points(self) -> None:
        receipt = self.serve().invoke(FRONTIERS, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        points = receipt["output"]["frontiers"]["points"]
        self.assertEqual(len(points), 3)
        self.assertEqual(points[0], {"x": 1.0, "y": 2.0, "z": 0.0})

    def test_the_exploration_region_observation_returns_one_operator_point(self) -> None:
        receipt = self.serve().invoke(REGION, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        message = receipt["output"]["region_point"]
        self.assertEqual(message["header"]["frame_id"], "map")
        self.assertEqual(message["point"], {"x": -2.0, "y": 0.5, "z": 0.0})

    def test_the_odometry_observation_returns_pose_and_twist(self) -> None:
        receipt = self.serve().invoke(ODOM, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        message = receipt["output"]["odometry"]
        self.assertEqual(message["child_frame_id"], "base_footprint")
        self.assertEqual(message["pose"]["pose"]["position"], {"x": 0.5, "y": -0.25, "z": 0.0})
        self.assertEqual(message["pose"]["pose"]["orientation"],
                         {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0})
        self.assertEqual(message["twist"]["twist"]["linear"], {"x": 0.2, "y": 0.0, "z": 0.0})
        self.assertEqual(message["twist"]["twist"]["angular"], {"x": 0.0, "y": 0.0, "z": 0.1})

    def test_the_scan_observation_returns_a_bounded_fake_array(self) -> None:
        receipt = self.serve().invoke(SCAN, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        message = receipt["output"]["scan"]
        self.assertEqual(message["header"]["frame_id"], "base_scan")
        self.assertEqual(len(message["ranges"]), 8)
        self.assertEqual(len(message["intensities"]), 8)
        self.assertEqual(message["range_min"], 0.12)
        self.assertEqual(message["range_max"], 3.5)

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
        driver.native.silent_topic = "/map"
        with self.assertRaises(Exception) as caught:
            driver.call(MAP, {}, BridgeContext(deadline_ms=50))
        self.assertIn(getattr(caught.exception, "code", ""),
                      {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})

    def test_an_unrelated_publication_id_does_not_satisfy_the_read(self) -> None:
        driver = self.driver()
        driver.native.wrong_id = True
        with self.assertRaises(Exception) as caught:
            driver.call(MAP, {}, BridgeContext(deadline_ms=50))
        self.assertIn(getattr(caught.exception, "code", ""),
                      {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})

    def test_malformed_messages_are_refused(self) -> None:
        for capability, (topic, _message_type) in ENDPOINTS.items():
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

    def test_a_nonfinite_scan_range_has_no_fabricated_output(self) -> None:
        # Model review 2026-11-05: a no-return range encoded as a non-finite number is refused, not mapped.
        driver = load_driver(HERE, "fake")
        driver.native.nonfinite_scan = True
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.invoke(SCAN, {}, device_id=device_id, session_id=session)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIsNone(receipt.get("output"))

    def test_the_stock_estop_is_software_only_and_latches_extension_reads(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "software_only", receipt)
        self.assertIs(receipt["output"]["latched"], True, receipt)
        refused = client.invoke(MAP, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()

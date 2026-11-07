import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FlightforgeCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_clock_observation_returns_a_ros2_time(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.ctu-mrs.clock.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(set(receipt["output"]["sim_time"]), {"sec", "nanosec"})

    def test_pose_observation_returns_frame_stamp_and_poses(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.ctu-mrs.uav_poses.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(set(output["stamp"]), {"sec", "nanosec"})
        self.assertTrue(output["frame_id"])
        self.assertGreaterEqual(len(output["poses"]), 1)
        self.assertEqual(set(output["poses"][0]["position"]), {"x", "y", "z"})
        self.assertEqual(set(output["poses"][0]["orientation"]), {"x", "y", "z", "w"})

    def test_subscriptions_reach_the_upstream_topics_and_types(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.call("x-cap.ctu-mrs.clock.v1", {})
        driver.call("x-cap.ctu-mrs.uav_poses.v1", {})
        subscriptions = [message for message in driver.native.sent
                         if message.get("op") == "subscribe"]
        self.assertEqual([message.get("topic") for message in subscriptions],
                         ["/clock", "/flightforge_simulator/uav_poses"])
        self.assertEqual([message.get("type") for message in subscriptions],
                         ["rosgraph_msgs/msg/Clock", "geometry_msgs/msg/PoseArray"])

    def served_driver(self, **flags):
        driver = load_driver(HERE, "fake")
        for name, value in flags.items():
            setattr(driver.native, name, value)
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_a_silent_clock_fails_before_the_deadline(self) -> None:
        client = self.served_driver(silent_clock=True)
        receipt = client.invoke("x-cap.ctu-mrs.clock.v1", {}, deadline_ms=50, **self.ids)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIsNone(receipt.get("output"))

    def test_a_malformed_clock_is_refused(self) -> None:
        client = self.served_driver(malformed_clock=True)
        receipt = client.invoke("x-cap.ctu-mrs.clock.v1", {}, **self.ids)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIsNone(receipt.get("output"))

    def test_an_estop_latches_the_extension_observation(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIn(receipt["output"]["estop"], {"engaged", "software_only"})
        refused = client.invoke("x-cap.ctu-mrs.clock.v1", {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()

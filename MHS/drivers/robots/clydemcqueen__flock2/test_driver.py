"""Acceptance and package-specific cases for the flock2 ROS package.

The gate case is expected to fail at G3 until the upstream provides an
acknowledged stop; the package-specific cases exercise the honest topic
contract and the operator-required cmd_vel envelope on the fake backend.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, OutcomeUnknown
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
START = "x-cap.clydemcqueen.start_mission.v1"
STOP = "x-cap.clydemcqueen.stop_mission.v1"
CMD_VEL = "x-cap.clydemcqueen.cmd_vel.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Flock2Cases(unittest.TestCase):
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

    def test_mission_publications_reach_the_fake(self) -> None:
        driver = self.driver()
        self.assertTrue(driver.call(START, {})["published"])
        self.assertTrue(driver.native.mission)
        self.assertTrue(driver.call(STOP, {})["published"])
        self.assertFalse(driver.native.mission)
        self.assertEqual(driver.native.stop_requests, 1)
        sent_topics = [message.get("topic") for message in driver.native.sent
                       if message.get("op") == "publish"]
        self.assertEqual(sent_topics, ["/start_mission", "/stop_mission"])

    def test_cmd_vel_is_refused_until_the_operator_supplies_bounds(self) -> None:
        client = self.serve()
        receipt = client.invoke(CMD_VEL, {"linear_x": 0.0, "linear_y": 0.0,
                                          "linear_z": 0.0, "angular_z": 0.0}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")

    def test_the_odometry_read_returns_the_subscribed_sample(self) -> None:
        driver = self.driver()
        position = driver.read("main", fields=["odom_position"])["odom_position"]
        self.assertEqual(set(position), {"x", "y", "z"})

    def test_a_malformed_odometry_message_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.malformed_odom = True
        with self.assertRaises(MHSError) as caught:
            driver.read("main", fields=["odom_position"])
        self.assertEqual(caught.exception.code, "MHS.DEVICE.NOT_READY")

    def test_a_rejected_publication_does_not_complete(self) -> None:
        driver = self.driver()
        driver.native.reject_publish = True
        with self.assertRaises(OutcomeUnknown):
            driver.call(START, {})

    def test_stop_mission_is_not_an_estop(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertFalse(receipt.get("output", {}).get("estop") == "engaged"
                         and receipt.get("output", {}).get("safe_state_achieved") is True)


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the MuJoCo ROS utilities package: the gate, plus cases for this plugin graph.

The gate is expected to fail on the missing acknowledged stop for the actuator
publication; ``RESULT.json`` records that blocker.  These cases keep the
observable contract and the operator-required-limit behavior exercised
independently of that blocker.

Add cases, never remove the check_driver call.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
CLOCK = "x-cap.isri-aist.clock.v1"
BODY_POSE = "x-cap.isri-aist.body_pose.v1"
BODY_TWIST = "x-cap.isri-aist.body_twist.v1"
RANGEFINDER = "x-cap.isri-aist.rangefinder.v1"
ACTUATOR = "x-cap.isri-aist.actuator_command.v1"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"


def example_overlay():
    return json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MujocoRosUtilsCases(unittest.TestCase):
    def serve(self, *, overlay=True):
        server = load(HERE, backend="fake", site_limits=example_overlay() if overlay else None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def direct(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver, driver.native

    def test_the_clock_observation_returns_a_clock_sample(self) -> None:
        client = self.serve()
        receipt = client.invoke(CLOCK, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(set(receipt["output"]["sim_time"]), {"sec", "nanosec"})

    def test_the_pose_observation_returns_position_and_frame(self) -> None:
        client = self.serve()
        receipt = client.invoke(BODY_POSE, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIn("position", receipt["output"]["pose"])
        self.assertIn("orientation", receipt["output"]["pose"])
        self.assertEqual(receipt["output"]["frame_id"], "map")

    def test_the_twist_observation_returns_linear_and_angular(self) -> None:
        client = self.serve()
        receipt = client.invoke(BODY_TWIST, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIn("linear", receipt["output"]["twist"])
        self.assertIn("angular", receipt["output"]["twist"])

    def test_the_rangefinder_observation_returns_a_scalar(self) -> None:
        client = self.serve()
        receipt = client.invoke(RANGEFINDER, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["distance"], 0.5)

    def test_the_actuator_publication_is_not_confirmed(self) -> None:
        client = self.serve()
        receipt = client.invoke(ACTUATOR, {"value": 0.25}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["published"])
        self.assertFalse(receipt["output"]["confirmed"])
        self.assertEqual(receipt["output"]["message"], {"data": 0.25})

    def test_the_actuator_publication_without_an_overlay_is_refused(self) -> None:
        client = self.serve(overlay=False)
        receipt = client.invoke(ACTUATOR, {"value": 0.0}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)

    def test_a_missing_pose_sample_is_reported_as_a_failure(self) -> None:
        driver, fake = self.direct()
        fake.omit_pose = True
        with self.assertRaises(MHSError):
            driver.call(BODY_POSE, {})

    def test_the_observations_do_not_publish(self) -> None:
        driver, fake = self.direct()
        driver.call(CLOCK, {})
        driver.call(BODY_POSE, {})
        driver.call(BODY_TWIST, {})
        driver.call(RANGEFINDER, {})
        self.assertFalse([message for message in fake.sent if message.get("op") == "publish"
                          and message.get("topic") != "/clock"])


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the swarm_stage_ros package: the gate, plus cases specific to this simulator.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import OutcomeUnknown
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
UNSET = "MHS.SAFETY.LIMITS_UNSET"
SAFE_STATE_UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
CAP = "x-cap.viviancremerkalempa.target_pose.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SwarmStageCases(unittest.TestCase):
    def serve(self, **options):
        server = load(HERE, backend="fake", **options)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_the_target_is_advertised_and_published_on_robot_0(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        receipt = driver.call(CAP, {"x": 1.5, "y": -2.0})
        self.assertTrue(receipt["submitted"])
        self.assertFalse(receipt["confirmed"])
        operations = [(message.get("op"), message.get("topic"), message.get("type"))
                      for message in driver.native.sent]
        self.assertEqual(operations, [("advertise", "/robot_0", "turtlesim/Pose"),
                                      ("publish", "/robot_0", None)])
        self.assertEqual(driver.native.last_target["x"], 1.5)
        self.assertEqual(driver.native.last_target["y"], -2.0)
        self.assertEqual(driver.native.last_target["theta"], 0.0)
        self.assertEqual(driver.native.last_target["linear_velocity"], 0.0)
        self.assertEqual(driver.native.last_target["angular_velocity"], 0.0)

    def test_two_targets_produce_two_distinct_recorded_poses(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.call(CAP, {"x": 1.0, "y": 2.0})
        first = dict(driver.native.last_target)
        driver.call(CAP, {"x": -1.0, "y": -2.0})
        second = dict(driver.native.last_target)
        self.assertNotEqual(first, second)
        self.assertEqual(driver.native.publish_count, 2)

    def test_an_uncertain_publication_is_not_reported_as_success(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_publish = True
        with self.assertRaises(OutcomeUnknown) as caught:
            driver.call(CAP, {"x": 1.0, "y": 2.0})
        self.assertEqual(caught.exception.code, "MHS.OUTCOME.UNKNOWN")
        self.assertIsNone(driver.native.last_target)

    def test_operator_required_pose_limits_refuse_the_invoke(self) -> None:
        client = self.serve()
        receipt = client.invoke(CAP, {"x": 1.0, "y": 2.0}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)

    def test_the_target_receipt_is_transmission_only_with_an_operator_envelope(self) -> None:
        client = self.serve(site_limits=HERE / "site-limits.example.json")
        receipt = client.invoke(CAP, {"x": 0.5, "y": -0.5}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"submitted": True, "confirmed": False})

    def test_no_safe_state_is_claimed_without_an_acknowledged_stop(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], SAFE_STATE_UNREACHED)


if __name__ == "__main__":
    unittest.main()

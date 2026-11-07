"""Acceptance run of the Mavswarm2 package: the gate, plus simulator-specific cases.

The gate is expected to fail on the missing acknowledged stop (G6.ESTOP_FAILED and
the matching SAFE-028 in G8); RESULT.json records that blocker.  These cases keep the
observable wire contract and the publication-only behavior exercised independently of
that blocker.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
DESIRED = "x-cap.malintha.desired_state.v1"
TRAJECTORY = "x-cap.malintha.trajectory.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Mavswarm2Cases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
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

    def test_the_trajectory_observation_returns_the_last_map_point(self) -> None:
        client = self.serve()
        receipt = client.invoke(TRAJECTORY, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["frame_id"], "map")
        self.assertEqual(set(receipt["output"]["position"]), {"x", "y", "z"})

    def test_the_desired_state_publication_reaches_the_topic_and_is_not_confirmed(self) -> None:
        driver, fake = self.direct()
        result = driver.call(DESIRED, {"x": 2.0, "y": -1.5, "z": 2.0})
        self.assertTrue(result["published"])
        self.assertFalse(result["confirmed"])
        self.assertEqual(fake.last_goal, {"x": 2.0, "y": -1.5, "z": 2.0})
        sent = [{key: message.get(key) for key in ("op", "topic", "type")} for message in fake.sent]
        self.assertIn({"op": "advertise", "topic": "/mavswarm2/robot_3/desired_state",
                       "type": "geometry_msgs/msg/Point"}, sent)
        self.assertIn({"op": "publish", "topic": "/mavswarm2/robot_3/desired_state", "type": None}, sent)

    def test_a_goal_is_refused_until_the_operator_supplies_the_envelope(self) -> None:
        client = self.serve()
        receipt = client.invoke(DESIRED, {"x": 2.0, "y": -1.5, "z": 2.0}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_resource_snapshot_observes_the_trajectory_trail(self) -> None:
        client = self.serve()
        state = client.read("main", **self.ids)["state"]
        self.assertIn("trail", state)
        self.assertGreaterEqual(len(state["trail"]), 1)
        self.assertEqual(set(state["trail"][0]), {"x", "y", "z"})
        self.assertEqual(set(state["last_goal"]), {"x", "y", "z"})

    def test_the_last_goal_resource_observes_a_publication(self) -> None:
        server = load(HERE, backend="fake", site_limits=HERE / "site-limits.example.json")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        ids = {"device_id": device_id, "session_id": session}
        before = client.read("main", **ids)["state"]["last_goal"]
        receipt = client.invoke(DESIRED, {"x": 2.0, "y": -1.5, "z": 2.0}, **ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        after = client.read("main", **ids)["state"]["last_goal"]
        self.assertNotEqual(before, after)
        self.assertEqual(after, {"x": 2.0, "y": -1.5, "z": 2.0})

    def test_a_silent_trajectory_is_reported_as_a_failure(self) -> None:
        driver, fake = self.direct()
        fake.silent_trajectory = True
        with self.assertRaises((DriverFailed, MHSError)) as caught:
            driver.call(TRAJECTORY, {})
        self.assertIn(getattr(caught.exception, "code", None),
                      {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY", "MHS.CAPABILITY.OUTPUT_INVALID"})

    def test_a_malformed_trajectory_is_reported_as_a_failure(self) -> None:
        driver, fake = self.direct()
        fake.malformed_trajectory = True
        with self.assertRaises((DriverFailed, MHSError)) as caught:
            driver.call(TRAJECTORY, {})
        self.assertIn(getattr(caught.exception, "code", None),
                      {"MHS.CAPABILITY.OUTPUT_INVALID", "MHS.ADAPTER.SHIM_FAILED",
                       "MHS.RESOURCE.STATE_INVALID", "MHS.DEVICE.NOT_READY"})

    def test_the_estop_is_not_confirmed_without_an_acknowledged_stop(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED)
        self.assertFalse(receipt["output"]["safe_state_achieved"])
        refused = client.invoke(TRAJECTORY, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()

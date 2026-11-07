"""Acceptance run of the GDR2 Gymnasium package: the gate plus cases specific to this fake.

Add cases, never remove the check_driver call.  These tests use the fake backend
only; no Docker, ROS 2, Gazebo or hardware is contacted.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class GDR2Cases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_a_step_advances_one_tick_and_reports_the_point_mass_observation(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"values": [0.5]}}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertFalse(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertEqual(len(output["observation"]["values"]), 2)
        self.assertAlmostEqual(output["reward"], -abs(output["observation"]["values"][0]), places=6)

    def test_an_action_outside_the_upstream_box_is_refused_before_the_fake(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"values": [1.5]}}, **self.ids)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE, receipt)
        self.assertIsNone(receipt.get("output"))

    def test_the_same_reset_seed_reproduces_the_fake_start_state(self) -> None:
        client = self.serve()

        def reset_with(seed):
            self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": seed}, **self.ids)["status"],
                             "completed")
            return client.invoke("cap.world.reset.v1", {}, **self.ids)["output"]["observation"]

        self.assertEqual(reset_with(11), reset_with(11))

    def test_the_fake_reproduces_the_dynamics_node_euler_update(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        fake = driver.native
        fake.reset(seed=0)
        # Test data, not a device fact: place the modelled state at the origin so
        # the one-step update is checked against dynamics_node.py:45-47.
        fake.position = 0.0
        fake.velocity = 0.0
        observation, reward, terminated, truncated, info = fake.step([1.0])
        self.assertAlmostEqual(observation[1], 0.05 * 0.99, places=9)
        self.assertAlmostEqual(observation[0], 0.05 * 0.99 * 0.05, places=9)
        self.assertAlmostEqual(reward, -abs(observation[0]), places=9)
        self.assertFalse(terminated)
        self.assertFalse(truncated)
        self.assertEqual(set(info), {"position", "velocity"})

    def test_the_episode_truncates_after_the_upstream_max_steps_and_needs_a_reset(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        output = driver.call("cap.world.step.v1", {"ticks": 1000, "action": {"values": [0.0]}})
        self.assertEqual(output["tick"], 1000)
        self.assertTrue(output["truncated"])
        with self.assertRaises(MHSError) as caught:
            driver.call("cap.world.step.v1", {"ticks": 1, "action": {"values": [0.0]}})
        self.assertEqual(caught.exception.code, PRECONDITION)


if __name__ == "__main__":
    unittest.main()

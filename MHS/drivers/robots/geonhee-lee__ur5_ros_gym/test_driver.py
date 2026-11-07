"""Acceptance run of the ur5_ros_gym package: the gate plus environment-specific cases.

The cases run on the fake backend (fake.py).  ROS 1, Gazebo, MoveIt and gym==0.10.5 are not installed
where the gate runs, so nothing here compares the fake with the upstream simulator.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
STATE_FIELDS = {"x", "y", "z", "force_z", "screw_joint_value"}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class UnscrewingCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def step(self, client, index, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"index": index}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    @staticmethod
    def value(receipt, field):
        return receipt["output"]["observation"][field]["value"]

    def test_reset_returns_the_legacy_state_and_records_the_seed(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=7)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["seed"], 7)
        observation = receipt["output"]["observation"]
        self.assertEqual(set(observation), STATE_FIELDS)
        # fake-only values: the fake's placeholder start pose; the upstream reset reads the live pose
        self.assertAlmostEqual(observation["x"]["value"], 0.5)
        self.assertAlmostEqual(observation["y"]["value"], 0.0)
        self.assertAlmostEqual(observation["z"]["value"], 0.03)
        self.assertEqual(observation["force_z"]["value"], 0.0)
        self.assertEqual(observation["screw_joint_value"]["value"], 0.0)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_step_moves_the_pose_and_advances_the_tick(self) -> None:
        client = self.serve()
        receipt = self.step(client, 0, ticks=2)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 2)
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertAlmostEqual(self.value(receipt, "x"), 0.5010)
        self.assertAlmostEqual(self.value(receipt, "y"), 0.0)
        self.assertAlmostEqual(self.value(receipt, "z"), 0.03)
        self.assertEqual(output["reward"], 0.0)
        self.assertTrue(output["state_hash"].startswith("sha256:"))
        self.assertEqual(self.state(client)["tick"], 2)

    def test_an_unscrewing_action_returns_reward_two_and_turns_the_tool(self) -> None:
        client = self.serve()
        receipt = self.step(client, 6)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["reward"], 2.0)
        self.assertFalse(output["terminated"])
        self.assertAlmostEqual(self.value(receipt, "force_z"), -0.5)
        self.assertAlmostEqual(self.value(receipt, "screw_joint_value"), -0.25)

    def test_the_fake_sets_the_screw_touch_state_below_the_height(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        native = driver.native
        self.assertEqual(native.step(5)[3], {})
        self.assertFalse(native.screw_touch_state)
        native.step(5)
        self.assertTrue(native.screw_touch_state)

    def test_the_episode_terminates_when_the_fake_force_crosses_the_threshold(self) -> None:
        client = self.serve()
        receipt = self.step(client, 6, ticks=21)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 21)
        self.assertTrue(output["terminated"])
        self.assertFalse(output["truncated"])
        ended = self.step(client, 6)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_episode_terminates_when_the_pose_leaves_the_boundaries(self) -> None:
        client = self.serve()
        receipt = self.step(client, 0, ticks=43)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 43)
        self.assertTrue(output["terminated"])
        self.assertEqual(output["reward"], -10.0)

    def test_an_out_of_envelope_action_is_refused_before_the_fake_moves(self) -> None:
        client = self.serve()
        refused = self.step(client, 7)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        state = self.state(client)
        self.assertEqual(state["tick"], 0)
        self.assertEqual(state["observation"], {})

    def test_the_seed_is_recorded_for_the_next_reset(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.world.seed.v1", {"seed": 11}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"seed": 11, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 11)
        # fake-only: the deterministic fake returns the same start state; the upstream reset has no seed
        # parameter and returns the live pose after a MoveIt motion and a Gazebo world reset
        self.assertEqual(first["observation"], self.reset(client, seed=11)["output"]["observation"])

    def test_the_fake_repeats_a_short_trajectory(self) -> None:
        def trajectory(actions):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=9)["status"], "completed")
            return [self.step(client, index)["output"]["state_hash"] for index in actions]

        first = trajectory((0, 6, 2, 5, 6, 1))
        self.assertEqual(trajectory((0, 6, 2, 5, 6, 1)), first)
        self.assertNotEqual(trajectory((6, 6, 6, 0, 0, 0)), first)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 0), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_fake_preserves_the_legacy_gym_surface(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        native = driver.native
        self.assertEqual(native.action_space.n, 7)
        observation = native.reset()
        self.assertEqual(set(observation), STATE_FIELDS)
        result = native.step(0)
        self.assertEqual(len(result), 4)
        state, reward, done, info = result
        self.assertEqual(set(state), STATE_FIELDS)
        self.assertEqual(reward, 0)
        self.assertIs(done, False)
        self.assertEqual(info, {})


if __name__ == "__main__":
    unittest.main()

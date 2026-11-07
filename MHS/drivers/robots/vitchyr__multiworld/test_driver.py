"""Acceptance run of the multiworld GoalGridworld package: the gate, plus cases for this driver.

The cases run on the fake backend (fake.py).  Nothing here imports multiworld, gym or numpy: the fake is a pure
Python re-implementation of ``GoalGridworld`` and was not compared with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ROWS, COLS = 10, 10


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class GoalGridworldCases(unittest.TestCase):
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

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 4)["status"], "completed")
        for index in (-1, 5):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)                    # the refused steps changed nothing

    def test_a_move_follows_the_action_table_and_the_reward(self) -> None:
        client = self.serve()
        reset = self.reset(client, seed=3)
        self.assertEqual(reset["status"], "completed")
        observation = reset["output"]["observation"]["observation"]["values"]
        goal = reset["output"]["observation"]["desired_goal"]["values"]
        self.assertEqual(len(observation), ROWS * COLS)
        cell = observation.index(1.0)
        row, col = divmod(cell, COLS)
        # goal_gridworld.py:13: action 0 is (-1, 0), 1 is (0, 1), 2 is (1, 0), 3 is (0, -1), 4 stays
        for action, (dr, dc) in enumerate(((-1, 0), (0, 1), (1, 0), (0, -1))):
            if 0 <= row + dr < ROWS and 0 <= col + dc < COLS:
                break
        else:
            self.fail("the reset put the agent in a cell with no legal move")
        receipt = self.step(client, action)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        moved = output["observation"]["observation"]["values"]
        expected = (row + dr) * COLS + (col + dc)
        self.assertEqual(moved.index(1.0), expected)
        expected_reward = -sum((a - b) ** 2 for a, b in
                               zip(output["observation"]["observation"]["values"],
                                   output["observation"]["desired_goal"]["values"]))
        self.assertAlmostEqual(output["reward"], expected_reward, places=9)
        self.assertEqual(output["tick"], 1)
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertNotEqual(goal, moved)

    def test_a_reset_draws_distinct_agent_and_goal_cells(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=5)["output"]["observation"]
        agent = observation["observation"]["values"].index(1.0)
        goal = observation["desired_goal"]["values"].index(1.0)
        self.assertNotEqual(agent, goal)                                   # goal_gridworld.py:71-76
        self.assertEqual(observation["achieved_goal"], observation["observation"])

    def test_the_episode_ends_after_41_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, 4, ticks=41)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # goal_gridworld.py:106-115: the count is incremented, then done is count > 40
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 41))
        ended = self.step(client, 4)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                     # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"] for action in (0, 1, 2, 3, 4)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        other = self.serve()
        self.assertEqual(self.reset(other, seed=21)["output"]["observation"], first["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("custom:multiworld:GoalGridworld-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 4)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 4), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                    # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

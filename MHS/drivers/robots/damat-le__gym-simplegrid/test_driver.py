"""Acceptance run of the gym-simplegrid package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): gym-simplegrid itself
is not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
FAULTED = "MHS.DEVICE.FAULTED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
# SimpleGrid-4x4-v0 cell indexes: 0 is (0, 0), 10 is (2, 2), 15 is (3, 3); 5 is (1, 1) and is an obstacle
# (gym_simplegrid/__init__.py:5).
START_0 = {"start_loc": 0}
GOAL_15 = {"goal_loc": 15}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SimpleGridCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, 1)["status"], "completed")
        for index in (-1, 4):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_the_first_step_matches_the_state_machine(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3, options={"start_loc": 0, "goal_loc": 15})["status"], "completed")
        receipt = self.step(client, 3)                                           # right: (0, 0) -> (0, 1)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # simple_grid.py:90-114: a free move pays the -0.1 step penalty and the observation is the flat index
        self.assertEqual(output["observation"]["index"], 1)
        self.assertAlmostEqual(output["reward"], -0.1)
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, False, 1))
        self.assertEqual(self.state(client)["info"]["agent_xy"], [0, 1])
        self.assertEqual(self.state(client)["info"]["step_count"], 1)

    def test_an_invalid_move_keeps_the_agent_and_pays_minus_one(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1, options={"start_loc": 0, "goal_loc": 15})["status"], "completed")
        receipt = self.step(client, 0)                                           # up from (0, 0): off the grid
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["observation"]["index"], 0)
        self.assertEqual(receipt["output"]["reward"], -1.0)                     # simple_grid.py:140-144
        self.assertEqual(receipt["output"]["tick"], 1)

    def test_the_reset_options_select_the_start_and_goal(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=2, options={"start_loc": 10, "goal_loc": 15})   # (2, 2) and (3, 3)
        self.assertEqual(receipt["output"]["observation"]["index"], 10)
        self.assertEqual(self.state(client)["info"]["agent_xy"], [2, 2])
        self.assertEqual(self.step(client, 1)["output"]["observation"]["index"], 14)      # down to (3, 2)
        goal = self.step(client, 3)                                                       # right to the goal
        self.assertEqual((goal["output"]["terminated"], goal["output"]["reward"]), (True, 1.0))
        self.assertEqual(goal["output"]["observation"]["index"], 15)

    def test_reaching_the_goal_terminates_the_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=4, options={"start_loc": 0, "goal_loc": 1})["status"], "completed")
        receipt = self.step(client, 3)                                           # right: (0, 0) -> (0, 1) is the goal
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual((receipt["output"]["terminated"], receipt["output"]["reward"]), (True, 1.0))
        ended = self.step(client, 0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=4, options={"start_loc": 0, "goal_loc": 1})["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_episode_truncates_at_the_registered_200_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5, options={"start_loc": 0, "goal_loc": 15})["status"], "completed")
        # up from (0, 0) is invalid every time, so the agent never reaches (3, 3) and the 200-step TimeLimit of
        # SimpleGrid-4x4-v0 (gym_simplegrid/__init__.py:31) truncates the episode.
        receipt = self.step(client, 0, ticks=200)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 200))
        self.assertAlmostEqual(output["reward"], -200.0)
        ended = self.step(client, 0)
        self.assertEqual(ended["error"]["mhs_code"], PRECONDITION)

    def test_a_seed_repeats_the_sampled_start(self) -> None:
        def start(seed):
            client = self.serve()                                  # a fresh world
            receipt = self.reset(client, seed=seed)
            return (receipt["output"]["seed"], receipt["output"]["observation"]["index"],
                    self.state(client)["info"]["agent_xy"])

        first = start(11)
        self.assertEqual(start(11), first)
        self.assertNotEqual(start(13), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_an_invalid_start_or_goal_is_refused(self) -> None:
        client = self.serve()
        for options in ({"start_loc": 5}, {"goal_loc": 5}):      # (1, 1) is an obstacle (__init__.py:5)
            refused = self.reset(client, options=options)
            self.assertEqual(refused["status"], "failed", options)
            self.assertEqual(refused["error"]["mhs_code"], FAULTED, options)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:SimpleGrid-4x4-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

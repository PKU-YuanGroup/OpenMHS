"""Acceptance run of the gym-maze package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the ``check_driver`` call.  The cases run on the fake backend (``fake.py``):
gym, pygame and numpy are not imported where the gate runs, so nothing here compares the fake with a
run of the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
# The shortest path found by breadth-first search over the wall bitmasks the fake embeds; the
# action indexes are 0 N, 1 S, 2 E, 3 W (maze_env.py:14).  Test data of this case, not a Fact.
PATH_TO_GOAL = [2, 2, 1, 1, 1, 1, 2, 0, 0, 0, 2, 1, 1, 1]
CELL_REWARD = -0.1 / (5 * 5)                                  # maze_env.py:83 for a 5x5 world


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MazeCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, 2)["status"], "completed")
        for index in (-1, 4):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    def test_a_blocked_move_keeps_the_cell(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["output"]["observation"], {"values": [0.0, 0.0]})
        receipt = self.step(client, 0)                           # north from (0, 0) is walled off
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["observation"]["values"], [0.0, 0.0])
        self.assertAlmostEqual(output["reward"], CELL_REWARD)
        self.assertEqual((output["terminated"], output["tick"]), (False, 1))

    def test_an_east_move_advances_one_cell(self) -> None:
        client = self.serve()
        self.reset(client)
        output = self.step(client, 2)["output"]                  # 2 is E (maze_env.py:14)
        self.assertEqual(output["observation"]["values"], [1.0, 0.0])
        self.assertAlmostEqual(output["reward"], CELL_REWARD)
        self.assertEqual(output["terminated"], False)

    def test_the_shortest_path_reaches_the_goal(self) -> None:
        client = self.serve()
        self.reset(client)
        for expected_tick, index in enumerate(PATH_TO_GOAL, start=1):
            receipt = self.step(client, index)
            self.assertEqual(receipt["status"], "completed", expected_tick)
            output = receipt["output"]
            self.assertEqual(output["tick"], expected_tick)
            if expected_tick < len(PATH_TO_GOAL):
                self.assertFalse(output["terminated"], expected_tick)
                self.assertAlmostEqual(output["reward"], CELL_REWARD)
        self.assertEqual(output["observation"]["values"], [4.0, 4.0])
        self.assertEqual((output["reward"], output["terminated"]), (1.0, True))
        ended = self.step(client, 0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_seed_is_echoed_but_does_not_change_the_maze(self) -> None:
        def trajectory(seed):
            client = self.serve()                                # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, index)["output"]["state_hash"] for index in (2, 2, 1)]

        first = trajectory(7)
        self.assertEqual(trajectory(7), first)
        self.assertEqual(trajectory(8), first)                   # the sample maze has no random draw

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        self.assertEqual(self.reset(client)["output"]["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], {"values": [0.0, 0.0]})

    def test_the_registered_time_limit_truncates_at_2000(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, 0, ticks=2000)               # north is blocked: the robot stays at (0, 0)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (2000, False, True))
        ended = self.step(client, 0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gym_maze:maze-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "exact")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 2)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 2), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

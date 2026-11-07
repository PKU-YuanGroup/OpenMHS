"""Acceptance run of the UR5 grasper package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py); the upstream environment
needs mujoco-py and MuJoCo, which are not installed where the gate runs, so nothing here compares the fake with it.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
STEP = "cap.world.step.v1"
RESET = "cap.world.reset.v1"
SEED = "cap.world.seed.v1"
# The fake's observation is an 8 x 8 stand-in (fake.py); the real camera is 200 x 200 (GraspingEnv.py:31-32).
STANDIN = 8
REAL = 200


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class GrasperCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, **fields):
        return client.invoke(RESET, fields, **self.ids)

    def step(self, client, pixel, rotation=0, ticks=1):
        return client.invoke(STEP, {"ticks": ticks, "action": {"values": [pixel, rotation]}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    @staticmethod
    def _pixel_for_cell(row, col):
        """A 200 x 200 pixel that the fake maps to the stand-in cell ``(row, col)``."""
        return (row * REAL // STANDIN) * REAL + (col * REAL // STANDIN)

    def _depth(self, observation):
        return observation["depth"]["values"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0)["status"], "completed")
        refused_cases = ((REAL * REAL, 0), (-1, 0), (0, 6), (0, -1))
        for pixel, rotation in refused_cases:
            refused = self.step(client, pixel, rotation)
            self.assertEqual(refused["status"], "rejected", (pixel, rotation))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (pixel, rotation))
        self.assertEqual(self.state(client)["tick"], 1)                  # the refused steps changed nothing

    def test_an_occupied_pixel_gives_the_binary_reward(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=5)["output"]["observation"]
        depth = self._depth(observation)
        occupied = next(((row, col) for row, line in enumerate(depth) for col, value in enumerate(line)
                         if value >= 0.8), None)
        empty = next(((row, col) for row, line in enumerate(depth) for col, value in enumerate(line)
                      if value < 0.8), None)
        self.assertIsNotNone(occupied)
        self.assertIsNotNone(empty)
        reward = self.step(client, self._pixel_for_cell(*occupied), rotation=2)
        self.assertEqual(reward["status"], "completed")
        self.assertEqual(reward["output"]["reward"], 1.0)
        self.assertEqual((reward["output"]["terminated"], reward["output"]["truncated"]), (False, False))
        self.assertEqual(reward["output"]["tick"], 1)
        miss = self.step(client, self._pixel_for_cell(*empty), rotation=2)
        self.assertEqual(miss["status"], "completed")
        self.assertEqual(miss["output"]["reward"], 0.0)

    def test_ticks_repeat_the_action_and_advance_the_tick(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=1)["output"]["observation"]
        depth = self._depth(observation)
        occupied = next((row, col) for row, line in enumerate(depth) for col, value in enumerate(line)
                        if value >= 0.8)
        output = self.step(client, self._pixel_for_cell(*occupied), rotation=0, ticks=3)["output"]
        self.assertEqual(output["reward"], 3.0)
        self.assertEqual(output["tick"], 3)
        self.assertEqual(self.state(client)["tick"], 3)

    def test_a_seed_repeats_the_observation(self) -> None:
        def observation(seed):
            client = self.serve()                       # a fresh world: the state hash counts episodes
            receipt = self.reset(client, seed=seed)
            self.assertEqual(receipt["status"], "completed")
            self.assertEqual(receipt["output"]["seed"], seed)
            return receipt["output"]["observation"]

        first = observation(11)
        self.assertEqual(observation(11), first)
        self.assertNotEqual(observation(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke(SEED, {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        second = self.reset(client, seed=21)["output"]
        self.assertEqual(second["observation"], first["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:Grasper-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (2.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 0), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

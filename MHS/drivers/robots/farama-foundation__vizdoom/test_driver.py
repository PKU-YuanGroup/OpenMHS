"""Acceptance run of the ViZDoom package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the ``check_driver`` call.  The cases run on the fake backend (fake.py): the upstream
ViZDoom extension and gymnasium are not installed where the gate runs, so nothing here compares the fake with the
real game.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class VizdoomBasicCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, 0)["status"], "completed")
        for index in (-1, 4):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_the_first_step_returns_the_scenario_reward_and_observation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, 0)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["reward"], output["tick"]), (-1.0, 1))          # basic.cfg:11 living_reward = -1
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        observation = output["observation"]
        self.assertEqual(sorted(observation), ["gamevariables", "screen"])
        self.assertEqual(len(observation["screen"]["values"]), 8)
        self.assertEqual(len(observation["screen"]["values"][0]), 8)
        self.assertEqual(len(observation["screen"]["values"][0][0]), 3)
        self.assertEqual(len(observation["gamevariables"]["values"]), 1)

    def test_attack_decrements_ammo_and_movement_changes_the_screen(self) -> None:
        client = self.serve()
        self.reset(client, seed=7)
        before = self.state(client)["observation"]
        receipt = self.step(client, 1)                                          # ATTACK
        after = receipt["output"]["observation"]
        self.assertEqual(after["gamevariables"]["values"][0],
                         before["gamevariables"]["values"][0] - 1.0)
        right = self.step(client, 2)["output"]["observation"]                   # MOVE_RIGHT
        left = self.step(client, 3)["output"]["observation"]                    # MOVE_LEFT
        self.assertNotEqual(right["screen"]["values"], left["screen"]["values"])

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"] for action in (0, 1, 2, 3, 0)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_episode_truncates_at_the_scenario_timeout(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        receipt = self.step(client, 0, ticks=300)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # basic.cfg:27 episode_timeout = 300; the fake has no death model, so only truncation ends the episode
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 300))
        self.assertEqual(output["reward"], -300.0)                              # one living reward per tic
        self.assertTrue(all(value == 0 for row in output["observation"]["screen"]["values"]
                            for pixel in row for value in pixel))               # base_gymnasium_env.py:316-324
        ended = self.step(client, 0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")       # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("vizdoom:VizdoomBasic-v1", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 35.0, places=6)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertTrue(any("240 x 320 x 3" in gap for gap in fidelity["gaps"]), fidelity["gaps"])

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 0), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

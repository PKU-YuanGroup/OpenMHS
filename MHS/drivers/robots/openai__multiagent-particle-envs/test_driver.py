"""Acceptance run of the particle-world package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call. The cases run on the fake backend (fake.py): gym and numpy are not
installed where the gate runs, so nothing here compares the fake with the upstream environment.
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


class ParticleSimpleCases(unittest.TestCase):
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
        for index in (-1, 5):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_the_first_step_follows_the_world_integration(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=3)["output"]["observation"]["values"]
        receipt = self.step(client, 2)                                          # action 2 is +x, sensitivity 5.0
        after = receipt["output"]["observation"]["values"]
        # by hand from core.py:158-169 with velocity 0 and force 5.0: vx = 5.0 * 0.1 = 0.5, then x += 0.5 * 0.1
        self.assertAlmostEqual(after[0], 0.5, places=9)
        self.assertAlmostEqual(after[1], 0.0, places=9)
        self.assertAlmostEqual(after[2], before[2] - 0.05, places=9)
        self.assertAlmostEqual(after[3], before[3], places=9)
        self.assertAlmostEqual(receipt["output"]["reward"], -(after[2] ** 2 + after[3] ** 2), places=9)

    def test_the_discrete_actions_map_to_the_two_axes(self) -> None:
        def velocity(index):
            client = self.serve()
            self.reset(client, seed=1)
            return self.step(client, index)["output"]["observation"]["values"][:2]

        self.assertEqual(velocity(0), [0.0, 0.0])
        self.assertEqual(velocity(1), [-0.5, 0.0])
        self.assertEqual(velocity(2), [0.5, 0.0])
        self.assertEqual(velocity(3), [0.0, -0.5])
        self.assertEqual(velocity(4), [0.0, 0.5])

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"] for action in (1, 2, 3, 4, 0)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_simple_episode_truncates_at_100_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        output = None
        for expected_tick in range(1, 101):
            receipt = self.step(client, 0)
            self.assertEqual(receipt["status"], "completed", expected_tick)
            output = receipt["output"]
            self.assertEqual(output["tick"], expected_tick)
        # the registration sets max_episode_steps=100 (multiagent/__init__.py:14); the simple scenario itself
        # supplies no done callback, so a step never terminates the episode (environment.py:132-135)
        self.assertEqual((output["terminated"], output["truncated"]), (False, True))
        ended = self.step(client, 0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")       # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertIn("MultiagentSimple-v0", fidelity["engine"])
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (100.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

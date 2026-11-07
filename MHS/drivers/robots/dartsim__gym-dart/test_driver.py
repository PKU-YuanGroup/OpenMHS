"""Acceptance run of the gym-dart package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): the clone is never imported or run, dartpy is not installed here, and
nothing compares the fake with the upstream environment.  The numbers in the cases are derived from the seeded fake
(the state it reports), not from a physical device.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
TIMESTEP_S = 0.01
THETA_REWARD_THRESHOLD = 0.1


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DartCartPoleCases(unittest.TestCase):
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

    def step(self, client, velocity, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": [velocity]}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1.0)["status"], "completed")
        for velocity in (-5.1, 5.1):
            refused = self.step(client, velocity)
            self.assertEqual(refused["status"], "rejected", velocity)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, velocity)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_a_seed_repeats_the_initial_state(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=17)["output"]
        second = self.reset(client, seed=17)["output"]
        self.assertEqual(first["observation"], second["observation"])
        self.assertEqual(first["seed"], 17)
        other = self.reset(client, seed=18)["output"]
        self.assertNotEqual(other["observation"], first["observation"])

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, velocity)["output"]["state_hash"] for velocity in (1.0, 0.0, -2.0, 3.0)]

        first = trajectory(17)
        self.assertEqual(trajectory(17), first)
        self.assertNotEqual(trajectory(18), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_action_moves_the_cart_and_the_episode_advances(self) -> None:
        client = self.serve()
        theta, theta_dot, x, x_dot = self.reset(client, seed=5)["output"]["observation"]["values"]
        receipt = self.step(client, 1.0)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        state = output["observation"]["values"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        # fake.py: the action is the cart velocity (dart_cartpole_env.py:163) and the cart integrates at 10 ms
        self.assertAlmostEqual(state[2], x + TIMESTEP_S * 1.0, places=12)
        self.assertEqual(state[3], 1.0)
        # the reward is computed on the state before the step (dart_cartpole_env.py:166 and :144-156)
        expected = (THETA_REWARD_THRESHOLD - abs(theta)) / THETA_REWARD_THRESHOLD + math.exp(-x)
        if abs(theta) >= THETA_REWARD_THRESHOLD:
            expected = 0.0
        self.assertAlmostEqual(output["reward"], expected, places=12)
        self.assertNotEqual(state, [theta, theta_dot, x, x_dot])

    def test_a_constant_push_ends_the_episode_at_the_cart_limit(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        output = None
        for _ in range(100):
            receipt = self.step(client, 5.0)
            self.assertEqual(receipt["status"], "completed")
            output = receipt["output"]
            if output["terminated"]:
                break
        self.assertIsNotNone(output)
        self.assertTrue(output["terminated"])
        self.assertGreater(abs(output["observation"]["values"][2]), 1.0)        # dart_cartpole_env.py:182
        ended = self.step(client, 5.0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")       # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_balanced_pole_is_truncated_at_200_steps(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        output = None
        for expected_tick in range(1, 201):
            receipt = self.step(client, 0.0)
            self.assertEqual(receipt["status"], "completed", expected_tick)
            output = receipt["output"]
            self.assertEqual(output["tick"], expected_tick)
        # gym_dart/__init__.py:12 registers max_episode_steps=200; the TimeLimit wrapper stops there
        self.assertEqual((output["terminated"], output["truncated"]), (False, True))
        self.assertEqual(self.step(client, 0.0)["error"]["mhs_code"], PRECONDITION)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gym_dart:DartCartPole-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (10.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0.0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 0.0), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

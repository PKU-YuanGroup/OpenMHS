"""Acceptance run of the ANYmal D blind-flat package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Isaac Sim and Isaac Lab
are not installed where the gate runs, so nothing here compares the fake with the registered environment.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ACTION_SIZE = 12                 # placeholder, the fake's dimension (not a device fact)
OBSERVATION_SIZE = 36            # placeholder, the fake's dimension (not a device fact)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AnymalDBlindFlatCases(unittest.TestCase):
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

    def step(self, client, values, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_envelope(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * ACTION_SIZE)["status"], "completed")
        refused = self.step(client, [1.5] + [0.0] * (ACTION_SIZE - 1))
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 1)               # the refused step changed nothing

    def test_the_first_step_is_the_kinematic_update(self) -> None:
        client = self.serve()
        reset = self.reset(client, seed=3)
        start = reset["output"]["observation"]["values"]
        self.assertEqual(len(start), OBSERVATION_SIZE)
        receipt = self.step(client, [0.0] * ACTION_SIZE)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        positions = start[:ACTION_SIZE]
        # fake.py: velocity = 0 - position, position += 0.25 * velocity, reward = -mean(velocity^2)
        self.assertAlmostEqual(output["reward"], -sum(value * value for value in positions) / ACTION_SIZE,
                               places=12)
        observation = output["observation"]["values"]
        for index, value in enumerate(positions):
            self.assertAlmostEqual(observation[index], 0.75 * value, places=12)
            self.assertAlmostEqual(observation[ACTION_SIZE + index], -value, places=12)
            self.assertEqual(observation[2 * ACTION_SIZE + index], 0.0)
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                   # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, values)["output"]["state_hash"]
                    for values in ([0.5] * ACTION_SIZE, [0.0] * ACTION_SIZE, [-0.5] * ACTION_SIZE)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_reset_returns_the_zero_tick(self) -> None:
        client = self.serve()
        self.step(client, [0.0] * ACTION_SIZE)
        receipt = self.reset(client)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(len(receipt["output"]["observation"]["values"]), OBSERVATION_SIZE)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("gymnasium:Isaac-Quadruped-AnymalD-Blind-Flat-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (5.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * ACTION_SIZE)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * ACTION_SIZE), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)               # readable, and not advanced

    def test_the_info_tick_is_a_placeholder(self) -> None:
        client = self.serve()
        output = self.step(client, [0.0] * ACTION_SIZE, ticks=2)["output"]
        self.assertEqual(output["tick"], 2)
        self.assertTrue(math.isfinite(output["reward"]))


if __name__ == "__main__":
    unittest.main()

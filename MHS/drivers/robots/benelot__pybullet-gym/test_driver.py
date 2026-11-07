"""Acceptance run of the pybullet-gym package: the gate, plus cases for the inverted pendulum driver.

The cases run on the package's fake backend.  They check the contract the bridge derives from the fake's spaces and
the behaviour the fake implements; nothing here compares the fake with Bullet or with the upstream environment.
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


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class InvertedPendulumCases(unittest.TestCase):
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

    def step(self, client, value, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": [value]}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1.0)["status"], "completed")
        for value in (-1.5, 1.5):
            refused = self.step(client, value)
            self.assertEqual(refused["status"], "rejected", value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["tick"], 1)                  # the refused steps changed nothing

    def test_the_observation_has_the_upstream_layout(self) -> None:
        client = self.serve()
        output = self.reset(client, seed=5)["output"]
        values = output["observation"]["values"]
        self.assertEqual(len(values), 5)                                 # interted_pendulum.py:9
        self.assertAlmostEqual(values[2] ** 2 + values[3] ** 2, 1.0, places=12)
        self.assertGreaterEqual(values[2], math.cos(0.1))                # the reset draws |theta| <= 0.1
        receipt = self.step(client, 1.0)["output"]
        self.assertEqual(receipt["reward"], 1.0)                         # inverted_pendulum_env.py:35
        self.assertEqual(len(receipt["observation"]["values"]), 5)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, value)["output"]["state_hash"] for value in (1.0, -1.0, 0.5, -0.5)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]
        self.assertEqual(accepted, {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_constant_push_ends_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        output = self.step(client, 1.0, ticks=50)["output"]
        # the fake integrates the same angle threshold as inverted_pendulum_env.py:36
        self.assertTrue(output["terminated"])
        self.assertLess(output["tick"], 50)
        self.assertEqual(output["reward"], float(output["tick"]))        # 1.0 for every step
        ended = self.step(client, 1.0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_registered_limit_truncates_at_1000_steps(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=3)["output"]["observation"]["values"]
        output = None
        for expected_tick in range(1, 1001):
            theta = math.atan2(observation[3], observation[2])
            # a proportional controller on the fake's simplified dynamics; the fake is deterministic
            value = 1.0 if theta + 0.2 * observation[4] > 0 else -1.0
            receipt = self.step(client, value)
            self.assertEqual(receipt["status"], "completed", expected_tick)
            output = receipt["output"]
            self.assertEqual(output["tick"], expected_tick)
            observation = output["observation"]["values"]
        self.assertFalse(output["terminated"])
        self.assertTrue(output["truncated"])                             # pybulletgym/envs/__init__.py:8
        self.assertEqual(self.step(client, 1.0)["error"]["mhs_code"], PRECONDITION)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["safety"]["risk_class"], "R0")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("pybullet-gym:InvertedPendulumPyBulletEnv-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (16.5, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1.0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1.0), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

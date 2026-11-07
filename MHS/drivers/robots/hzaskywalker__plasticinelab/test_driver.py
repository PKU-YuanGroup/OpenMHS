"""Acceptance run of the PlasticineLab package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py); the upstream environment is not importable where the gate runs (it needs
Taichi, the legacy gym package, numpy and a GPU), so nothing here compares the fake with a real run of the solver.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ACTION_DIM = 6
OBSERVATION_DIM = 2 * 200 * 3 + 2 * 7


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PlasticineLabCases(unittest.TestCase):
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

    def step(self, client, values=None, ticks=1):
        action = {"values": list(values) if values is not None else [0.0] * ACTION_DIM}
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_a_step_advances_the_world(self) -> None:
        client = self.serve()
        before = self.state(client)
        receipt = self.step(client, [1.0] * ACTION_DIM)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["tick"], output["reward"]), (1, 0.0))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        observation = output["observation"]["values"]
        self.assertEqual(len(observation), OBSERVATION_DIM)       # 200 observed particles x 6 + 2 primitives x 7
        self.assertIsInstance(output["state_hash"], str)
        self.assertEqual((before["tick"], self.state(client)["tick"]), (0, 1))
        # the fake moves both primitive positions by action * 0.01 (plb/envs/move.yml:18, :26)
        self.assertAlmostEqual(observation[-14], 0.5757143040494873 + 0.01, places=12)
        self.assertAlmostEqual(observation[-7], 0.7757143040494873 + 0.01, places=12)
        # the rotation quaternions stay (1, 0, 0, 0) and are present in the observation
        self.assertEqual(observation[-11:-7], [1.0, 0.0, 0.0, 0.0])

    def test_the_action_space_is_the_bound(self) -> None:
        client = self.serve()
        high = [1.0] * ACTION_DIM
        high[0] = 1.000001
        low = [-1.0] * ACTION_DIM
        low[-1] = -1.000001
        for values in (high, low):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 0)            # the refused steps changed nothing

    def test_reset_restores_the_fixed_start_state(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=5)
        self.assertEqual(first["status"], "completed", first)
        self.assertEqual(first["output"]["seed"], 5)
        self.assertEqual(self.step(client, [1.0] * ACTION_DIM)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 1)
        again = self.reset(client)
        self.assertEqual(again["status"], "completed", again)
        self.assertEqual(again["output"]["observation"], first["output"]["observation"])
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_seed_labels_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 23}, **self.ids)
        self.assertEqual(accepted["status"], "completed", accepted)
        self.assertEqual(accepted["output"], {"seed": 23, "accepted": True})
        first = self.reset(client)
        self.assertEqual(first["output"]["seed"], 23)
        second = self.reset(client, seed=7)                         # an explicit seed overrides the pending one
        self.assertEqual(second["output"]["seed"], 7)
        # reset() takes no seed upstream (plb/envs/env.py:28), so the seed labels the episode, not the state
        self.assertEqual(second["output"]["observation"], first["output"]["observation"])

    def test_the_registered_episode_limit_truncates_at_50_steps(self) -> None:
        client = self.serve()
        receipt = self.step(client, [0.0] * ACTION_DIM, ticks=50)  # max_episode_steps 50 (plb/envs/__init__.py:12)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (50, False, True))
        ended = self.step(client, [0.0] * ACTION_DIM)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("taichi-mpm:PlasticineLab-Move-v1", "F1"))
        self.assertEqual((fidelity["determinism"]["kind"], fidelity["determinism"]["seed_control"]),
                         ("seeded", "none"))
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (2.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 8)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)            # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

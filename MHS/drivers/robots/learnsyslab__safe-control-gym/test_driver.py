"""Acceptance run of the safe-control-gym CartPole package: the gate, plus cases for this driver.

The cases run on the fake backend (``fake.py``): the upstream package is not installed where the gate runs, so nothing
here compares the fake with the PyBullet environment.  Keep ``check_driver``; add cases, never remove it.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CartPoleCases(unittest.TestCase):
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

    def step(self, client, force, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": [force]}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_enforced_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0.5)["status"], "completed")
        for force in (10.5, -10.5):
            refused = self.step(client, force)
            self.assertEqual(refused["status"], "rejected", force)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, force)
        self.assertEqual(self.state(client)["tick"], 1)  # the refused steps changed nothing

    def test_reset_seed_repeats_the_initial_state(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]
        self.assertEqual(first["seed"], 7)
        self.assertEqual(len(first["observation"]["values"]), 4)
        second = self.reset(client, seed=7)["output"]
        self.assertEqual(second["observation"], first["observation"])

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["status"], "completed")
        self.assertTrue(accepted["output"]["accepted"])
        without_seed = self.reset(client)["output"]
        self.assertEqual(without_seed["seed"], 21)
        with_seed = self.reset(client, seed=21)["output"]
        self.assertEqual(with_seed["observation"], without_seed["observation"])

    def test_a_step_changes_the_world_state(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")
        receipt = self.step(client, 0.0)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertEqual(len(output["observation"]["values"]), 4)
        self.assertGreaterEqual(output["reward"], 0.0)
        self.assertLessEqual(output["reward"], 1.0)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("safe-control-gym:cartpole", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0.0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 0.0), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the BiGym 2.0 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py); the upstream package is
not installed where the gate runs and package code never imports the clone, so nothing here compares the fake with
the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ACTION_DIM = 24          # placeholder: the fake's action length; the real one is computed from the G1 layout
STATE_DIM = 12           # placeholder: the fake's state length; the real one is summed over the state keys


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class BiGym2Cases(unittest.TestCase):
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
        values = [0.5] * ACTION_DIM if values is None else values
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_a_step_advances_the_world_and_changes_the_state(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        before = self.state(client)
        self.assertEqual(before["tick"], 0)
        receipt = self.step(client, values=[0.5] * ACTION_DIM, ticks=2)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 2)
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        values = output["observation"]["state"]["values"]
        self.assertEqual(len(values), STATE_DIM)
        self.assertNotEqual(values, before["observation"]["state"]["values"])
        self.assertEqual(output["observation"]["rgb"]["values"][0], 2)     # the fake marks the tick in pixel 0
        self.assertEqual(self.state(client)["tick"], 2)

    def test_the_action_space_bounds_are_enforced(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        tick = self.state(client)["tick"]
        for outside in (1.5, -1.5):
            values = [0.0] * ACTION_DIM
            values[0] = outside
            refused = self.step(client, values=values)
            self.assertEqual(refused["status"], "rejected", outside)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, outside)
        self.assertEqual(self.state(client)["tick"], tick)                 # no refused step advanced the world

    def test_a_reset_seed_repeats_the_initial_state(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]
        second = self.reset(client, seed=7)["output"]
        self.assertEqual(first["seed"], 7)
        self.assertEqual(first["observation"], second["observation"])
        other = self.reset(client, seed=8)["output"]
        self.assertEqual(other["seed"], 8)
        self.assertNotEqual(first["observation"], other["observation"])

    def test_the_seed_action_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual((accepted["status"], accepted["output"]["seed"], accepted["output"]["accepted"]),
                         ("completed", 21, True))
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        direct = self.reset(client, seed=21)["output"]
        self.assertEqual(first["observation"], direct["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["safety"]["risk_class"], "R0")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertIn("bigym2", fidelity["engine"])
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=2)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                    # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

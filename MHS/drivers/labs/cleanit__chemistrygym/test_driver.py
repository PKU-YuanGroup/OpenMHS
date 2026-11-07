"""Acceptance run of the ChemistryLab package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py); the upstream environment is not importable where the gate runs, so
nothing here compares the fake with a real run of the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"


def step_payload(selector, multiplier=0, ticks=1):
    return {"ticks": ticks, "action": {"values": [selector, multiplier]}}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ExtractWorldCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def step(self, client, payload):
        return client.invoke("cap.world.step.v1", payload, **self.ids)

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_a_step_advances_the_world(self) -> None:
        client = self.serve()
        before = self.state(client)
        receipt = self.step(client, step_payload(1))                 # Mix ExV: no amount changes
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["tick"], output["reward"]), (1, -1.0))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertIn("values", output["observation"])
        after = self.state(client)
        self.assertEqual((before["tick"], after["tick"]), (0, 1))
        self.assertIsInstance(output["state_hash"], str)

    def test_the_action_space_is_the_bound(self) -> None:
        client = self.serve()
        for values in ([9, 0], [0, 5]):                              # MultiDiscrete([9, 5]) at water_oil_v1.py:56
            refused = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"values": values}}, **self.ids)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_transfer_reaches_the_second_beaker_and_done_pays_it(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, step_payload(6, 4))["output"]["reward"], -1.0)  # ExV -> B2, full speed
        receipt = self.step(client, step_payload(8))                 # Done (water_oil_v1.py:189-192)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        # the fake moves 25 percent of the 10 fake Na units, so done_reward is 25.0 (water_oil_v1.py:195-205)
        self.assertEqual((output["reward"], output["terminated"], output["tick"]), (25.0, True, 2))
        ended = self.step(client, step_payload(1))
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))

    def test_done_without_target_material_pays_minus_100(self) -> None:
        client = self.serve()
        receipt = self.step(client, step_payload(8))
        self.assertEqual(receipt["output"]["reward"], -100.0)
        self.assertTrue(receipt["output"]["terminated"])

    def test_the_episode_ends_after_100_steps(self) -> None:
        client = self.serve()
        first = self.step(client, step_payload(1, ticks=99))         # n_steps=100 (extractworld_v1_engine.py:17)
        self.assertEqual((first["output"]["tick"], first["output"]["terminated"]), (99, False))
        receipt = self.step(client, step_payload(1))
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (100, True, False))
        self.assertEqual(output["reward"], -100.0)                   # done_reward without beaker 2 target material
        refused = self.step(client, step_payload(1))
        self.assertEqual(refused["error"]["mhs_code"], PRECONDITION)

    def test_reset_starts_a_new_episode_and_echoes_the_seed(self) -> None:
        client = self.serve()
        self.step(client, step_payload(1))
        receipt = self.reset(client, seed=7)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["seed"], 7)
        self.assertIn("values", receipt["output"]["observation"])
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 23}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 23, "accepted": True})
        self.assertEqual(self.reset(client)["output"]["seed"], 23)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("chemistrylab:ExtractWorld_0-v1", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (10.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, step_payload(1))["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, step_payload(1)), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)              # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

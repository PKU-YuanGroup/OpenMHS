"""Acceptance run of the RLRoverLab package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): Isaac Sim and Isaac Lab are not installed where the gate runs, so
nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RLRoverLabCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, seed=None):
        fields = {} if seed is None else {"seed": seed}
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def step(self, client, linear=0.0, angular=0.0, ticks=1):
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": {"values": [linear, angular]}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_reset_reports_the_five_scalar_observation_terms(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=2)
        self.assertEqual(receipt["status"], "completed")
        observations = receipt["output"]["observation"]["values"]
        self.assertEqual(len(observations), 5)
        # the target sits on the 9 m circle (terrain_importer.py:167) and the distance term is scaled by 0.11
        self.assertAlmostEqual(observations[2], 0.11 * 9.0, places=7)
        self.assertLessEqual(abs(observations[3]), 1.0)          # heading is atan2(dy, dx) / pi
        self.assertLessEqual(abs(observations[4]), 1.0)          # angle difference is wrapped and / pi
        self.assertEqual((observations[0], observations[1]), (0.0, 0.0))

    def test_a_step_applies_the_two_action_values(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=0)["status"], "completed")
        receipt = self.step(client, linear=1.0, angular=0.0)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertEqual(output["reward"], 0.0)                  # gap: the reward terms are not modelled
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertEqual(output["observation"]["values"][:2], [1.0, 0.0])
        self.assertEqual(self.state(client)["tick"], 1)

    def test_a_seed_repeats_the_target(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]["observation"]["values"]
        self.step(client, linear=0.5)
        again = self.reset(client, seed=7)["output"]["observation"]["values"]
        self.assertEqual(first, again)
        other = self.reset(client, seed=8)["output"]["observation"]["values"]
        self.assertNotEqual(first, other)

    def test_an_action_with_the_wrong_length_is_refused(self) -> None:
        client = self.serve()
        refused = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"values": [1.0]}}, **self.ids)
        self.assertIn(refused["status"], ("rejected", "failed"))
        self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["engine"], "gymnasium:AAURoverEnv-v0 (analytic fake)")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (200.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, linear=0.5)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, linear=0.5), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

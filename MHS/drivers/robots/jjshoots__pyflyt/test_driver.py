"""Acceptance run of the PyFlyt QuadX Hover package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The cases run on the package fake (fake.py); PyFlyt, pybullet,
numpy and gymnasium are not installed where the gate runs, so nothing here compares the fake with the upstream
PyBullet simulation.
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
HOVER = [0.0, 0.0, 0.0, 0.4]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class QuadXHoverCases(unittest.TestCase):
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

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, HOVER)["status"], "completed")
        refused = self.step(client, [-math.pi - 0.1, 0.0, 0.0, 0.4])
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        refused = self.step(client, [0.0, 0.0, 0.0, 0.81])
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 1)             # the refused steps changed nothing

    def test_a_step_returns_the_21_element_observation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        receipt = self.step(client, [0.1, -0.1, 0.0, 0.4])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertEqual(len(output["observation"]["values"]), 21)
        self.assertTrue(math.isfinite(output["reward"]))
        self.assertFalse(output["terminated"] or output["truncated"])

    def test_a_seed_repeats_the_start_state(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]
        second = self.reset(client, seed=7)["output"]
        self.assertEqual(first["seed"], 7)
        self.assertEqual(first["observation"], second["observation"])

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        self.assertEqual(self.reset(client)["output"]["seed"], 21)

    def test_the_episode_truncates_at_the_step_limit(self) -> None:
        client = self.serve()
        receipt = self.step(client, HOVER, ticks=401)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual((receipt["output"]["tick"], receipt["output"]["truncated"]), (401, True))
        ended = self.step(client, HOVER)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("PyFlyt:PyFlyt/QuadX-Hover-v4", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (25.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, HOVER)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, HOVER), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)             # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

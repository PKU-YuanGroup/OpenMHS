"""Acceptance run of the Slimebot Volleyball package: the gate, plus cases for this driver.

The cases run on the package fake backend (fake.py).  gym, numpy, opencv and Webots are not installed where the gate
runs, so nothing here compares the fake with the upstream environment.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ZERO_ACTION = [0, 0, 0, 0, 0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class VolleyBotCases(unittest.TestCase):
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

    def step(self, client, action=None, ticks=1):
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": {"values": list(action or ZERO_ACTION)}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        self.assertEqual(self.step(client)["status"], "completed")
        for action in ([2, 0, 0, 0, 0], [-1, 0, 0, 0, 0], [1, 1, 1, 1, 2]):
            refused = self.step(client, action)
            self.assertEqual(refused["status"], "rejected", action)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, action)
        self.assertEqual(self.state(client)["tick"], 1)  # the refused steps changed nothing

    def test_the_observation_is_the_eighteen_value_state(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=4)["output"]["observation"]
        values = observation["values"]
        self.assertEqual(len(values), 18)
        self.assertTrue(all(math.isfinite(value) for value in values), values)
        stepped = self.step(client, [1, 0, 1, 0, 0])
        self.assertEqual(stepped["status"], "completed")
        self.assertEqual(len(stepped["output"]["observation"]["values"]), 18)
        self.assertEqual(stepped["output"]["tick"], 1)

    def test_a_seed_repeats_the_initial_observation(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]["observation"]
        second = self.reset(client, seed=11)["output"]["observation"]
        self.assertEqual(first, second)
        other = self.reset(client, seed=12)["output"]["observation"]
        self.assertNotEqual(first, other)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        explicit = self.reset(client, seed=21)["output"]
        self.assertEqual(first["observation"], explicit["observation"])

    def test_ticks_advance_the_environment(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        receipt = self.step(client, ticks=4)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 4)
        self.assertEqual(self.state(client)["tick"], 4)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "slimebot-volleyball:VolleyBotEnv (1_vs_1)")
        self.assertEqual(fidelity["fidelity_level"], "F1")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 30.0)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=6)["status"], "completed")
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=6)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

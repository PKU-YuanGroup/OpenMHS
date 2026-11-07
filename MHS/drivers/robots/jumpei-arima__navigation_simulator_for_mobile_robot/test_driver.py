"""Acceptance run of this driver package: the gate, plus cases for what is specific to the NSMR simulator.

Add cases, never remove the check_driver call.  Everything runs on the fake backend (fake.py): the upstream environment
needs legacy gym, numpy and the Cython raycasting extension and was never installed or run where the gate runs, so
nothing here compares the fake with it.
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


class NsmrCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, [0.5, 0.0])["status"], "completed")
        tick = self.state(client)["tick"]
        for values in ([-0.1, 0.0], [1.1, 0.0], [0.5, -1.1], [0.5, 1.1]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], tick)          # the refused steps changed nothing

    def test_a_step_returns_the_legacy_observation_shape(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=5)["output"]["observation"]
        self.assertEqual(len(observation["lidar"]["values"]), 720)   # robot.json:18
        self.assertEqual(len(observation["target"]["values"]), 3)    # [distance, sin, cos]
        receipt = self.step(client, [0.5, 0.0])
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertIn("observation", output)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_ticks_advance_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=6)["status"], "completed")
        receipt = self.step(client, [0.5, 0.0], ticks=3)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["tick"], 3)
        self.assertEqual(self.state(client)["tick"], 3)

    def test_a_seed_repeats_the_reset(self) -> None:
        def observation(seed):
            client = self.serve()
            receipt = self.reset(client, seed=seed)
            self.assertEqual(receipt["output"]["seed"], seed)
            return receipt["output"]["observation"]

        first = observation(11)
        self.assertEqual(observation(11), first)
        self.assertNotEqual(observation(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("nsmr:2d-raycasting", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (100.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.5, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.5, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)              # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

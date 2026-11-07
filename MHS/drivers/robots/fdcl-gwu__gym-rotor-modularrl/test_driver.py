"""Acceptance run of the gym-rotor-modularrl package: the gate, plus cases specific to the Quad-v0 driver.

Add cases, never remove the check_driver call.  Everything runs on the fake backend (fake.py): the upstream package
needs gymnasium, numpy and scipy, and is never imported here.
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


class QuadRotorCases(unittest.TestCase):
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
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0, 0.0])["status"], "completed")
        tick = self.state(client)["tick"]
        for values in ([1.5, 0.0, 0.0, 0.0], [0.0, -1.0001, 0.0, 0.0], [0.0, 0.0, 2.0, 0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], tick)                       # the refused steps changed nothing

    def test_a_step_returns_the_eighteen_element_state(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=7)["status"], "completed")
        receipt = self.step(client, [0.0, 0.0, 0.0, 0.0], ticks=2)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(len(output["observation"]["values"]), 18)              # quad.py:146
        self.assertGreaterEqual(output["tick"], 1)
        self.assertLessEqual(output["tick"], 2)
        self.assertTrue(output["state_hash"].startswith("sha256:"))

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                              # a fresh world
            reset = self.reset(client, seed=seed)
            self.assertEqual(reset["output"]["seed"], seed)
            observations = [reset["output"]["observation"]["values"]]
            for _ in range(4):
                observations.append(self.step(client, [0.0, 0.0, 0.0, 0.0])["output"]
                                    ["observation"]["values"])
            return observations

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        pending = self.reset(client)["output"]
        self.assertEqual(pending["seed"], 21)
        direct = self.reset(client, seed=21)["output"]
        self.assertEqual(pending["observation"], direct["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["reference"]["device"]["kind"], "world.sim")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gym_rotor:Quad-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["timestep_ms"], 5.0)                          # 200 Hz, quad.py:60-61
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0, 0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the WorldComposer Tableware package: the gate, plus cases for this driver.

The cases run on the fake backend (fake.py).  Isaac Sim, Isaac Lab and the external Assets dataset are not installed
where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class TablewareCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": list(values)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_first_step_returns_the_interface_observation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        values = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
        receipt = self.step(client, values)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        observation = output["observation"]
        self.assertEqual(observation["action"]["values"], values)
        self.assertEqual(observation["observation.state"]["values"], values)
        self.assertEqual((output["reward"], output["tick"]), (0.0, 1))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_action_must_have_six_values(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        for values in ([0.0] * 5, [0.0] * 7):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, values)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_same_actions_repeat(self) -> None:
        def trajectory():
            client = self.serve()
            self.assertEqual(self.reset(client, seed=5)["output"]["seed"], 5)
            return [self.step(client, [0.1, -0.2, 0.3, -0.4, 0.5, -0.6])["output"]["state_hash"]
                    for _ in range(3)]

        self.assertEqual(trajectory(), trajectory())

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_time_limit_marks_both_flags(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        receipt = self.step(client, [0.0] * 6, ticks=7200)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (7200, True, True))
        ended = self.step(client, [0.0] * 6)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("mhs-fake:WorldComposer-Tableware-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 120.0, places=9)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 6)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * 6), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)


if __name__ == "__main__":
    unittest.main()

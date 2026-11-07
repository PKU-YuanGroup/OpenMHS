"""Acceptance run of the DoorGym package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): gym 0.14, mujoco-py,
mjremote and torch are not installed where the gate runs, so nothing here compares the fake with the upstream
environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ACTION = [0.1] * 7 + [0.5]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DoorGymCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def step(self, client, values=None, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values or ACTION}},
                             **self.ids)

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        for values in ([2.0] + ACTION[1:], ACTION[:-1] + [-0.01], ACTION[:-1] + [1.06]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 0)                   # the refused steps changed nothing
        self.assertEqual(self.step(client)["status"], "completed")

    def test_the_action_has_eight_values(self) -> None:
        client = self.serve()
        for values in (ACTION[:-1], ACTION + [0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, values)

    def test_the_step_advances_the_world(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        before = self.state(client)
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed")
        after = self.state(client)
        self.assertEqual(before["tick"], 0)
        self.assertEqual(after["tick"], 1)
        self.assertEqual(len(after["observation"]["values"]), 19)         # 2 * nn + 3 with nn = 8
        self.assertNotEqual(after["observation"], before["observation"])
        self.assertEqual(receipt["output"]["tick"], 1)

    def test_a_seed_repeats_the_reset(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]
        self.assertEqual(first["seed"], 11)
        second = self.reset(client, seed=11)["output"]
        self.assertEqual(second["observation"], first["observation"])
        other = self.reset(client, seed=12)["output"]
        self.assertNotEqual(other["observation"], first["observation"])

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_time_limit_ends_the_episode(self) -> None:
        client = self.serve()
        receipt = self.step(client, ticks=512)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 512)
        self.assertEqual(receipt["output"]["terminated"], True)
        self.assertEqual(receipt["output"]["truncated"], False)
        ended = self.step(client)
        self.assertEqual(ended["status"], "failed")
        self.assertEqual(ended["error"]["mhs_code"], PRECONDITION)
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("mujoco:blue-doorenv-v1", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)


if __name__ == "__main__":
    unittest.main()

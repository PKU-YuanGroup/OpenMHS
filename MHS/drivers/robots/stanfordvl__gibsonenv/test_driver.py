"""Acceptance run of the Gibson package: the gate, plus cases for this driver.

The cases run on the fake backend (fake.py); the upstream environment is not imported and was not
run (it needs the pinned gym 0.9.4 / pybullet 1.9.4 stack, downloaded scenes and a GPU).
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


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AntNavigateCases(unittest.TestCase):
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

    def step(self, client, index, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"index": index}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def sensor(self, receipt):
        return receipt["output"]["observation"]["nonviz_sensor"]["values"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0)["status"], "completed")
        for index in (-1, 17):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)                # the refused steps changed nothing

    def test_one_step_returns_the_nonviz_sensor(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]["observation"]["nonviz_sensor"]["values"]
        receipt = self.step(client, 1)
        self.assertEqual(receipt["status"], "completed")
        values = self.sensor(receipt)
        self.assertEqual(len(values), 28)                              # robot_locomotors.py:259-260
        self.assertTrue(all(-5.0 <= value <= 5.0 for value in values), values)   # :204
        self.assertNotEqual(values, first)                             # the action moved the toy body
        self.assertEqual(receipt["output"]["tick"], 1)
        self.assertTrue(math.isfinite(receipt["output"]["reward"]))

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                      # a fresh world: the hash covers the episode
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"] for action in (1, 9, 0, 5, 16)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)                      # the reset joint draw uses the seed

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_an_episode_ends_after_300_frames(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, 0, ticks=301)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # ant_env.py:89: done is nframe > 300, and nframe is incremented before the check
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 301))
        ended = self.step(client, 0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("pybullet", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (10.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 0), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

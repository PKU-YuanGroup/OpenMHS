"""Acceptance run of the GenesisLab package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py).  The upstream environment needs torch, the Genesis engine and the robot
assets, so nothing here compares the fake with a real rollout.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
#: Placeholder test data: the fake's unbounded action vector (see fake.py).
ACTION = {"values": [0.0] * 29}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class GenesisLabCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": dict(action or ACTION)}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("genesis", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_reset_step_and_seed(self) -> None:
        client = self.serve()
        reset = self.reset(client, seed=7)
        self.assertEqual((reset["status"], reset["output"]["seed"]), ("completed", 7))
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        # placeholder observation: 3 + 3 + 3 + 3 + 29 + 29 + 29 values
        self.assertEqual(len(output["observation"]["policy"]["values"]), 99)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_action_shape_is_checked_by_the_bridge(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        refused = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"values": [0.0] * 28}}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 1)                         # refused before the native step

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_seed_repeats_a_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.reset(client, seed=seed)
            return [self.step(client)["output"]["state_hash"] for _ in range(3)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_episode_truncates_at_the_configured_length(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        output = self.step(client, ticks=1000)["output"]           # placeholder 20 s / 20 ms
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 1000))
        ended = self.step(client)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", "MHS.DEVICE.PRECONDITION_UNMET"))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

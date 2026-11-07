"""Acceptance run of the OCBbench package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo, dm_control,
Gymnasium and ocbench are not installed where the gate runs, so nothing here compares the fake with the upstream
environment.  The 7 action values and 28 observation values are the fake's test data; the sourced shapes are in
facts.md.
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
ACTION_VALUES = 7
OBSERVATION_VALUES = 28
MAX_EPISODE_STEPS = 1250


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class BlockSingleTask1Cases(unittest.TestCase):
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
        self.assertEqual(self.step(client, [0.0] * ACTION_VALUES)["status"], "completed")
        refused = self.step(client, [2.0] * ACTION_VALUES)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 1)                 # the refused step changed nothing

    def test_reset_is_seeded_and_returns_the_observation(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]
        self.assertEqual(first["seed"], 7)
        self.assertEqual(len(first["observation"]["values"]), OBSERVATION_VALUES)
        second = self.reset(client, seed=7)["output"]
        self.assertEqual(second["observation"], first["observation"])
        other = self.reset(client, seed=8)["output"]
        self.assertNotEqual(other["observation"], first["observation"])

    def test_a_step_advances_the_world_and_changes_the_observation(self) -> None:
        client = self.serve()
        start = self.reset(client, seed=3)["output"]["observation"]
        receipt = self.step(client, [0.1] * ACTION_VALUES, ticks=2)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 2)
        self.assertNotEqual(output["observation"], start)
        self.assertTrue(math.isfinite(output["reward"]))
        self.assertFalse(output["terminated"] or output["truncated"])
        self.assertEqual(self.state(client)["tick"], 2)

    def test_the_registered_time_limit_truncates_the_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        receipt = self.step(client, [0.0] * ACTION_VALUES, ticks=MAX_EPISODE_STEPS)
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(receipt["output"]["truncated"])
        self.assertFalse(receipt["output"]["terminated"])
        self.assertEqual(receipt["output"]["tick"], MAX_EPISODE_STEPS)
        ended = self.step(client, [0.0] * ACTION_VALUES)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")   # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("mujoco:block-cpu-single-task1-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * ACTION_VALUES)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * ACTION_VALUES), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                 # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

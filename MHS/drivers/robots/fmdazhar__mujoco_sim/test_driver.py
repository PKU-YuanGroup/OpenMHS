"""Acceptance run of the mujoco_sim package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo,
gymnasium, glfw and PyOpenGL are not installed where the gate runs, so nothing here compares the fake with
the upstream environment.  The three action values and 27 observation values are the fake's contract and
test data; the sourced action and observation spaces are in facts.md.
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
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ACTION_VALUES = 3
OBSERVATION_VALUES = 27


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class UR5ePegInHoleCases(unittest.TestCase):
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
        for values in ([1.5, 0.0, 0.0], [0.0, -1.5, 0.0], [0.0, 0.0, 2.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                 # the refused steps changed nothing

    def test_an_action_of_the_wrong_length_is_refused(self) -> None:
        client = self.serve()
        refused = self.step(client, [0.0, 0.0])
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", INPUT_INVALID))
        self.assertEqual(self.state(client)["tick"], 0)

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
        receipt = self.step(client, [0.1, -0.2, 0.3], ticks=2)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 2)
        self.assertNotEqual(output["observation"], start)
        self.assertTrue(math.isfinite(output["reward"]))
        self.assertFalse(output["terminated"] or output["truncated"])
        self.assertEqual(self.state(client)["tick"], 2)

    def test_the_episode_truncates_at_the_upstream_limit(self) -> None:
        client = self.serve()
        receipt = self.step(client, [0.0] * ACTION_VALUES, ticks=1000)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1000, False, True))
        ended = self.step(client, [0.0] * ACTION_VALUES)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")       # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("mujoco:ur5ePegInHoleGymEnv_easy-v0", "F1"))
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

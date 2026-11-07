"""Acceptance run of the panda_robot package: the gate, plus cases for this fake-only integration.

The cases run on the package's analytic fake.  The upstream PandaReacherEnv is Python 2, needs a
live ROS graph, MoveIt, franka_ros and a real Franka arm, and its envs package imports a missing
module, so nothing here constructs or compares against the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import load
from mhs.driver import close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ZERO = [0.0, 0.0, 0.0]
# The fake's placeholder start pose is [0.30, 0.0, 0.25] and its placeholder goal is
# [0.20, 0.0, 0.25]; one step of this action reaches within the placeholder threshold.
TOWARD_GOAL = [-1.0, 0.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PandaReacherCases(unittest.TestCase):
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

    def test_reset_and_step_use_the_old_gym_observation(self) -> None:
        client = self.serve()
        reset = self.reset(client)
        self.assertEqual(reset["status"], "completed")
        values = reset["output"]["observation"]["values"]
        self.assertEqual(len(values), 6)
        receipt = self.step(client, ZERO)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 1)
        self.assertLess(receipt["output"]["reward"], 0.0)
        self.assertFalse(receipt["output"]["terminated"])
        self.assertEqual(self.state(client)["tick"], 1)
        self.assertEqual(self.state(client)["observation"]["values"], receipt["output"]["observation"]["values"])

    def test_the_action_box_is_the_fake_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        for values in ([1.5, 0.0, 0.0], [0.0, -1.5, 0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        for values in ([0.0, 0.0], [0.0, 0.0, 0.0, 0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, values)
        self.assertEqual(self.state(client)["tick"], 0)              # the refused steps changed nothing

    def test_reaching_the_placeholder_goal_terminates(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, TOWARD_GOAL)
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(receipt["output"]["terminated"])
        self.assertFalse(receipt["output"]["truncated"])
        ended = self.step(client, ZERO)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_seed_class_arms_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        second = self.reset(client, seed=21)["output"]
        self.assertEqual(first["observation"], second["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertIn("analytic", fidelity["engine"])
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"]), (0, 0))
        self.assertEqual(fidelity["reset"], "full")
        self.assertFalse(fidelity["snapshot_restore"])
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_fake(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)              # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

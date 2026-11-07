"""Acceptance run of the RoboManipBaselines package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream package
needs mujoco, numpy and the training stack, is not installed where the gate runs, and package code never imports the
clone.  The numbers the cases use are the model's actuator ctrlrange values or test data, never a new bound.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
# MujocoUR5eCableEnv.py:20-30: the six arm start values of the cable task (the class appends eight zeros).
START_ARM = (math.pi, -math.pi / 2, -0.75 * math.pi, -0.25 * math.pi, math.pi / 2, math.pi / 2)
# placeholder test action: neutral arm targets and a mid-range gripper command (the gripper ctrlrange is 0 to 255)
ACTION = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 127.5]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CableTaskCases(unittest.TestCase):
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

    def step(self, client, values=ACTION, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": list(values)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_reset_restores_the_fixed_start_pose(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=4)
        self.assertEqual(receipt["status"], "completed")
        observation = receipt["output"]["observation"]
        self.assertEqual(receipt["output"]["seed"], 4)
        self.assertEqual(len(observation["joint_pos"]["values"]), 7)
        self.assertEqual(len(observation["joint_vel"]["values"]), 7)
        self.assertEqual(len(observation["wrench"]["values"]), 6)
        for got, want in zip(observation["joint_pos"]["values"][:6], START_ARM):
            self.assertAlmostEqual(got, want, places=9)
        self.assertEqual(observation["joint_pos"]["values"][6], 0.0)
        self.assertEqual(observation["joint_vel"]["values"], [0.0] * 7)
        self.assertEqual(observation["wrench"]["values"], [0.0] * 6)

    def test_a_step_advances_the_arm_and_the_tick(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertFalse(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertEqual(output["reward"], 0.0)
        # placeholder motion: the gripper leaves its start value and the arm joints move toward the commands
        self.assertGreater(output["observation"]["joint_pos"]["values"][6], 0.0)
        self.assertLess(output["observation"]["joint_pos"]["values"][0], START_ARM[0])
        self.assertNotEqual(self.state(client)["tick"], 0)

    def test_the_actuator_ctrlranges_are_the_action_envelope(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        before = self.state(client)["tick"]
        for index, value in ((0, 7.0), (2, -3.5), (6, -1.0), (6, 256.0)):
            values = list(ACTION)
            values[index] = value
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", (index, value))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
        self.assertEqual(self.state(client)["tick"], before)          # a refused step never reaches the fake
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 255.0])["status"], "completed")

    def test_the_seed_class_sets_the_next_reset_seed(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        second = self.reset(client, seed=21)["output"]
        self.assertEqual(second["seed"], 21)
        self.assertEqual(first["observation"], second["observation"])

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=3)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)               # readable, and not advanced

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "mujoco:robo_manip_baselines/MujocoUR5eCableEnv-v0")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (32.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)


if __name__ == "__main__":
    unittest.main()

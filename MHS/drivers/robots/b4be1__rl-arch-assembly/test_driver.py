"""Acceptance run of the StackingTask package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream environment
needs the missing assembly-gym submodule and PyBullet, so nothing here compares the fake with an upstream run.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ARM = "joint_velocity_difference_controller_ur10_arm"
GRIPPER = "joint_position_controller_ur10_gripper"
OBSERVATION_KEYS = {
    "arm_joint_pos_sin", "arm_joint_pos_cos", "arm_joint_vel", "gripper_joint_pos", "gripper_joint_vel",
    "end_effector_pos", "end_effector_rot", "end_effector_vel_angular", "end_effector_vel_linear",
    "current_part_pos", "current_part_rot", "current_part_vel_angular", "current_part_vel_linear",
    "current_part_target_pos", "current_part_target_rot", "time",
}
OBSERVATION_LENGTHS = {
    "arm_joint_pos_sin": 6, "arm_joint_pos_cos": 6, "arm_joint_vel": 6, "gripper_joint_pos": 1,
    "gripper_joint_vel": 1, "end_effector_pos": 3, "end_effector_rot": 6, "end_effector_vel_angular": 3,
    "end_effector_vel_linear": 3, "current_part_pos": 3, "current_part_rot": 6, "current_part_vel_angular": 3,
    "current_part_vel_linear": 3, "current_part_target_pos": 3, "current_part_target_rot": 6, "time": 1,
}


def action(arm_value=0.1, gripper_value=0.0):
    return {ARM: [arm_value] * 6, GRIPPER: [gripper_value]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class StackingTaskCases(unittest.TestCase):
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

    def step(self, client, payload=None, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": payload or action()}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_and_observation_contract(self) -> None:
        client = self.serve()
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertEqual(output["terminated"], False)
        self.assertIsInstance(output["reward"], float)
        self.assertRegex(output["state_hash"], r"^sha256:[0-9a-f]{64}$")
        observation = output["observation"]
        self.assertEqual(set(observation), OBSERVATION_KEYS)
        for key, length in OBSERVATION_LENGTHS.items():
            values = observation[key]["values"]
            self.assertEqual(len(values), length, key)
            self.assertTrue(all(-1.0 <= value <= 1.0 for value in values), (key, values))

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        for payload in ({ARM: [1.5] * 6, GRIPPER: [0.0]},
                        {ARM: [0.0] * 6, GRIPPER: [1.5]},
                        action(arm_value=-1.5)):
            refused = self.step(client, payload)
            self.assertEqual(refused["status"], "rejected", payload)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, payload)
        self.assertEqual(self.state(client)["tick"], 1)          # the refused actions changed nothing
        malformed = self.step(client, {ARM: [0.0] * 6})
        self.assertEqual(malformed["status"], "rejected")
        self.assertEqual(malformed["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")

    def test_reset_and_seed_repeat_a_trajectory(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["output"]["seed"], 7)
        observation = first["output"]["observation"]
        trajectory = [self.step(client, action(0.2), ticks=1)["output"]["observation"] for _ in range(3)]
        again = self.reset(client, seed=7)
        self.assertEqual(again["output"]["observation"], observation)
        self.assertEqual([self.step(client, action(0.2), ticks=1)["output"]["observation"] for _ in range(3)],
                         trajectory)
        other = self.reset(client, seed=8)["output"]["observation"]
        self.assertNotEqual(other, observation)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["status"], "completed")
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        seeded = self.reset(client)["output"]
        self.assertEqual(seeded["seed"], 21)
        again = self.reset(client, seed=21)["output"]
        self.assertEqual(again["observation"], seeded["observation"])

    def test_a_different_action_changes_the_state(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        left = self.step(client, action(0.5))["output"]["state_hash"]
        self.reset(client, seed=3)
        right = self.step(client, action(-0.5))["output"]["state_hash"]
        self.assertNotEqual(left, right)

    def test_the_episode_stops_at_the_placeholder_limit(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        output = None
        for _ in range(100):
            receipt = self.step(client)
            self.assertEqual(receipt["status"], "completed", receipt)
            output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (100, True, False))
        after = self.step(client)
        self.assertEqual((after["status"], after["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["safety"]["risk_class"], "R1")
        self.assertEqual(fidelity["engine"], "rl-arch-assembly:StackingTask (analytic fake)")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

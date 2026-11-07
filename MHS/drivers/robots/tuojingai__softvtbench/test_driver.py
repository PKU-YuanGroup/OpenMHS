"""Acceptance run of the SoftVTBench package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Isaac Sim and Isaac Lab
are not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SoftVTBenchCases(unittest.TestCase):
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

    @staticmethod
    def action(*values):
        # Seven values: three position components, three orientation components and one binary gripper command.
        return list(values)

    def test_the_first_step_follows_the_configured_observation_terms(self) -> None:
        client = self.serve()
        action = self.action(1.0, 2.0, 3.0, 0.0, 0.0, 0.0, 1.0)
        receipt = self.step(client, action)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["tick"], output["reward"]), (1, 0.0))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertTrue(output["state_hash"].startswith("sha256:"))
        policy = output["observation"]["policy"]
        self.assertEqual(policy["actions"]["values"], action)
        self.assertEqual(policy["eef_pose"]["values"], [1.0, 2.0, 3.0, 1.0, 0.0, 0.0, 0.0])
        self.assertEqual(policy["gripper_pos"]["values"], [0.04, -0.04])
        self.assertEqual(policy["arm_joint_pos"]["values"], [0.0] * 7)
        self.assertEqual(output["observation"]["subtask_terms"]["grasp_1"]["values"], [0.0])

    def test_the_action_has_seven_unbounded_values(self) -> None:
        client = self.serve()
        six = self.step(client, self.action(0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
        self.assertEqual(six["status"], "rejected", six)
        self.assertEqual(six["error"]["mhs_code"], INPUT_INVALID)
        # No file of the clone states a numeric action bound, so the environment's action space is unbounded and a
        # large value is accepted rather than clamped or refused by an invented limit.
        completed = self.step(client, self.action(1.0e6, -1.0e6, 0.0, 0.0, 0.0, 0.0, -1.0))
        self.assertEqual(completed["status"], "completed", completed)
        self.assertEqual(completed["output"]["observation"]["policy"]["eef_pose"]["values"][:2], [1.0e6, -1.0e6])

    def test_the_gripper_command_is_binary(self) -> None:
        client = self.serve()
        opened = self.step(client, self.action(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5))
        closed = self.step(client, self.action(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -0.5))
        self.assertEqual(opened["output"]["observation"]["policy"]["gripper_pos"]["values"], [0.04, -0.04])
        self.assertEqual(closed["output"]["observation"]["policy"]["gripper_pos"]["values"], [0.0, 0.0])

    def test_the_libero_10_episode_truncates_at_320_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, self.action(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0), ticks=320)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 320))
        ended = self.step(client, self.action(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0))
        self.assertEqual(ended["status"], "failed")
        self.assertEqual(ended["error"]["mhs_code"], PRECONDITION)
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_seed_is_echoed_and_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, self.action(0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0))["output"]["state_hash"]
                    for _ in range(3)]

        first = trajectory(7)
        self.assertEqual(trajectory(7), first)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "isaaclab:Isaac-Libero-Franka-IK-v0")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 8)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, self.action(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0))["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, self.action(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0)), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)


if __name__ == "__main__":
    unittest.main()

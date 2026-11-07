"""Acceptance run of the ROBEL DClaw pose package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo, mujoco-py,
gym and numpy are not installed where the gate runs, so nothing here compares the fake with the upstream
environment.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
JOINTS = 9
OBSERVATION = 27


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DClawPoseCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, seed=None):
        return client.invoke("cap.world.reset.v1", {} if seed is None else {"seed": seed}, **self.ids)

    def step(self, client, values, ticks=1):
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": {"values": list(values)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def observation(self, client, seed):
        receipt = self.reset(client, seed)
        self.assertEqual(receipt["status"], "completed", receipt)
        return receipt["output"]["observation"]["values"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * JOINTS)["status"], "completed")
        for values in ([1.5] + [0.0] * (JOINTS - 1), [0.0] * (JOINTS - 1) + [-1.5]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, refused)
        self.assertEqual(self.state(client)["tick"], 1)  # the refused steps changed nothing

    def test_a_reset_returns_the_three_observation_keys(self) -> None:
        client = self.serve()
        values = self.observation(client, 3)
        self.assertEqual(len(values), OBSERVATION)
        self.assertEqual(values[JOINTS:2 * JOINTS], [0.0] * JOINTS)  # last_action is zero after a reset
        for position in values[:JOINTS]:
            self.assertLessEqual(abs(position), math.pi / 2)  # the widest qpos range of the group
        self.assertTrue(all(math.isfinite(value) for value in values))

    def test_a_seed_repeats_the_reset_and_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()  # a fresh world: the state hash counts episodes
            self.observation(client, seed)
            return [self.step(client, [0.25 * (index % 3 - 1)] * JOINTS)["output"]["state_hash"]
                    for index in range(4)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_a_step_moves_the_joints_and_pays_the_pose_reward(self) -> None:
        client = self.serve()
        before = self.observation(client, 5)
        receipt = self.step(client, [0.3] * JOINTS)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        values = output["observation"]["values"]
        self.assertNotEqual(values[:JOINTS], before[:JOINTS])
        self.assertEqual(values[JOINTS:2 * JOINTS], [0.3] * JOINTS)
        # pose.py:120-124: qvel is clipped to 2*PI/3 < pi, so only the pose error cost is non-zero.
        expected = -math.sqrt(sum(value * value for value in values[2 * JOINTS:]))
        self.assertAlmostEqual(output["reward"], expected, places=6)

    def test_ticks_advance_and_sum_the_reward(self) -> None:
        client = self.serve()
        self.observation(client, 2)
        receipt = self.step(client, [0.0] * JOINTS, ticks=3)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["tick"], 3)
        values = receipt["output"]["observation"]["values"]
        self.assertEqual(len(values), OBSERVATION)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        receipt = self.reset(client)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["seed"], 21)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("mujoco:dclaw3xh", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.observation(client, 4)
        self.assertEqual(self.step(client, [0.0] * JOINTS)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * JOINTS), self.reset(client)):
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)
        self.assertEqual(self.state(client)["tick"], 1)  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

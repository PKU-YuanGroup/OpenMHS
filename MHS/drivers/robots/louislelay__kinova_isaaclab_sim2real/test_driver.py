"""Acceptance run of the gen3 driver package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Isaac Sim, Isaac Lab,
PhysX, torch and gymnasium are not installed where the gate runs, so nothing here compares the fake with the
upstream environment.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
N_JOINTS = 7


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Gen3ReachCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": list(values)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def observation(self, receipt):
        return receipt["output"]["observation"]

    def test_the_action_is_one_value_per_joint(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * N_JOINTS)["status"], "completed")
        for count in (N_JOINTS - 1, N_JOINTS + 1):
            refused = self.step(client, [0.0] * count)
            self.assertNotEqual(refused["status"], "completed", count)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, count)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_the_action_moves_the_joint_positions_by_the_configured_scale(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=0)["status"], "completed")
        # env.yaml:347-350: target = default offset + 0.5 * action; joint_pos_rel is relative to the default.
        action = [0.0] * N_JOINTS
        action[0] = 1.0
        receipt = self.step(client, action)
        self.assertEqual(receipt["status"], "completed")
        values = self.observation(receipt)["joint_pos"]["values"]
        # env.yaml:298-315: the observation adds uniform noise of at most 0.01.
        self.assertAlmostEqual(values[0], 0.5, delta=0.011)
        for value in values[1:]:
            self.assertAlmostEqual(value, 0.0, delta=0.011)

    def test_the_observation_group_and_the_command_ranges(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=0)
        self.assertEqual(receipt["status"], "completed")
        observation = self.observation(receipt)
        self.assertEqual(sorted(observation), ["actions", "joint_pos", "joint_vel", "pose_command"])
        for name, value in observation.items():
            self.assertEqual(len(value["values"]), N_JOINTS, name)
        x, y, z, qw, qx, qy, qz = observation["pose_command"]["values"]
        # env.yaml:518-535: the recorded UniformPoseCommand ranges.
        self.assertTrue(0.35 <= x <= 0.65, x)
        self.assertTrue(-0.2 <= y <= 0.2, y)
        self.assertTrue(0.15 <= z <= 0.5, z)
        self.assertAlmostEqual(math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz), 1.0, places=9)
        self.assertEqual(observation["actions"]["values"], [0.0] * N_JOINTS)   # no action precedes the reset

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()
            observations = [self.reset(client, seed=seed)["output"]["observation"]]
            for action in ([0.1] * N_JOINTS, [0.2] * N_JOINTS, [-0.1] * N_JOINTS):
                observations.append(self.step(client, action)["output"]["observation"])
            return observations

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_an_episode_truncates_after_twelve_seconds(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=0)["status"], "completed")
        # env.yaml:369 and :21-76: 12.0 s / (2 * 0.016666666666666666 s) = 360 policy steps.
        receipt = self.step(client, [0.0] * N_JOINTS, ticks=360)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 360))
        ended = self.step(client, [0.0] * N_JOINTS)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")       # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_command_resamples_every_four_seconds(self) -> None:
        client = self.serve()
        command = self.reset(client, seed=0)["output"]["observation"]["pose_command"]["values"]
        # env.yaml:511-513: resampling_time_range is (4.0, 4.0); 4.0 s / (1/30 s) = 120 policy steps.
        before = self.step(client, [0.0] * N_JOINTS, ticks=119)["output"]["observation"]["pose_command"]["values"]
        self.assertEqual(before, command)
        after = self.step(client, [0.0] * N_JOINTS)["output"]["observation"]["pose_command"]["values"]
        self.assertNotEqual(after, command)

    def test_the_observation_noise_is_bounded(self) -> None:
        client = self.serve()
        self.reset(client, seed=0)
        values = self.step(client, [0.0] * N_JOINTS)["output"]["observation"]["joint_pos"]["values"]
        self.assertTrue(all(abs(value) <= 0.0100000001 for value in values), values)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "gymnasium:Gen3-Reach-v0")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 30.0, places=6)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * N_JOINTS)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * N_JOINTS), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

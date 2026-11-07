"""Acceptance run of the legged_lab package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Isaac Sim, Isaac Lab and
gymnasium are not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_ACTION = {"values": [0.0] * 29}
# The G1 default joint positions of assets/unitree.py:94-105, in the joint_sdk_names order of :167-197.
DEFAULT_JOINTS = {
    "left_hip_pitch_joint": -0.1,
    "left_knee_joint": 0.3,
    "left_ankle_pitch_joint": -0.2,
    "left_shoulder_pitch_joint": 0.3,
    "left_shoulder_roll_joint": 0.25,
    "left_elbow_joint": 0.97,
    "left_wrist_roll_joint": 0.15,
    "right_hip_pitch_joint": -0.1,
    "right_knee_joint": 0.3,
    "right_ankle_pitch_joint": -0.2,
    "right_shoulder_pitch_joint": 0.3,
    "right_shoulder_roll_joint": -0.25,
    "right_elbow_joint": 0.97,
    "right_wrist_roll_joint": -0.15,
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class G1AmpCases(unittest.TestCase):
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
        return receipt["output"]["observation"]["policy"]["values"]

    def test_the_action_is_one_joint_position_per_g1_joint(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 29)["status"], "completed")
        for count in (28, 30):
            refused = self.step(client, [0.0] * count)
            self.assertNotEqual(refused["status"], "completed", count)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, count)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_the_action_moves_the_joint_positions_by_the_configured_scale(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=0)["status"], "completed")
        # amp_env_cfg.py:92: target = default offset + 0.25 * action
        action = [0.0] * 29
        action[0] = 1.0                                   # left_hip_pitch_joint, default -0.1 (unitree.py:95)
        action[18] = -2.0                                 # left_elbow_joint, default 0.97 (unitree.py:102)
        step = self.step(client, action)
        self.assertEqual(step["status"], "completed")
        values = self.observation(step)
        self.assertAlmostEqual(values[0], -0.1 + 0.25, places=9)
        self.assertAlmostEqual(values[18], 0.97 - 0.5, places=9)
        self.assertAlmostEqual(values[4], -0.2, places=9)  # left_ankle_pitch_joint, untouched default
        self.assertEqual(values[13], 0.0)                  # waist_roll_joint, no default in the asset config

    def test_the_observation_groups_and_their_order_match_the_asset(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        zeros = self.observation(self.step(client, [0.0] * 29))
        names = (
            "left_hip_pitch_joint", "left_hip_roll_joint", "left_hip_yaw_joint", "left_knee_joint",
            "left_ankle_pitch_joint", "left_ankle_roll_joint",
            "right_hip_pitch_joint", "right_hip_roll_joint", "right_hip_yaw_joint", "right_knee_joint",
            "right_ankle_pitch_joint", "right_ankle_roll_joint",
            "waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint",
            "left_shoulder_pitch_joint", "left_shoulder_roll_joint", "left_shoulder_yaw_joint", "left_elbow_joint",
            "left_wrist_roll_joint", "left_wrist_pitch_joint", "left_wrist_yaw_joint",
            "right_shoulder_pitch_joint", "right_shoulder_roll_joint", "right_shoulder_yaw_joint", "right_elbow_joint",
            "right_wrist_roll_joint", "right_wrist_pitch_joint", "right_wrist_yaw_joint",
        )
        self.assertEqual(len(zeros), len(names))
        self.assertEqual(len(names), 29)
        for index, name in enumerate(names):
            self.assertAlmostEqual(zeros[index], DEFAULT_JOINTS.get(name, 0.0), places=9, msg=name)

    def test_a_seed_repeats_the_stand_in_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            opened = self.reset(client, seed=seed)["output"]
            self.assertEqual(opened["seed"], seed)
            hashes = [self.step(client, [(index + 1) / 10.0] * 29)["output"]["state_hash"] for index in range(4)]
            return opened["observation"], hashes

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        # The fake's reset offset is the only seeded value: once a step writes the joint targets the observation no
        # longer depends on the seed, so the start observation is compared as well as the step hashes.
        self.assertNotEqual(trajectory(12)[0], first[0])
        self.assertEqual(trajectory(12)[1], first[1])

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_an_episode_is_truncated_after_1000_policy_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=0)["status"], "completed")
        # amp_env_cfg.py:395 with :394 and :397: 20.0 s / (4 x 0.005 s) = 1000 policy steps
        receipt = self.step(client, [0.0] * 29, ticks=1000)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 1000))
        ended = self.step(client, [0.0] * 29)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=0)["status"], "completed")       # a reset starts the next episode

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("gymnasium:LeggedLab-Isaac-AMP-G1-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 8)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 29)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * 29), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

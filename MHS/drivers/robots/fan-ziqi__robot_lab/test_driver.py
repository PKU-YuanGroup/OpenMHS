"""Acceptance run of the robot_lab G1 AMP package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py).  gymnasium, torch, Isaac Lab and Isaac Sim are not installed where the
gate runs, so nothing here compares the fake with the upstream environment; the driver's fidelity ``gaps`` say so.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
NUM_JOINTS = 29
NUM_POLICY_OBS = 105
HALF = {"values": [0.5] * NUM_JOINTS}
ZERO = {"values": [0.0] * NUM_JOINTS}


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

    def step(self, client, action, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_step_contract_and_the_action_l2_reward(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, HALF)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(len(output["observation"]["policy"]["values"]), NUM_POLICY_OBS)
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        # g1_amp_env.py:400 with rew_action_l2 = -0.1 (g1_amp_env_cfg.py:33): -0.1 * 29 * 0.5**2.
        self.assertAlmostEqual(output["reward"], -0.725, places=12)
        self.assertRegex(output["state_hash"], r"^sha256:[0-9a-f]{64}$")

    def test_the_policy_observation_has_the_compute_obs_layout(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")
        output = self.step(client, HALF)["output"]
        policy = output["observation"]["policy"]["values"]
        self.assertEqual(len(policy), NUM_POLICY_OBS)          # g1_amp_env_cfg.py:53
        # g1_amp_env.py:369-382: 29 joint positions, 29 joint velocities, root z, tangent+normal, 13 key bodies x 3,
        # progress.  The fake starts at zero and tracks 0.5 * action at rate 4; the first step is 1/60 s.
        self.assertEqual(policy[:NUM_JOINTS], [1.0 / 60.0] * NUM_JOINTS)
        self.assertEqual(policy[NUM_JOINTS:2 * NUM_JOINTS], [1.0] * NUM_JOINTS)
        self.assertEqual(policy[2 * NUM_JOINTS + 1:2 * NUM_JOINTS + 7], [1.0, 0.0, 0.0, 0.0, 0.0, 1.0])
        self.assertAlmostEqual(policy[-1], 1.0 / 599.0, places=12)  # g1_amp_env.py:110 denominator

    def test_the_action_space_refuses_out_of_range_values(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        for replacement in (-1.5, 1.5):
            values = [0.0] * NUM_JOINTS
            values[4] = replacement
            refused = self.step(client, {"values": values})
            self.assertEqual(refused["status"], "rejected", replacement)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, replacement)
        self.assertEqual(self.state(client)["tick"], 1)        # the refusals changed nothing

    def test_a_seed_repeats_the_initial_observation(self) -> None:
        def observation(seed):
            client = self.serve()
            receipt = self.reset(client, seed=seed)
            self.assertEqual(receipt["status"], "completed")
            return receipt["output"]["observation"]

        first = observation(7)
        self.assertEqual(observation(7), first)
        self.assertNotEqual(observation(8), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        second = self.reset(client, seed=21)["output"]
        self.assertEqual(first["observation"], second["observation"])

    def test_the_episode_truncates_at_max_episode_length_minus_one(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        receipt = self.step(client, ZERO, ticks=598)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertFalse(receipt["output"]["truncated"])
        receipt = self.step(client, ZERO)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        # With max_episode_length = 600, the cited >= max_episode_length - 1 predicate is true at counter 599.
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (599, False, True))
        ended = self.step(client, ZERO)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, HALF)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, HALF), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)        # readable and not advanced

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("isaaclab:RobotLab-Isaac-G1-AMP-Dance-Direct-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 60.0, places=9)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)


if __name__ == "__main__":
    unittest.main()

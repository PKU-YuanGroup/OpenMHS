"""Acceptance run of the SurgVLA ECMReach package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  Every case runs on the package's fake backend (fake.py); the PyBullet
environment is not installed where the gate runs, so nothing here compares the fake with the upstream scene.
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
START = (0.45, 0.05, 0.70)                       # surrol/tasks/ecm_reach.py:18-22


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ECMReachCases(unittest.TestCase):
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

    def observation(self, client):
        return self.state(client)["observation"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        for values in ([1.2, 0.0, 0.0], [0.0, -1.2, 0.0], [0.0, 0.0, 1.2]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                   # the refused steps changed nothing

    def test_the_first_step_moves_the_end_effector_by_the_action_scale(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        before = self.observation(client)["achieved_goal"]["values"]
        self.assertEqual(tuple(before), START)
        receipt = self.step(client, [1.0, 0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        after = receipt["output"]["observation"]["achieved_goal"]["values"]
        # EcmEnv dmove scales the action by 0.01 (surrol/tasks/ecm_env.py:140).
        self.assertAlmostEqual(after[0], START[0] + 0.01, places=12)
        self.assertAlmostEqual(after[1], START[1], places=12)
        self.assertAlmostEqual(after[2], START[2], places=12)
        self.assertEqual(receipt["output"]["tick"], 1)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, values)["output"]["state_hash"]
                    for values in ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0])]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_episode_truncates_at_50_steps(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        receipt = self.step(client, [0.0, 0.0, 0.0], ticks=50)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # ECMReach-v0 is registered with max_episode_steps=50 (surrol/gym/__init__.py:46); gym.make adds the
        # TimeLimit wrapper, and the env itself never sets done (surrol/gym/surrol_env.py:109).
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 50))
        self.assertEqual(output["reward"], -50.0)                  # the sparse reward is -1 per step off-goal
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["error"]["mhs_code"], PRECONDITION)
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_observation_has_the_documented_shapes(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        observation = self.observation(client)
        self.assertEqual(len(observation["observation"]["values"]), 6)   # ecm_env.py:93-116
        self.assertEqual(len(observation["achieved_goal"]["values"]), 3)
        self.assertEqual(len(observation["desired_goal"]["values"]), 3)

    def test_the_goal_is_sampled_inside_the_workspace(self) -> None:
        client = self.serve()
        bounds = ((0.45, 0.55), (-0.05, 0.05), (0.60, 0.70))         # ecm_reach.py:12
        for seed in range(8):
            goal = self.reset(client, seed=seed)["output"]["observation"]["desired_goal"]["values"]
            for value, (low, high) in zip(goal, bounds):
                self.assertGreaterEqual(value, low)
                self.assertLessEqual(value, high)

    def test_a_negative_seed_is_refused_by_the_class_schema(self) -> None:
        client = self.serve()
        refused = self.reset(client, seed=-1)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("pybullet", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (1000.0 / 240.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                 # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the Easy DRL Isaac Sim package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py); Isaac Sim 2021.2.1 is not installed where the gate runs, so nothing here
compares the fake with the upstream environment.  The direct-fake case exercises the old Gym step result and the
upstream time-limit offset (env.py:34,159) without the bridge's own tick counter.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class IsaacSimCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return client, {"device_id": device_id, "session_id": session}

    def reset(self, client, ids, **fields):
        return client.invoke("cap.world.reset.v1", fields, **ids)

    def step(self, client, ids, index, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"index": index}}, **ids)

    def state(self, client, ids):
        return client.read("world", **ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client, ids = self.serve()
        self.assertEqual(self.step(client, ids, 1)["status"], "completed")
        for index in (-1, 3):
            refused = self.step(client, ids, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client, ids)["tick"], 1)            # the refused steps changed nothing

    def test_the_observation_has_the_upstream_layout(self) -> None:
        client, ids = self.serve()
        reset = self.reset(client, ids, seed=3)
        self.assertEqual(reset["status"], "completed")
        receipt = self.step(client, ids, 1)
        self.assertEqual(receipt["status"], "completed")
        observation = receipt["output"]["observation"]
        self.assertEqual(set(observation), {"IR_raleted", "pos_raleted", "vel_raleted"})
        lidar = observation["IR_raleted"]["values"]
        self.assertEqual((len(lidar), len(lidar[0])), (1, 12))           # env.py:108
        self.assertEqual(len(observation["pos_raleted"]["values"]), 2)    # env.py:229
        self.assertEqual(len(observation["vel_raleted"]["values"]), 2)    # env.py:235
        self.assertTrue(all(0.0 <= value <= 1.0 for value in lidar[0]))
        self.assertEqual(receipt["output"]["tick"], 1)
        self.assertIsInstance(receipt["output"]["reward"], float)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client, ids = self.serve()
            self.assertEqual(self.reset(client, ids, seed=seed)["output"]["seed"], seed)
            return [self.step(client, ids, action)["output"]["state_hash"] for action in (0, 1, 2, 1, 0)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client, ids = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        first = self.reset(client, ids)["output"]
        self.assertEqual(first["seed"], 21)
        second = self.reset(client, ids, seed=21)["output"]
        self.assertEqual(first["observation"], second["observation"])

    def test_the_time_limit_uses_the_upstream_offset(self) -> None:
        driver = load_driver(HERE, backend="fake")
        self.addCleanup(driver.close)
        env = driver.native
        env._max_episode_length = 2                        # placeholder: small limit to reach it quickly
        env.seed(11)
        env.reset()
        results = [env.step(1) for _ in range(3)]
        # env.py:159: done when world_index - steps_after_reset >= max_episode_length, with steps_after_reset = 1
        self.assertEqual([result[2] for result in results], [False, False, True])
        self.assertEqual(env.step_count, 3)

    def test_the_goal_angle_preserves_the_pinned_quaternion_expression(self) -> None:
        driver = load_driver(HERE, backend="fake")
        self.addCleanup(driver.close)
        env = driver.native
        # Placeholder planar poses. isaac_robots.py:245-259 assigns qx=qy=0 for the fake's quaternion
        # [0, 0, sin(yaw/2), cos(yaw/2)], so theta is pi for either heading, not the heading itself.
        env._x = env._y = 0.0
        env._goal = [0.0, 1.0, 0.25]
        for yaw in (math.pi / 2.0, -math.pi / 2.0):
            env._yaw = yaw
            self.assertAlmostEqual(env.get_observations()["pos_raleted"][1], math.pi / 2.0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client, ids = self.serve()
        device = client.inspect(ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "isaac-sim-2021.2.1 (analytic fake)")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 60.0)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client, ids = self.serve()
        self.assertEqual(self.step(client, ids, 1)["status"], "completed")
        client.estop("test", **ids)
        for refused in (self.step(client, ids, 1), self.reset(client, ids, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client, ids)["tick"], 1)             # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the gym-agx package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): AGX Dynamics is not installed where the gate runs, so nothing here
compares the fake with the upstream environment.  The fake's start jitter, curvature length and goal array are test
data, not facts about the device.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_ACTION = {"values": [0.0, 0.0, 0.0]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class BendWireCases(unittest.TestCase):
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
    def observation(receipt):
        return receipt["output"]["observation"]

    @staticmethod
    def position(observation):
        return observation["observation"]["ee_position"]["gripper_right"]["values"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        for values in ([1.1, 0.0, 0.0], [0.0, -1.1, 0.0], [0.0, 0.0, 1.1]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_the_first_step_uses_the_acceleration_limit(self) -> None:
        client = self.serve()
        start = self.observation(self.reset(client, seed=3))
        receipt = self.step(client, [1.0, 0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        before, after = self.position(start), self.position(self.observation(receipt))
        # end_effector.py:183-186: one step may change the speed by max_acceleration*dt = 0.01*0.02 = 0.0002 m/s,
        # and the position by that speed times dt
        self.assertAlmostEqual(after[0] - before[0], 0.0002 * 0.02, places=12)
        self.assertAlmostEqual(after[1], before[1], places=12)
        self.assertAlmostEqual(after[2], before[2], places=12)

    def test_the_dense_reward_is_the_negative_curvature_distance(self) -> None:
        client = self.serve()
        observation = self.observation(self.reset(client, seed=5))
        achieved = observation["achieved_goal"]["dlo_curvature"]["values"]
        desired = observation["desired_goal"]["dlo_curvature"]["values"]
        distance = math.sqrt(sum((a - d) ** 2 for a, d in zip(achieved, desired)))
        self.assertGreater(distance, 0.05)
        receipt = self.step(client, [0.0, 0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        # bend_wire_env.py:24-37 and :39-40: clip(-distance, -1.5, 1.5), then round to four decimals
        self.assertAlmostEqual(receipt["output"]["reward"], round(max(-1.5, min(1.5, -distance)), 4), places=12)
        self.assertEqual(receipt["output"]["terminated"], False)
        self.assertEqual(receipt["output"]["truncated"], False)

    def test_the_observation_has_the_goal_env_shape(self) -> None:
        client = self.serve()
        observation = self.observation(self.reset(client, seed=7))
        self.assertEqual(sorted(observation), ["achieved_goal", "desired_goal", "observation"])
        for part in ("achieved_goal", "desired_goal"):
            self.assertIn("dlo_curvature", observation[part])
            self.assertIn("ee_velocity", observation[part])
            self.assertIn("gripper_right", observation[part]["ee_velocity"])
        self.assertIn("ee_position", observation["observation"])
        achieved = observation["achieved_goal"]["dlo_curvature"]["values"]
        desired = observation["desired_goal"]["dlo_curvature"]["values"]
        self.assertEqual(len(achieved), len(desired))
        self.assertTrue(all(math.isfinite(value) for value in achieved + desired))

    def test_a_seed_repeats_the_trajectory(self) -> None:
        actions = ([0.5, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, -1.0])

        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["status"], "completed")
            return [self.step(client, action)["output"]["state_hash"] for action in actions]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_episode_stops_at_1000_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, [0.0, 0.0, 0.0], ticks=1000)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # gym_agx/__init__.py:34: max_episode_steps=1000.  The legacy four-value step reports it as done, which the
        # bridge maps to terminated (agx_goal_env.py:166-178).
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 1000))
        ended = self.step(client, [0.0, 0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")       # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("agx-dynamics:BendWire-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the AirGym package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): AirSim, gym, numpy, cv2,
eventlet and PIL are not installed where the gate runs, and the clone is never imported.  The numbers checked here
are the fake's placeholder pose and the upstream constants cited in driver.py and fake.py, not measurements.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
GOAL_REWARD = 100.0                       # AirGym.py:102
GOAL_RADIUS = 3.0                         # AirGym.py:100


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AirGymCases(unittest.TestCase):
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

    def step(self, client, index, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"index": index}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        for index in (-1, 3):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        for ticks in (0, 10001):
            refused = self.step(client, 1, ticks=ticks)
            self.assertEqual(refused["status"], "rejected", ticks)
            self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID", ticks)
        self.assertEqual(self.state(client)["tick"], 1)       # the refused steps changed nothing

    def test_straight_moves_four_metres_along_the_heading(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, 0)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 1)
        info = self.state(client)["info"]
        # the fake starts at (0, 0) facing the goal (placeholder); straight is 4 m/s for 1 s (myAirSimClient.py:72)
        self.assertAlmostEqual(info["x_pos"], 4.0 * math.cos(math.atan2(-9.0, 221.0)), places=6)
        self.assertAlmostEqual(info["y_pos"], 4.0 * math.sin(math.atan2(-9.0, 221.0)), places=6)
        self.assertEqual(len(receipt["output"]["observation"]["values"]), 30)

    def test_a_turn_in_place_pays_the_step_penalty(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        self.assertEqual(self.step(client, 0)["status"], "completed")   # align the distance log with the pose
        for index in (1, 2):
            receipt = self.step(client, index)
            self.assertEqual(receipt["status"], "completed")
            # no translation, so the distance reward is -1 plus zero (AirGym.py:60-70)
            self.assertEqual(receipt["output"]["reward"], -1.0)

    def test_the_observation_is_a_30_by_100_byte_image(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=1)["output"]["observation"]["values"]
        self.assertEqual(len(observation), 30)
        for row in observation:
            self.assertEqual(len(row), 100)
            self.assertTrue(all(isinstance(value, int) and 0 <= value <= 255 for value in row))

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                    # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, index)["output"]["state_hash"] for index in (0, 1, 0, 2)]

        first = trajectory(7)
        self.assertEqual(trajectory(7), first)
        self.assertNotEqual(trajectory(8), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_reaching_the_goal_ends_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        # the fake flies straight toward (221, -9) at 4 m/step; 55 steps close 220 of the 221.18 m
        receipt = self.step(client, 0, ticks=60)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(output["terminated"])
        self.assertEqual(output["tick"], 55)
        self.assertGreaterEqual(output["reward"], GOAL_REWARD)
        self.assertEqual(self.state(client)["terminated"], True)

    def test_a_cumulative_penalty_ends_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        # yaw in place pays about -1 per step; the first pays -1.18 because the distance log starts at 221 while the
        # placeholder pose is 221.18 m from the goal.  The reward log starts at 0 (AirGym.py:35).
        receipt = self.step(client, 1, ticks=110)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(output["terminated"])
        self.assertEqual(output["tick"], 100)
        self.assertLess(output["reward"], -100.0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("airsim-gym:AirSimEnv", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (1000.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)
        self.assertGreater(GOAL_RADIUS, 0)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 0), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

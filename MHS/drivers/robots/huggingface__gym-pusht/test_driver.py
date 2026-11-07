"""Acceptance run of the gym-pusht package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): gym_pusht itself is not
installed where the gate runs, so nothing here compares the fake with the upstream environment.
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
GOAL_POSE = [256.0, 256.0, math.pi / 4]     # pusht.py:447
BLOCK_COG_Y = 45.0                          # pusht.py:511


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PushTCases(unittest.TestCase):
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

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0])["status"], "completed")
        for values in ([-1.0, 0.0], [0.0, 513.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                 # the refused steps changed nothing

    def test_the_first_step_follows_the_pd_control(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3,
                                    options={"reset_to_state": [100.0, 100.0, 256.0, 300.0, 0.0]})["status"],
                         "completed")
        receipt = self.step(client, [300.0, 100.0])
        self.assertEqual(receipt["status"], "completed")
        values = receipt["output"]["observation"]["values"]
        # by hand from pusht.py:247-253 with the agent at rest at (100, 100), the target x 300, k_p 100, k_v 20,
        # dt 0.01 and 10 substeps: the agent moves +x and the y error stays 0
        position, velocity = [100.0, 100.0], [0.0, 0.0]
        for _ in range(10):
            velocity[0] += (100.0 * (300.0 - position[0]) - 20.0 * velocity[0]) * 0.01
            velocity[1] += (100.0 * (100.0 - position[1]) - 20.0 * velocity[1]) * 0.01
            position[0] += velocity[0] * 0.01
            position[1] += velocity[1] * 0.01
        self.assertAlmostEqual(values[0], position[0], places=6)
        self.assertAlmostEqual(values[1], 100.0, places=6)
        self.assertGreater(values[0], 100.0)
        self.assertTrue(0.0 <= receipt["output"]["reward"] <= 1.0)      # pusht.py:257

    def test_a_reset_to_state_sets_the_observation(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=1, options={"reset_to_state": [100.0, 200.0, 300.0, 200.0, 0.5]})
        self.assertEqual(receipt["status"], "completed")
        values = receipt["output"]["observation"]["values"]
        self.assertEqual(values[:4], [100.0, 200.0, 300.0, 200.0])       # pusht.py:456-462
        self.assertAlmostEqual(values[4], 0.5)                          # the angle modulo 2*pi

    def test_a_random_reset_stays_in_the_documented_ranges(self) -> None:
        client = self.serve()
        values = self.reset(client, seed=5)["output"]["observation"]["values"]
        self.assertTrue(50 <= values[0] < 450 and 50 <= values[1] < 450, values)   # pusht.py:278-279
        self.assertTrue(100 <= values[2] < 400 and 100 <= values[3] < 400, values)  # pusht.py:280-281
        self.assertTrue(0 <= values[4] < 2 * math.pi, values)                     # :385 and :188

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                          # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, [256.0, 256.0])["output"]["state_hash"] for _ in range(3)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_goal_pose_terminates_the_episode(self) -> None:
        client = self.serve()
        # the block tee covers the goal tee when its centre of gravity sits at goal_pose + R(pi/4) * (0, 45)
        # (pusht.py:403-412, :447 and :511)
        block_x = GOAL_POSE[0] - math.sin(GOAL_POSE[2]) * BLOCK_COG_Y
        block_y = GOAL_POSE[1] + math.cos(GOAL_POSE[2]) * BLOCK_COG_Y
        self.assertEqual(self.reset(client, seed=0,
                                    options={"reset_to_state": [100.0, 100.0, block_x, block_y, GOAL_POSE[2]]})
                         ["status"], "completed")
        receipt = self.step(client, [100.0, 100.0])
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(output["terminated"])                          # pusht.py:258
        self.assertFalse(output["truncated"])                          # pusht.py:265
        self.assertAlmostEqual(output["reward"], 1.0, places=6)        # pusht.py:257
        ended = self.step(client, [100.0, 100.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=0)["status"], "completed")   # a reset starts the next episode

    def test_an_episode_is_truncated_at_300_steps(self) -> None:
        client = self.serve()
        self.reset(client, seed=1, options={"reset_to_state": [50.0, 450.0, 120.0, 120.0, 0.0]})
        receipt = self.step(client, [50.0, 450.0], ticks=300)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # max_episode_steps 300 is the TimeLimit wrapper that gymnasium.make adds (gym_pusht/__init__.py:6)
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (300, False, True))
        ended = self.step(client, [50.0, 450.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:gym_pusht/PushT-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (100.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [256.0, 256.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [256.0, 256.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                 # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

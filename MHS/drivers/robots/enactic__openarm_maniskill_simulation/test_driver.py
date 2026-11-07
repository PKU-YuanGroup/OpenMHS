"""Acceptance run of the OpenArm PickCube-v1 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the real ManiSkill,
SAPIEN and torch environment is not installed where the gate runs and package code never imports or runs the clone.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
OPEN_GRIPPER = 0.0451


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PickCubeCases(unittest.TestCase):
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

    def step(self, client, delta, gripper=OPEN_GRIPPER, ticks=1):
        return client.invoke(
            "cap.world.step.v1",
            {"ticks": ticks, "action": {"tcp_delta": list(delta), "gripper": gripper}},
            **self.ids,
        )

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def observation(self, client):
        return self.state(client)["observation"]

    def test_a_seed_repeats_the_reset_positions(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)
        self.assertEqual(first["status"], "completed")
        observation = first["output"]["observation"]
        self.assertEqual(first["output"]["seed"], 11)
        second = self.reset(client, seed=11)["output"]["observation"]
        self.assertEqual(second, observation)
        other = self.reset(client, seed=12)["output"]["observation"]
        self.assertNotEqual(other, observation)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"seed": 21, "accepted": True})
        self.assertEqual(self.reset(client)["output"]["seed"], 21)
        self.assertEqual(self.reset(client, seed=7)["output"]["seed"], 7)

    def test_the_cube_and_goal_follow_the_config(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        observation = self.observation(client)
        cube = observation["obj_pose"][:3]
        goal = observation["goal_pos"]
        tcp = observation["tcp_pose"][:3]
        # pick_cube_cfgs.py:70-80: spawn half-size 0.05, cube half-size 0.02, max goal height 0.3
        self.assertTrue(-0.05 <= cube[0] <= 0.05, cube)
        self.assertTrue(-0.05 <= cube[1] <= 0.05, cube)
        self.assertAlmostEqual(cube[2], 0.02, places=9)
        self.assertTrue(-0.05 <= goal[0] <= 0.05, goal)
        self.assertTrue(-0.05 <= goal[1] <= 0.05, goal)
        self.assertTrue(cube[2] <= goal[2] <= cube[2] + 0.3, goal)
        # the fake starts the TCP above the cube (placeholder start position)
        self.assertEqual((tcp[0], tcp[1]), (cube[0], cube[1]))
        self.assertGreater(tcp[2], cube[2])

    def test_a_step_changes_the_tick_and_the_observation(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, [0.0, 0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        self.assertIsInstance(output["reward"], float)
        self.assertTrue(output["state_hash"].startswith("sha256:"))
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_action_limits_refuse_before_the_native_call(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        for delta, gripper in (([0.11, 0.0, 0.0], OPEN_GRIPPER),
                               ([0.0, 0.0, 0.0], -0.01),
                               ([0.0, 0.0, 0.0], 0.05)):
            refused = self.step(client, delta, gripper)
            self.assertEqual(refused["status"], "rejected", (delta, gripper))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (delta, gripper))
        self.assertEqual(self.state(client)["tick"], 0)

    def test_grasp_and_place_reach_the_success_reward(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        observation = self.observation(client)
        cube = observation["obj_pose"][:3]
        goal = observation["goal_pos"]
        # put the TCP at the cube and close the gripper; the fake grasp test is a distance test (a gap)
        receipt = self.step(client, [0.0, 0.0, cube[2] - observation["tcp_pose"][2]], gripper=0.0)
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(self.observation(client)["is_grasped"])
        # move the held cube to the goal, at most 0.1 m per axis per step (openarm.py:100-109)
        for _ in range(40):
            current = self.observation(client)["obj_pose"][:3]
            delta = [max(-0.1, min(0.1, goal[index] - current[index])) for index in range(3)]
            receipt = self.step(client, delta, gripper=0.0)
            self.assertEqual(receipt["status"], "completed")
            if receipt["output"]["reward"] == 5.0:
                break
        self.assertEqual(receipt["output"]["reward"], 5.0)
        self.assertFalse(receipt["output"]["terminated"])
        self.assertEqual(self.state(client)["observation"]["is_grasped"], True)

    def test_fifty_steps_truncate_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        output = None
        for expected_tick in range(1, 51):
            receipt = self.step(client, [0.0, 0.0, 0.0], gripper=OPEN_GRIPPER)
            self.assertEqual(receipt["status"], "completed", expected_tick)
            output = receipt["output"]
            self.assertEqual(output["tick"], expected_tick)
        # pick_cube.py:34: max_episode_steps=50, so the 50th step truncates
        self.assertEqual((output["terminated"], output["truncated"]), (False, True))
        ended = self.step(client, [0.0, 0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["safety"]["risk_class"], "R0")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("sapien:mani_skill:PickCube-v1", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.reset(client, seed=6)
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0, 0.0]), self.reset(client, seed=6)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                 # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

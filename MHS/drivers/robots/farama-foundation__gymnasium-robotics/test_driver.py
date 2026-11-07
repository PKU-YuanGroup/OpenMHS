"""Acceptance run of the FetchSlide-v4 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream package is
not installed where the gate runs, so nothing here compares the fake with MuJoCo.
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
ZERO_ACTION = [0.0, 0.0, 0.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FetchSlideCases(unittest.TestCase):
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

    @staticmethod
    def observation(receipt):
        return receipt["output"]["observation"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        for index in range(4):
            for value in (-2.0, 2.0):
                values = list(ZERO_ACTION)
                values[index] = value
                refused = self.step(client, values)
                self.assertEqual(refused["status"], "rejected", (index, value))
                self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (index, value))
        self.assertEqual(self.state(client)["tick"], 1)                   # the refused steps changed nothing

    def test_the_reset_matches_the_documented_start_state(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=7)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 7)
        observation = self.observation(receipt)
        values = observation["observation"]["values"]
        achieved = observation["achieved_goal"]["values"]
        desired = observation["desired_goal"]["values"]
        self.assertEqual((len(values), len(achieved), len(desired)), (25, 3, 3))
        gripper = values[0:3]
        puck = values[3:6]
        # slide.py:132: the gripper starts at [1, 0.75, 0.41] m
        for actual, expected in zip(gripper, (1.0, 0.75, 0.41)):
            self.assertAlmostEqual(actual, expected, places=7)
        # slide.py:134: the puck sits at z = 0.42 and at least 0.1 m away in the x,y plane
        self.assertAlmostEqual(puck[2], 0.42, places=7)
        self.assertGreater(math.hypot(puck[0] - gripper[0], puck[1] - gripper[1]), 0.1)
        self.assertEqual(achieved, puck)
        self.assertAlmostEqual(desired[2], 0.42, places=7)
        self.assertEqual(values[9:11], [0.0, 0.0])                       # block_gripper=True (slide.py:177)

    def test_the_position_control_scales_by_005(self) -> None:
        client = self.serve()
        before = self.observation(self.reset(client, seed=3))["observation"]["values"]
        receipt = self.step(client, [1.0, 0.0, 0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        after = output["observation"]["observation"]["values"]
        self.assertAlmostEqual(after[0], before[0] + 0.05, places=7)     # fetch_env.py:92
        self.assertAlmostEqual(after[1], before[1], places=7)
        self.assertAlmostEqual(after[2], before[2], places=7)
        self.assertEqual((output["reward"], output["tick"]), (-1.0, 1))

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            first = self.observation(self.reset(client, seed=seed))
            hashes = []
            for values in ([1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], ZERO_ACTION):
                receipt = self.step(client, values)
                self.assertEqual(receipt["status"], "completed")
                hashes.append(receipt["output"]["state_hash"])
            return first, hashes

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.observation(self.reset(client))
        self.assertEqual(self.observation(self.reset(client, seed=21)), first)

    def test_the_episode_truncates_at_50_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=9)["status"], "completed")
        for expected_tick in range(1, 51):
            receipt = self.step(client, ZERO_ACTION)
            self.assertEqual(receipt["status"], "completed", expected_tick)
            output = receipt["output"]
            self.assertEqual(output["tick"], expected_tick)
        # __init__.py:37 and slide.py:142: max_episode_steps=50, never terminated
        self.assertEqual((output["terminated"], output["truncated"]), (False, True))
        ended = self.step(client, ZERO_ACTION)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=9)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("gymnasium-robotics:FetchSlide-v4", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (40.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                   # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

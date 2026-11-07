"""Acceptance run of the Space Robotics Bench package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  Every case runs on the fake backend (fake.py): the upstream
environment needs Python 3.11, NVIDIA Omniverse and Isaac Sim (srb/__main__.py:37-40) and is not imported here.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
# the default action has seven values: the Franka's six pose values and its hand's gripper value
ZERO_ACTION = [0.0] * 7
HALF_ACTION = [0.5] * 7


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SpaceRoboticsBenchCases(unittest.TestCase):
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

    def test_the_action_box_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, HALF_ACTION)["status"], "completed")
        outside = [1.5] * 7
        refused = self.step(client, outside)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        short = self.step(client, [0.0] * 6)
        self.assertEqual(short["status"], "rejected")          # the Box has seven elements: the six pose values alone
        self.assertEqual(self.state(client)["tick"], 1)         # the refused steps changed nothing

    def test_the_reward_is_the_action_rate_penalty(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        first = self.step(client, HALF_ACTION)
        # task.py:192-196: -0.5 * mean((action - previous_action)^2) = -0.5 * 0.25 with a zero previous action
        self.assertAlmostEqual(first["output"]["reward"], -0.125, places=12)
        self.assertEqual((first["output"]["terminated"], first["output"]["truncated"]), (False, False))
        second = self.step(client, HALF_ACTION)
        self.assertEqual(second["output"]["reward"], 0.0)       # the action did not change
        observation = second["output"]["observation"]
        # impl.py:543-556: each group is one vector of its members, concatenated in sorted name order
        self.assertEqual(sorted(observation), ["proprio", "proprio_dyn"])
        self.assertEqual(len(observation["proprio"]["values"]), 3 + 6)          # position, 6D rotation
        self.assertEqual(len(observation["proprio_dyn"]["values"]), 2 + 7)      # hand joints, arm joints

    def test_the_gripper_value_opens_and_closes_the_hand(self) -> None:
        client = self.serve()

        def hand_and_arm(response):
            values = response["output"]["observation"]["proprio_dyn"]["values"]
            return values[:2], values[2:]                                   # the hand's two joints sort first

        start, arm = hand_and_arm(self.reset(client, seed=5))
        self.assertEqual(start, [1.0, 1.0])                                 # franka_hand.py:40 starts the hand open
        closed, closed_arm = hand_and_arm(self.step(client, [0.0] * 6 + [-1.0]))
        self.assertEqual(closed, [-1.0, -1.0])                              # a negative value closes it
        self.assertEqual(closed_arm, arm)                                   # the arm stays
        opened, _ = hand_and_arm(self.step(client, ZERO_ACTION))
        self.assertEqual(opened, [1.0, 1.0])                                # any other value opens it
        self.step(client, [0.0] * 6 + [-0.5])
        reset, _ = hand_and_arm(self.reset(client, seed=5))
        self.assertEqual(reset, [1.0, 1.0])                                 # a reset opens it again

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"]
                    for action in (HALF_ACTION, ZERO_ACTION, HALF_ACTION)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_episode_truncates_at_500_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        output = self.step(client, ZERO_ACTION, ticks=500)["output"]
        # task.py:41-42 and env.py:79-80: 10 s at 1/50 s per agent step
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 500))
        ended = self.step(client, ZERO_ACTION)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")       # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("isaac:srb/_manipulation (kinematic fake stand-in)", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, HALF_ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, HALF_ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

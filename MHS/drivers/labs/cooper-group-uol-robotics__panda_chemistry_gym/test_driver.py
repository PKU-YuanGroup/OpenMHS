"""Acceptance run of the Capping package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): PyBullet, gym and
gym_robotics are not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_ACTION = {"values": [0.0, 0.0, 0.0, 0.0]}
PUSH_X = {"values": [1.0, 0.0, 0.0, 0.0]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CappingCases(unittest.TestCase):
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

    def step(self, client, action=None, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action or ZERO_ACTION}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        for values in ([1.5, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, -1.5]):
            refused = self.step(client, {"values": values})
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_the_observation_layout_is_16_plus_two_goals_of_6(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=1)["output"]["observation"]
        values = observation["observation"]["values"]
        achieved = observation["achieved_goal"]["values"]
        desired = observation["desired_goal"]["values"]
        self.assertEqual((len(values), len(achieved), len(desired)), (16, 6, 6))
        # placeholder fake layout: 7 robot values (ee position, ee velocity, finger width), then 9 cap values
        self.assertEqual(values[:3], [0.0, 0.0, 0.2])
        self.assertEqual(achieved[:3], values[7:10])                              # cap position (Capping_Task.py:166)
        self.assertEqual(achieved[3:], values[:3])                                # ee position (Capping_Task.py:166)
        self.assertEqual(desired[3:], [0.1, 0.0, 0.2])                            # placeholder ee target
        self.assertEqual(len(observation["desired_goal"]["values"]), 6)

    def test_one_step_moves_the_end_effector_by_the_scaled_action(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, {"values": [0.2, 0.0, 0.0, 0.0]})
        self.assertEqual(receipt["status"], "completed")
        values = receipt["output"]["observation"]["observation"]["values"]
        # the fake scales the first three action values by 0.05 (panda.py:66), from the placeholder zero x
        self.assertAlmostEqual(values[0], 0.01, places=9)
        self.assertEqual((receipt["output"]["terminated"], receipt["output"]["tick"]), (False, 1))

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, ZERO_ACTION)["output"]["state_hash"] for _ in range(3)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_reaching_the_goal_pays_the_success_reward(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        first = self.step(client, PUSH_X)["output"]
        self.assertEqual(first["terminated"], False)
        self.assertLess(first["reward"], 1.0)                     # -distance before the goal is reached
        receipt = self.step(client, PUSH_X)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # placeholder fake: two 0.05 m steps reach the fixed ee target; the upstream reward is 1.0 on success
        # (Capping_Task.py:219-220)
        self.assertTrue(output["observation"]["desired_goal"]["values"])
        self.assertEqual(output["reward"], 1.0)
        self.assertEqual(self.state(client)["info"]["is_success"], True)
        self.assertEqual(output["terminated"], False)

    def test_the_registered_step_limit_ends_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        output = None
        for _ in range(100):
            receipt = self.step(client, ZERO_ACTION)
            self.assertEqual(receipt["status"], "completed", receipt)
            output = receipt["output"]
        # Capping-v1 is registered with max_episode_steps=100 (custom_envs/__init__.py:18); the old Gym four-tuple
        # carries the limit in done, which the bridge reports as terminated
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (100, True, False))
        self.assertEqual(self.state(client)["info"]["TimeLimit.truncated"], True)
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
                         ("pybullet:panda_chemistry_gym/Capping-v1", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (2.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the SRU navigation-simulation package: the gate, plus cases for what is specific to this driver.

The cases run on the analytic fake backend (fake.py); Isaac Lab, Isaac Sim and the upstream clone are never imported.
They check the 3-dimensional SE2 action envelope, the seeded reset, the 300-step/60 s truncation, the goal-dwell
truncation, the published F0 fidelity contract and the software e-stop latch.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_ACTION = {"values": [0.0, 0.0, 0.0]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class NavigationCases(unittest.TestCase):
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

    def test_the_action_is_a_bounded_three_element_se2_command(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        for values in ([1.5, 0.0, 0.0], [0.0, 0.0, -2.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        for values in ([0.0, 0.0], [0.0, 0.0, 0.0, 0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, values)
        self.assertEqual(self.state(client)["tick"], 1)        # every refused step changed nothing

    def test_a_seed_repeats_the_fake_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, [0.5, 0.1, 0.2])["output"]["state_hash"] for _ in range(5)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(receipt["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_four_observation_groups_are_published(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=2)["output"]["observation"]
        self.assertEqual(sorted(observation), ["critic", "low_level_policy", "metrics", "policy"])
        self.assertEqual({name: len(group["values"]) for name, group in observation.items()},
                         {"policy": 10, "critic": 12, "low_level_policy": 10, "metrics": 1})

    def test_the_episode_is_truncated_at_300_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, [0.0, 0.0, 0.0], ticks=300)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # navigation_env_cfg.py:421-428: episode_length_s = 60.0 and one step is 0.2 s, so 300 steps
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 300))
        ended = self.step(client, [0.0, 0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.state(client)["tick"], 300)

    def test_the_goal_counter_keeps_running_after_leaving_the_goal(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        output = self.step(client, [0.0, 0.0, 0.0])["output"]
        for _ in range(250):
            if output["observation"]["metrics"]["values"][0]:
                break
            policy = output["observation"]["policy"]["values"]
            low_level = output["observation"]["low_level_policy"]["values"]
            goal_x, goal_y = policy[3], policy[4]
            x, y, yaw = low_level[3], low_level[4], low_level[5]
            heading = math.atan2(goal_y - y, goal_x - x)
            error = (heading - yaw + math.pi) % (2.0 * math.pi) - math.pi
            action = [max(-1.0, min(1.0, value))
                      for value in (math.cos(error), math.sin(error), error)]
            output = self.step(client, action)["output"]
        self.assertTrue(output["observation"]["metrics"]["values"][0], output)
        reached_tick = output["tick"]
        self.assertFalse(output["truncated"])
        # time_out_navigation records the first entry (terminations.py:62-65); at_goal_navigation then counts
        # every step, including outside the radius (:158-166). required_steps_at_goal is 20 at this step size.
        for _ in range(20):
            policy = output["observation"]["policy"]["values"]
            low_level = output["observation"]["low_level_policy"]["values"]
            heading = math.atan2(policy[4] - low_level[4], policy[3] - low_level[3]) - low_level[5]
            output = self.step(client, [-math.cos(heading), -math.sin(heading), 0.0])["output"]
        self.assertEqual(output["observation"]["metrics"]["values"][0], 0.0)
        self.assertEqual(output["tick"], reached_tick + 20)
        self.assertTrue(output["truncated"], output)
        self.assertFalse(output["terminated"], output)

    def test_the_f0_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("analytic", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (200.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)
        self.assertTrue(any("absence of dynamics" in gap for gap in fidelity["gaps"]))

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)        # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

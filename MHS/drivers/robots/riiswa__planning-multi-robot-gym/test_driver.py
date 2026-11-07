"""Acceptance run of the Planning Multi-Robot Gym package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): the upstream environment is not installed where the gate runs, so nothing
here compares the fake with the upstream environment.  Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
N_ROBOTS = 5


def wheels(value):
    """One wheel-speed value for each robot of the fake's default configuration (test data, not a fact)."""
    return [value] * N_ROBOTS


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PlanningMultiRobotCases(unittest.TestCase):
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

    def step(self, client, v_right, v_left, ticks=1):
        return client.invoke(
            "cap.world.step.v1",
            {"ticks": ticks, "action": {"vR": wheels(v_right), "vL": wheels(v_left)}},
            **self.ids,
        )

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_bounds_both_wheel_arrays(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0.0, 0.0)["status"], "completed")
        for bad in ({"vR": wheels(0.6), "vL": wheels(0.0)},
                    {"vR": wheels(0.0), "vL": wheels(-0.6)}):
            refused = client.invoke("cap.world.step.v1", {"ticks": 1, "action": bad}, **self.ids)
            self.assertEqual(refused["status"], "rejected", bad)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, bad)
        wrong_shape = client.invoke("cap.world.step.v1",
                                    {"ticks": 1, "action": {"vR": [0.0] * 4, "vL": wheels(0.0)}},
                                    **self.ids)
        self.assertEqual(wrong_shape["status"], "rejected")
        self.assertEqual(wrong_shape["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 1)                   # the refused steps changed nothing

    def test_a_step_requires_an_action(self) -> None:
        client = self.serve()
        refused = client.invoke("cap.world.step.v1", {"ticks": 1}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)

    def test_the_first_step_follows_the_wheel_speed_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, 0.04, 0.04)
        self.assertEqual(receipt["status"], "completed")
        observation = receipt["output"]["observation"]
        # max_acceleration * dt = 0.4 * 0.1 = 0.04 (planning_multi_robot_env.py:35-37,222-229), and with
        # equal wheel speeds the pose moves straight (planning_multi_robot_env.py:184-188).
        self.assertEqual(observation["vR"]["values"][0], 0.04)
        self.assertEqual(observation["vL"]["values"][0], 0.04)
        self.assertEqual(observation["theta"]["values"][0], 0.0)
        position = observation["robot_positions"]["values"][0]
        self.assertAlmostEqual(position[0], -4.5 + 0.04 * 0.1, places=12)
        self.assertAlmostEqual(position[1], -2.0, places=12)
        self.assertEqual(receipt["output"]["tick"], 1)

    def test_a_wheel_speed_is_clamped_to_the_acceleration_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, 0.5, 0.5)
        self.assertEqual(receipt["status"], "completed")
        self.assertAlmostEqual(receipt["output"]["observation"]["vR"]["values"][0], 0.04, places=12)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                      # a fresh world for each run
            self.assertEqual(self.reset(client, seed=seed)["status"], "completed")
            observations = []
            for right, left in ((0.04, 0.04), (0.04, 0.0), (-0.04, 0.04)):
                receipt = self.step(client, right, left)
                self.assertEqual(receipt["status"], "completed")
                observations.append(receipt["output"]["observation"])
            return observations

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_observation_has_the_space_shape(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=5)["output"]["observation"]
        self.assertEqual(set(observation), {"vR", "vL", "theta", "robot_positions",
                                            "future_target_position", "future_obstacle_positions"})
        for name in ("vR", "vL", "theta"):
            self.assertEqual(len(observation[name]["values"]), N_ROBOTS, name)
        self.assertEqual(len(observation["robot_positions"]["values"]), N_ROBOTS)
        self.assertTrue(all(len(row) == 2 for row in observation["robot_positions"]["values"]))
        self.assertEqual(len(observation["future_target_position"]["values"]), 2)
        # 20 barriers, one of them the target (planning_multi_robot_env.py:92-113)
        self.assertEqual(len(observation["future_obstacle_positions"]["values"]), 19)
        self.assertTrue(all(len(row) == 2 for row in observation["future_obstacle_positions"]["values"]))

    def test_ticks_advance_the_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        receipt = self.step(client, 0.0, 0.0, ticks=5)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (5, False, False))
        self.assertEqual(self.state(client)["tick"], 5)

    def test_the_reset_options_are_accepted(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=2, options={"note": "upstream ignores reset options"})
        self.assertEqual(receipt["status"], "completed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("gymnasium:PlanningMultiRobot-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (100.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0.0, 0.0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 0.0, 0.0), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                   # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

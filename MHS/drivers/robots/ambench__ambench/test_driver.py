"""Acceptance run of the AM-Bench package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Isaac Sim, Isaac Lab and
the cloned packages are not installed where the gate runs, so nothing here compares the fake with the upstream
environment.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
OBSERVATION_KEYS = ("ee_pos", "ee_quat", "ee_lin_vel", "ee_ang_vel", "base_pos", "base_quat",
                    "base_lin_vel", "base_ang_vel", "gripper_width", "button_pressed", "goal_pos")


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PressButtonCases(unittest.TestCase):
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

    def test_the_observation_has_the_eleven_members_of_the_task(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=3)["output"]["observation"]
        self.assertEqual(tuple(observation), OBSERVATION_KEYS)
        sizes = {"ee_quat": 4, "base_quat": 4, "gripper_width": 1, "button_pressed": 1}
        for name in OBSERVATION_KEYS:
            self.assertEqual(len(observation[name]["values"]), sizes.get(name, 3), name)
        # eef.py:29-35: start pose (0, 0, 1), identity quaternion, two fingers at 0.001
        self.assertEqual(observation["ee_pos"]["values"], [0.0, 0.0, 1.0])
        self.assertEqual(observation["base_pos"]["values"], [0.0, 0.0, 1.0])
        self.assertEqual(observation["ee_quat"]["values"], [1.0, 0.0, 0.0, 0.0])
        self.assertAlmostEqual(observation["gripper_width"]["values"][0], 0.002)
        self.assertEqual(observation["button_pressed"]["values"], [0.0])

    def test_the_action_space_is_eight_values(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        goal = self.reset(client, seed=1)["output"]["observation"]["goal_pos"]["values"]
        action = list(goal) + [1.0, 0.0, 0.0, 0.0, -1.0]
        self.assertEqual(self.step(client, action)["status"], "completed")
        for length in (7, 9):
            refused = self.step(client, [0.0] * length)
            self.assertEqual(refused["status"], "rejected", length)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, length)

    def test_moving_the_end_effector_to_the_button_presses_it(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=7)["output"]["observation"]
        goal = observation["goal_pos"]["values"]
        # command the absolute EE pose past the button surface (control_pipeline.py:93-95); the fake's contact rule
        # is geometric (fake.py) and the success threshold is 0.004 (press_button_env_cfg.py:170)
        action = [goal[0] + 0.01, goal[1], goal[2], 1.0, 0.0, 0.0, 0.0, -1.0]
        receipt = self.step(client, action, ticks=30)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertEqual(output["reward"], 0.0)                                  # press_button_env.py:108-110
        self.assertEqual(output["observation"]["button_pressed"]["values"], [1.0])
        # eef.py:63-65: for the free end effector the base body and the end-effector body are both ee_link
        self.assertEqual(output["observation"]["base_pos"]["values"],
                         output["observation"]["ee_pos"]["values"])
        self.assertEqual(output["observation"]["base_quat"]["values"],
                         output["observation"]["ee_quat"]["values"])
        ended = self.step(client, action)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=7)["status"], "completed")      # a reset starts the next episode

    def test_a_seed_repeats_the_placement(self) -> None:
        def run(seed):
            client = self.serve()
            observation = self.reset(client, seed=seed)["output"]["observation"]
            return observation["goal_pos"]["values"], self.step(
                client, [1.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 1.0])["output"]["state_hash"]

        first = run(11)
        self.assertEqual(run(11), first)
        self.assertNotEqual(run(12)[1], first[1])
        self.assertTrue(all(-0.5 <= value <= 2.5 for value in first[0]), first[0])   # within the jitter bounds

    def test_a_zero_action_presses_nothing_and_truncates_at_the_episode_length(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        receipt = self.step(client, [0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 1.0], ticks=2400)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # 20 s episode_length_s at 1/120 s per step (press_button_env_cfg.py:104, base_env_cfg.py:46-52)
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 2400))
        self.assertEqual(output["observation"]["button_pressed"]["values"], [0.0])

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        second = self.reset(client, seed=21)["output"]
        self.assertEqual(first["observation"], second["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "isaaclab:PressButton-Am-EE-Abs-PID-Direct-v0")
        self.assertEqual(fidelity["fidelity_level"], "F1")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 120.0, places=9)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)
        self.assertTrue(any("kinematic" in gap for gap in fidelity["gaps"]))

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        self.assertEqual(self.step(client, [0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 1.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0, 1.0]),
                        self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced

    def test_a_quaternion_with_zero_norm_falls_back_to_identity(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        output = self.step(client, [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0])["output"]
        self.assertEqual(output["observation"]["ee_quat"]["values"], [1.0, 0.0, 0.0, 0.0])
        self.assertTrue(all(math.isfinite(value) for value in output["observation"]["ee_lin_vel"]["values"]))

    def test_the_envelope_is_the_action_schema(self) -> None:
        client = self.serve()
        self.reset(client, seed=6)
        # the action Box is unbounded (the clone declares only the dimension, base_env_cfg.py:47), so any finite
        # eight-value action is accepted and the array length is the only bound
        self.assertEqual(self.step(client, [1e3, -1e3, 1.0, 1.0, 0.0, 0.0, 0.0, -0.5])["status"], "completed")
        refused = self.step(client, [0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0])
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertNotEqual(refused["error"]["mhs_code"], ENVELOPE)


if __name__ == "__main__":
    unittest.main()

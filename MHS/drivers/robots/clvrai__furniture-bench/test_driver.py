"""Acceptance run of the FurnitureSim package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): the upstream package needs Isaac Gym, CUDA and Python < 3.9, so nothing
here compares the fake with the real Isaac Gym environment.  Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_ACTION = [0.0] * 8


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FurnitureSimCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        for values in ([2.0] + [0.0] * 7, [-2.0] + [0.0] * 7):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    def test_the_observation_has_the_default_visual_keys(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=1)["output"]["observation"]
        self.assertEqual(sorted(observation), ["color_image1", "color_image2", "robot_state"])
        self.assertEqual(sorted(observation["robot_state"]),
                         ["ee_ori_vel", "ee_pos", "ee_pos_vel", "ee_quat", "gripper_width"])
        self.assertEqual(len(observation["robot_state"]["ee_pos"]["values"]), 3)
        self.assertEqual(len(observation["robot_state"]["ee_quat"]["values"]), 4)
        self.assertEqual(len(observation["robot_state"]["gripper_width"]["values"]), 1)
        # the fake uses 2 x 2 x 3 placeholders; the real configured sizes are 224 x 224 or 1280 x 720
        image = observation["color_image1"]["values"]
        self.assertEqual(len(image), 2)
        self.assertEqual(len(image[0]), 2)
        self.assertEqual(len(image[0][0]), 3)

    def test_the_position_part_of_the_action_moves_the_end_effector(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=3)["output"]["observation"]["robot_state"]["ee_pos"]["values"]
        receipt = self.step(client, [0.1, 0.0, -0.05, 0.0, 0.0, 0.0, 0.0, -1.0])
        self.assertEqual(receipt["status"], "completed")
        after = receipt["output"]["observation"]["robot_state"]["ee_pos"]["values"]
        self.assertAlmostEqual(after[0], before[0] + 0.1, places=7)
        self.assertAlmostEqual(after[1], before[1], places=7)
        self.assertAlmostEqual(after[2], before[2] - 0.05, places=7)
        self.assertEqual((receipt["output"]["reward"], receipt["output"]["tick"]), (0.0, 1))

    def test_a_negative_gripper_value_opens_and_a_positive_one_closes(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        opened = self.step(client, [0.0] * 7 + [-1.0])["output"]["observation"]["robot_state"]["gripper_width"]["values"]
        closed = self.step(client, [0.0] * 7 + [1.0])["output"]["observation"]["robot_state"]["gripper_width"]["values"]
        self.assertEqual(opened, [0.065])
        self.assertEqual(closed, [0.0])

    def test_the_episode_ends_after_3001_steps(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        # max_env_steps defaults to 3000 and _done compares env_steps > max_env_steps
        receipt = self.step(client, ZERO_ACTION, ticks=3001)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 3001))
        ended = self.step(client, ZERO_ACTION)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_seed_repeats_the_initial_pose(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]["observation"]
        self.assertEqual(self.reset(client, seed=11)["output"]["observation"], first)
        self.assertNotEqual(self.reset(client, seed=12)["output"]["observation"], first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        hello = client.hello()["devices"][0]
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(hello["risk_class"], "R0")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("furniture_bench:FurnitureSim-v0 (fake kinematic stand-in)", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (100.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

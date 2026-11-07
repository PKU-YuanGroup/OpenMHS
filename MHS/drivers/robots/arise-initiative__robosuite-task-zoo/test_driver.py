"""Acceptance run of the robosuite Task Zoo package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): robosuite, mujoco-py,
numpy, numba and scipy are not installed where the gate runs, so nothing here compares the fake with the upstream
environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class HammerPlaceCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": {"values": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_reset_returns_the_observation_and_the_recorded_seed(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=7)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["seed"], 7)
        self.assertIsInstance(output["observation"], dict)
        # the keys the clone's get_state_vector reads (hammer_place.py:530-533)
        for key in ("robot0_eef_pos", "robot0_eef_quat", "robot0_gripper_qpos", "robot0_joint_pos"):
            self.assertIn(key, output["observation"])
        state = self.state(client)
        self.assertEqual((state["tick"], state["seed"], state["episode"]), (0, 7, 1))

    def test_a_step_advances_the_environment_and_returns_a_state_hash(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        before = self.state(client)["observation"]["robot0_eef_pos"]
        receipt = self.step(client, [1.0, 0.0, 0.0, -1.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["reward"], output["terminated"], output["truncated"], output["tick"]),
                         (0.0, False, False, 1))
        self.assertTrue(output["state_hash"].startswith("sha256:"))
        after = output["observation"]["robot0_eef_pos"]
        self.assertNotEqual(after, before)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_ticks_repeat_the_action_and_accumulate_the_reward(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        receipt = self.step(client, [0.5, -0.5, 0.0, 0.0], ticks=3)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 3)
        self.assertEqual(receipt["output"]["reward"], 0.0)
        self.assertEqual(self.state(client)["tick"], 3)

    def test_an_empty_action_vector_is_refused(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        receipt = self.step(client, [])
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 0)       # the refused step changed nothing

    def test_reset_options_are_accepted(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5, options={"unused": True})["status"], "completed")

    def test_a_seed_is_recorded_but_does_not_steer_the_fake(self) -> None:
        # The clone exposes no seed method and the reset takes no seed (hammer_place.py:443-456), so the MHS seed
        # is a receipt value: the fake's fixed start state is the same for any seed.
        def trajectory(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, [1.0, 0.0, 0.0, 0.0])["output"]["state_hash"] for _ in range(3)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertEqual(trajectory(12), first)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "robosuite:HammerPlaceEnv")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertEqual(fidelity["determinism"]["seed_control"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 8)
        self.assertTrue(any("camera" in gap for gap in fidelity["gaps"]))

    def test_the_estop_latches_the_simulation_and_reset_recovers(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [1.0, 0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [1.0, 0.0, 0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertEqual(self.step(client, [0.0, 1.0, 0.0, 0.0])["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 1)


if __name__ == "__main__":
    unittest.main()

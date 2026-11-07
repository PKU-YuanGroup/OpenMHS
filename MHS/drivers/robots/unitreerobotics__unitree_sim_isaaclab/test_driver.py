"""Acceptance run of the Unitree Isaac Lab package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  Everything runs on the fake backend (fake.py); Isaac Sim, Isaac Lab
and the USD assets are not installed where the gate runs, so nothing here compares the fake with the upstream task.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
EPISODE_STEPS = 1000


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class G1Cases(unittest.TestCase):
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

    def test_the_step_advances_the_fake_and_returns_the_declared_observation(self) -> None:
        client = self.serve()
        receipt = self.step(client, [0.0, 0.0])
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        self.assertTrue(output["state_hash"].startswith("sha256:"))
        observation = output["observation"]
        self.assertEqual(sorted(observation), ["camera_image", "robot_gipper_state", "robot_joint_state"])
        # g1_29dof_state.py:152-156: 29 positions + 29 velocities + 29 torques
        self.assertEqual(len(observation["robot_joint_state"]["values"]), 87)
        # gripper_state.py:104-106: the two gripper joints
        self.assertEqual(len(observation["robot_gipper_state"]["values"]), 2)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_action_shape_is_enforced_before_the_environment_is_called(self) -> None:
        client = self.serve()
        for values in ([0.0], [0.0, 0.0, 0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, values)
        self.assertEqual(self.state(client)["tick"], 0)                       # no refused step advanced the world

    def test_a_seed_repeats_the_initial_observation_and_the_next_step(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world per run
            initial = self.reset(client, seed=seed)["output"]["observation"]
            after = self.step(client, [0.2, -0.2])["output"]["observation"]
            return initial, after

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_long_run_truncates_at_the_configured_episode_length(self) -> None:
        client = self.serve()
        receipt = self.step(client, [0.0, 0.0], ticks=EPISODE_STEPS)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        # hw_env_cfg.py:90-94 has no termination terms and hw_env_cfg.py:145 gives the 20 s episode (1000 * 20 ms)
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]),
                         (False, True, EPISODE_STEPS))
        ended = self.step(client, [0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")     # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"],
                         "isaaclab:Isaac-Move-Cylinder-G129-Dex1-Wholebody (kinematic fake)")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the gym-quadruped package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): mujoco, numpy, scipy and
gymnasium are not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ZERO_ACTION = [0.0] * 12
ONE_ACTION = [1.0] * 12


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class QuadrupedCases(unittest.TestCase):
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

    @staticmethod
    def joints(observation, name):
        return observation[name]["values"]

    def test_the_action_is_one_torque_per_actuator(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        completed = self.step(client, ZERO_ACTION)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 1)
        for values in (ZERO_ACTION[:-1], ZERO_ACTION + [0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", len(values))
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, len(values))
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    def test_a_torque_changes_the_joint_state(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=2)["output"]["observation"]
        receipt = self.step(client, ONE_ACTION)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["reward"], output["terminated"], output["truncated"], output["tick"]),
                         (0.0, False, False, 1))
        after = output["observation"]
        before_qvel = self.joints(before, "qvel")[6:]
        after_qvel = self.joints(after, "qvel")[6:]
        for old, new in zip(before_qvel, after_qvel):
            self.assertAlmostEqual(new, old + 0.002, places=12)   # one fake step adds torque * 0.002 s
        self.assertAlmostEqual(self.joints(after, "qpos")[7],
                               self.joints(before, "qpos")[7] + after_qvel[0] * 0.002, places=12)
        self.assertEqual(self.joints(after, "tau_ctrl_setpoint")[6:], ONE_ACTION[6:])
        self.assertEqual(self.state(client)["observation"]["qvel"]["values"][6:], after_qvel)

    def test_the_observation_has_the_default_names_and_lengths(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=3)["output"]["observation"]
        expected = {
            "qpos": 19,
            "qvel": 18,
            "tau_ctrl_setpoint": 12,
            "feet_pos:base": 12,
            "feet_vel:base": 12,
        }
        self.assertEqual(sorted(observation), sorted(expected))
        for name, length in expected.items():
            self.assertEqual(len(self.joints(observation, name)), length, name)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"] for action in (ONE_ACTION, ZERO_ACTION)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_reset_options_set_the_position_sweep(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=4, options={"angle_sweep": 0.0})["output"]["observation"]
        self.assertEqual(self.joints(observation, "qpos")[7:], [0.0] * 12)
        spread = self.reset(client, seed=4)["output"]["observation"]
        self.assertNotEqual(self.joints(spread, "qpos")[7:], [0.0] * 12)

    def test_a_reset_starts_a_new_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 1)
        reset = self.reset(client, seed=5)
        self.assertEqual(reset["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["tick"], state["episode"], state["seed"]), (0, 2, 5))
        self.assertEqual((state["terminated"], state["truncated"]), (False, False))

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("mujoco:gym_quadruped.QuadrupedEnv(go2, flat)", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (2.0, 0, "lockstep"))
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

"""Acceptance run of the G1 tracking package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Isaac Sim, Isaac Lab and
the upstream environment are not installed where the gate runs, so nothing here compares the fake with an upstream
run.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"

#: The flat layout of the fake observation (fake.py): command, anchor position, anchor orientation prefix, base linear
#: velocity, base angular velocity, joint positions, joint velocities, last action.  Test data, not a fact.
JOINTS = 29
JOINT_POS_START = 2 * JOINTS + 3 + 6 + 3 + 3
JOINT_VEL_START = JOINT_POS_START + JOINTS
ACTION_START = JOINT_VEL_START + JOINTS
OBSERVATION_SIZE = 5 * JOINTS + 15
#: One control step of the stand-in: 4 simulation steps of 0.005 s (tracking_env_cfg.py:312-315).
CONTROL_STEP_S = 0.02
MAX_EPISODE_STEPS = 500


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class TrackingCases(unittest.TestCase):
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

    def step(self, client, values, ticks=1, **fields):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values}, **fields},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    @staticmethod
    def zeros():
        return [0.0] * JOINTS

    def test_the_action_space_is_a_29_element_array(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.step(client, self.zeros())["status"], "completed")
        # the bridge derives the array length from the action space; no bound is declared because the clone states none
        for values in ([], [0.0] * (JOINTS - 1), [0.0] * (JOINTS + 1)):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", len(values))
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, len(values))
        self.assertEqual(self.state(client)["tick"], 1)              # the refused steps changed nothing

    def test_a_step_integrates_the_action_and_updates_the_observation(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=3)["output"]["observation"]["values"]
        self.assertEqual(len(before), OBSERVATION_SIZE)
        receipt = self.step(client, [1.0] * JOINTS)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        after = output["observation"]["values"]
        # fake.py: the joint velocity is the action (gain 1) and the joint position moves by 0.02 s times it
        for index in range(JOINTS):
            self.assertAlmostEqual(after[JOINT_POS_START + index], before[JOINT_POS_START + index] + CONTROL_STEP_S,
                                   places=7)
            self.assertEqual(after[JOINT_VEL_START + index], 1.0)
            self.assertEqual(after[ACTION_START + index], 1.0)
        self.assertEqual((output["reward"], output["terminated"], output["truncated"], output["tick"]),
                         (0.0, False, False, 1))

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()
            first = self.reset(client, seed=seed)["output"]
            self.assertEqual(first["seed"], seed)
            second = self.step(client, [0.5] * JOINTS)["output"]
            return first["observation"], second["observation"], second["state_hash"]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_episode_truncates_at_500_control_steps(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        output = None
        for expected_tick in range(1, MAX_EPISODE_STEPS + 1):
            receipt = self.step(client, self.zeros())
            self.assertEqual(receipt["status"], "completed", expected_tick)
            output = receipt["output"]
            self.assertEqual(output["tick"], expected_tick)
        # tracking_env_cfg.py:313 declares 10.0 s and :312-315 gives the 0.02 s control step: 500 steps
        self.assertEqual((output["terminated"], output["truncated"]), (False, True))
        ended = self.step(client, self.zeros())
        self.assertEqual(ended["error"]["mhs_code"], PRECONDITION)
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_action_values_are_unbounded_but_the_array_length_is_enforced(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        # the clone states no action bound (only the unitless action scale of g1.py:184-195), so a large value is in
        # range; the array structure still comes from the action space
        receipt = self.step(client, [1000.0] * JOINTS)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self.step(client, [0.0] * 2)["error"]["mhs_code"], INPUT_INVALID)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("isaaclab:Tracking-Flat-G1-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 8)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, self.zeros())["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, self.zeros()), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)              # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

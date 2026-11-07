"""Acceptance run of the go2_omniverse package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Isaac Sim, Isaac Lab,
gymnasium and torch are not installed where the gate runs, so nothing here compares the fake with the upstream task.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
N_JOINTS = 12
SCAN_POINTS = 17 * 11
OBSERVATION_SIZE = 3 + 3 + 3 + 3 + N_JOINTS + N_JOINTS + N_JOINTS + SCAN_POINTS
ZERO_ACTION = [0.0] * N_JOINTS


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Go2Cases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": list(values)}}, **self.ids)

    def policy(self, receipt):
        return receipt["output"]["observation"]["policy"]["values"]

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_a_step_returns_the_policy_observation(self) -> None:
        client = self.serve()
        receipt = self.step(client, ZERO_ACTION)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        values = self.policy(receipt)
        self.assertEqual(len(values), OBSERVATION_SIZE)
        self.assertTrue(all(math.isfinite(value) for value in values), values)
        self.assertEqual(values[12:24], [0.0] * N_JOINTS)   # joint_pos of the zero action
        self.assertEqual(values[36:48], [0.0] * N_JOINTS)  # last action
        self.assertEqual(output["reward"], 0.0)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_action_is_the_joint_position_offset_and_is_kept(self) -> None:
        client = self.serve()
        action = [0.1 * index for index in range(N_JOINTS)]
        values = self.policy(self.step(client, action))
        # custom_rl_env.py:167-186 keeps the term order: base terms, joint_pos, joint_vel, actions, height_scan.
        self.assertEqual(values[12:24], [0.25 * value for value in action])  # custom_rl_env.py:330
        self.assertEqual(values[36:48], action)                              # the last_action term
        scan = values[48:48 + SCAN_POINTS]
        self.assertEqual(len(scan), SCAN_POINTS)
        self.assertTrue(all(-1.0 <= value <= 1.0 for value in scan), scan)   # custom_rl_env.py:181

    def test_the_action_width_is_the_space(self) -> None:
        client = self.serve()
        refused = self.step(client, [0.0] * (N_JOINTS + 1))
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")  # the refused call changed nothing

    def test_a_seed_repeats_the_fake_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.policy(self.step(client, action))
                    for action in ([0.1] * N_JOINTS, [-0.2] * N_JOINTS, [0.3] * N_JOINTS)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_twenty_second_time_out_truncates(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, ZERO_ACTION, ticks=1000)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # 20.0 s at 0.02 s per policy step (custom_rl_env.py:296-300, :298); the fake does not model illegal contact.
        self.assertEqual((output["truncated"], output["terminated"], output["tick"]), (True, False, 1000))
        ended = self.step(client, ZERO_ACTION)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")

    def test_reset_options_are_accepted(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=2, options={"unused": True})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 2)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("gymnasium:Isaac-Velocity-Rough-Unitree-Go2-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["timestep_ms"], 20.0)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_action_space_has_no_invented_bound(self) -> None:
        client = self.serve()
        # The clone states no numeric action bound, so the fake publishes an unbounded Box and a finite action is
        # accepted; the schema still fixes the 12-value width.
        self.assertEqual(self.step(client, [1.0] * N_JOINTS)["status"], "completed")
        self.assertEqual(self.step(client, [0.0] * (N_JOINTS + 1))["status"], "rejected")

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

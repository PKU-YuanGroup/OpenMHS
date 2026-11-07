"""Acceptance run of the gym-gazebo2 MARA package: the gate plus cases for this legacy Gym environment.

The cases run on the fake backend only.  Gazebo, ROS 2 and the MARA workspace are not installed where the gate
runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
#: placeholder action of the fake: six joint values inside the upstream Box(-pi, pi)
ACTION = [0.0] * 6


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MARACases(unittest.TestCase):
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

    def step(self, client, values=None, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": list(values or ACTION)}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_contract_and_fidelity_are_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["safety"]["risk_class"], "R2")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)
        capabilities = {item["capability_id"] for item in device["capabilities"]}
        self.assertEqual(capabilities, {"cap.world.step.v1", "cap.world.reset.v1", "cap.world.seed.v1"})
        step = next(item for item in device["capabilities"] if item["capability_id"] == "cap.world.step.v1")
        self.assertEqual(step["limits"]["action.values"]["min"], [-3.141592653589793] * 6)
        self.assertEqual(step["limits"]["action.values"]["max"], [3.141592653589793] * 6)
        self.assertEqual(step["limits"]["action.values"]["source"], "upstream_code")
        self.assertEqual(step["limits"]["action.values"]["ref"], "gym_gazebo2/envs/MARA/mara.py:169-172")

    def test_reset_returns_a_24_value_observation(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=3)
        self.assertEqual(receipt["status"], "completed", receipt)
        values = receipt["output"]["observation"]["values"]
        self.assertEqual(len(values), 24)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_seed_repeats_the_initial_observation(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=3)["output"]["observation"]
        self.assertEqual(self.reset(client, seed=3)["output"]["observation"], first)
        other = self.reset(client, seed=4)["output"]["observation"]
        self.assertNotEqual(other, first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_step_advances_the_tick_and_the_action_moves_the_joints(self) -> None:
        client = self.serve()
        start = self.reset(client, seed=5)["output"]["observation"]
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["reward"]), (1, -1.0))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        # Upstream actions are absolute joint-position targets (ut_mara.py:84-102): the zero action moves
        # every joint toward 0 rad, not "nowhere".
        start_joints = start["values"][:6]
        zero_joints = output["observation"]["values"][:6]
        self.assertNotEqual(zero_joints, start_joints)
        for before, after in zip(start_joints, zero_joints):
            self.assertLessEqual(abs(after), abs(before))
        moved = self.step(client, [1.0] * 6)
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"]["tick"], 2)
        moved_joints = moved["output"]["observation"]["values"][:6]
        for before, after in zip(zero_joints, moved_joints):
            self.assertGreater(after, before)                    # toward the commanded 1.0 rad
            self.assertLess(after, 1.0)
        self.assertNotEqual(moved["output"]["state_hash"], output["state_hash"])
        self.assertEqual(self.state(client)["tick"], 2)

    def test_the_action_shape_is_the_step_input_schema(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        for values in (ACTION[:-1], ACTION + [0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", len(values))
            self.assertEqual(refused["error"]["mhs_code"], INVALID, len(values))
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    def test_an_out_of_envelope_action_is_refused_before_the_native_step(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        for value in (-3.15, 3.15):
            refused = self.step(client, [value] * 6)
            self.assertEqual(refused["status"], "rejected", value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_legacy_done_flag_ends_the_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, ticks=1024)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 1024))
        ended = self.step(client)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_seed_repeats_a_short_trajectory(self) -> None:
        actions = ([1.0] * 6, ACTION, [0.5] * 6)

        def trajectory(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["status"], "completed")
            return [self.step(client, action)["output"]["state_hash"] for action in actions]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

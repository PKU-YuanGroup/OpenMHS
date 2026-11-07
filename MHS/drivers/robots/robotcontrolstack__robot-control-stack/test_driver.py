"""Acceptance run of the Robot Control Stack package: the gate plus cases for the rcs/fr3 environment.

Add cases, never remove the ``check_driver`` call.  The cases run on the package's fake backend (``fake.py``): the
upstream MuJoCo environment is not installed and is never imported by this package.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ZERO_TQUAT = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]     # a level, unrotated pose (test input)
SMALL_MOVE = [0.05, -0.02, 0.0, 1.0, 0.0, 0.0, 0.0]  # test input inside the 0.5 m translation box
POSITIVE_W = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]    # test input: quaternion scalar 1


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Fr3Cases(unittest.TestCase):
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

    def step(self, client, tquat=None, gripper=1.0, ticks=1):
        return client.invoke(
            "cap.world.step.v1",
            {"ticks": ticks, "action": {"right": {"tquat": list(tquat or ZERO_TQUAT), "gripper": [gripper]}}},
            **self.ids,
        )

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def observation(self, client):
        return self.state(client)["observation"]["right"]

    def test_the_action_space_bounds_every_element(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, POSITIVE_W)["status"], "completed")
        refused_tquat = self.step(client, [0.6, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
        self.assertEqual(refused_tquat["status"], "rejected")
        self.assertEqual(refused_tquat["error"]["mhs_code"], ENVELOPE)
        refused_gripper = self.step(client, POSITIVE_W, gripper=1.5)
        self.assertEqual(refused_gripper["status"], "rejected")
        self.assertEqual(refused_gripper["error"]["mhs_code"], ENVELOPE)
        refused_quaternion = self.step(client, [0.0, 0.0, 0.0, 1.0, 2.0, 0.0, 0.0])
        self.assertEqual(refused_quaternion["status"], "rejected")
        self.assertEqual(refused_quaternion["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 1)  # the refused steps changed nothing

    def test_a_relative_move_changes_the_observation(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=2)["output"]["observation"]["right"]
        receipt = self.step(client, SMALL_MOVE, gripper=0.0)
        self.assertEqual(receipt["status"], "completed")
        right = receipt["output"]["observation"]["right"]
        self.assertAlmostEqual(right["tquat"]["values"][0], first["tquat"]["values"][0] + SMALL_MOVE[0], places=9)
        self.assertAlmostEqual(right["tquat"]["values"][1], first["tquat"]["values"][1] + SMALL_MOVE[1], places=9)
        self.assertEqual(right["gripper"]["values"], [0.0])
        self.assertEqual(receipt["output"]["tick"], 1)
        self.assertEqual(self.step(client, POSITIVE_W, gripper=1.0)["output"]["observation"]["right"]["gripper"]["values"],
                         [1.0])

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["status"], "completed")
            return [self.step(client, action)["output"]["state_hash"]
                    for action in (SMALL_MOVE, POSITIVE_W, [0.01, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_ticks_advance_the_environment(self) -> None:
        client = self.serve()
        receipt = self.step(client, SMALL_MOVE, ticks=3)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 3)
        self.assertEqual(self.state(client)["tick"], 3)
        self.assertEqual((receipt["output"]["terminated"], receipt["output"]["truncated"]), (False, False))

    def test_reset_options_are_accepted(self) -> None:
        client = self.serve()
        self.step(client, SMALL_MOVE)
        receipt = self.reset(client, seed=5, options={"ignored_by_the_empty_world": True})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:rcs/fr3", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)
        self.assertTrue(any("NOT COVERED" in gap for gap in fidelity["gaps"]))

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, SMALL_MOVE)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, SMALL_MOVE), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

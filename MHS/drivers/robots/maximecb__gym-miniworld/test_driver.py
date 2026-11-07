"""Acceptance run of the MiniWorld Maze package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py); the upstream environment
is not installed where the gate runs, so nothing here compares the fake with it.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
OBS_VALUES = 3 * 4 * 3          # the fake's coarse RGB stand-in, not the real 60 x 80 x 3 image


def flatten(value):
    if isinstance(value, list):
        return [item for element in value for item in flatten(element)]
    return [value]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MazeCases(unittest.TestCase):
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

    def step(self, client, index, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"index": index}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 2)["status"], "completed")
        for index in (-1, 3):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_a_step_returns_the_world_contract(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, 2)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        self.assertEqual(output["reward"], 0.0)
        self.assertEqual(len(flatten(output["observation"]["values"])), OBS_VALUES)
        self.assertTrue(output["state_hash"].startswith("sha256:"))

    def test_a_seed_repeats_the_reset_and_the_pose(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]
        self.assertEqual(first["seed"], 11)
        self.assertEqual(self.reset(client, seed=11)["output"]["observation"], first["observation"])
        self.assertNotEqual(self.reset(client, seed=12)["output"]["observation"], first["observation"])

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_three_forward_steps_reach_the_box(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=7)["status"], "completed")
        first, second = self.step(client, 2)["output"], self.step(client, 2)["output"]
        self.assertEqual((first["terminated"], second["terminated"]), (False, False))
        third = self.step(client, 2)
        self.assertEqual(third["status"], "completed")
        output = third["output"]
        # The fake places the box 1.5 m ahead (test data) and near() accepts 1.1 m plus both radii (miniworld.py:975);
        # each forward step is 0.15 m (params.py:123), so the third step ends the episode with the sparse reward.
        self.assertEqual((output["terminated"], output["tick"]), (True, 3))
        self.assertAlmostEqual(output["reward"], 1.0 - 0.2 * (3 / 1536), places=7)
        ended = self.step(client, 2)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=7)["status"], "completed")       # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_turning_never_reaches_the_box_and_truncates_at_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        output = self.step(client, 0, ticks=1536)["output"]                     # maze.py:58: 8 * 8 * 24
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1536, False, True))
        self.assertEqual(output["reward"], 0.0)
        ended = self.step(client, 0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))

    def test_a_turn_changes_the_observation(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=5)["output"]["observation"]
        self.assertEqual(self.step(client, 0)["status"], "completed")
        self.assertNotEqual(self.state(client)["observation"], before)

    def test_the_reset_options_are_accepted(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=2, options={"unknown": 1})["status"], "completed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:MiniWorld-Maze-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 2)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 2), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

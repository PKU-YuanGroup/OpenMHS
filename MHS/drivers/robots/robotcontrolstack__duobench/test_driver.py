"""Acceptance run of the DuoBench ball_maze package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): RCS, MuJoCo and numpy are
not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
INSTRUCTION = "pick up the board and tilt it so the ball rolls onto the red square"


def action(z=0.0, gripper=1.0, left_z=None):
    """The action dict of the clone's example (scripts/gym_make.py:31-34), with zero pose deltas."""
    left = [0.0, 0.0, z if left_z is None else left_z, 0.0, 0.0, 0.0, 1.0]
    right = [0.0, 0.0, z, 0.0, 0.0, 0.0, 1.0]
    return {
        "left": {"tquat": left, "gripper": [gripper]},
        "right": {"tquat": right, "gripper": [gripper]},
    }


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class BallMazeCases(unittest.TestCase):
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

    def step(self, client, payload, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": payload}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, action())["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 1)
        for payload in (
            action(z=0.0, gripper=1.0, left_z=1.5),        # tquat above the placeholder upper bound
            action(z=-1.5),                                # tquat below the placeholder lower bound
            action(gripper=2.0),                           # gripper above its placeholder upper bound
        ):
            refused = self.step(client, payload)
            self.assertEqual(refused["status"], "rejected", payload)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, payload)
        self.assertEqual(self.state(client)["tick"], 1)     # the refused steps changed nothing

    def test_a_seed_repeats_the_reset_state(self) -> None:
        first = self.serve()
        self.assertEqual(self.reset(first, seed=7)["status"], "completed")
        first_observation = self.state(first)["observation"]
        self.assertEqual(self.reset(first, seed=7)["output"]["observation"], first_observation)
        self.assertEqual(self.reset(first, seed=8)["output"]["observation"]["values"]
                         == first_observation["values"], False)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_stage_progress_is_the_reward_and_terminates(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        lifted = self.step(client, action(z=0.30, gripper=0.0))
        self.assertEqual(lifted["status"], "completed")
        first = lifted["output"]
        self.assertEqual((first["terminated"], first["truncated"], first["tick"]), (False, False, 1))
        self.assertEqual(first["reward"], 0.5)              # stage 2 of max_stage 4 (tasks/__init__.py:41-42)
        self.assertEqual(self.state(client)["info"]["stage"], 2)

        tilted = self.step(client, action(z=0.0, gripper=0.0, left_z=0.12))
        self.assertEqual(tilted["status"], "completed")
        final = tilted["output"]
        self.assertEqual((final["terminated"], final["truncated"], final["tick"]), (True, False, 2))
        self.assertEqual(final["reward"], 1.0)              # stage 4 of max_stage 4
        info = self.state(client)["info"]
        self.assertEqual((info["success"], info["stage"], info["max_stage"]), (True, 4, 4))
        self.assertEqual(info["current_subinstruction"], "task completed; the ball has reached the goal")

        ended = self.step(client, action())
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual((self.state(client)["tick"], self.state(client)["info"]["stage"]), (0, 0))

    def test_the_info_dictionary_has_the_clone_keys(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        info = self.state(client)["info"]
        for key in ("success", "stage", "max_stage", "current_subinstruction", "stage_to_subinstructions",
                    "instruction"):
            self.assertIn(key, info)
        self.assertEqual(info["instruction"], INSTRUCTION)
        self.assertEqual(sorted(info["stage_to_subinstructions"]), ["0", "1", "2", "3", "4"])

    def test_reset_options_are_accepted(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=3, options={"unused": True})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:duobench/ball_maze", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 30.0, places=6)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, action())["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, action()), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)      # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

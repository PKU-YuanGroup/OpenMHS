"""Acceptance run of the BlindVLA package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): ManiSkill, SAPIEN and
PyTorch are not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


def action(arm=0.0, gripper=0.0):
    return {"values": [arm] * 7 + [gripper]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class EmptyV1Cases(unittest.TestCase):
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

    def step(self, client, arm=0.0, gripper=0.0, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action(arm, gripper)}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_only_bound(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, arm=1.0, gripper=-1.0)["status"], "completed")
        self.assertEqual(self.step(client, arm=-1.0, gripper=1.0)["status"], "completed")
        for arm, gripper in ((-1.01, 0.0), (1.01, 0.0), (0.0, -1.01), (0.0, 1.01)):
            refused = self.step(client, arm=arm, gripper=gripper)
            self.assertEqual(refused["status"], "rejected", (arm, gripper))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (arm, gripper))
        self.assertEqual(self.state(client)["tick"], 2)              # the refused steps changed nothing

    def test_a_step_moves_the_joints_kinematically(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, arm=0.5, gripper=0.2)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        values = output["observation"]["values"]
        self.assertEqual(len(values), 18)                            # nine qpos + nine qvel
        self.assertEqual(values[:7], [0.05] * 7)                     # 0.5 scaled to -0.1 .. 0.1
        self.assertEqual(values[7:9], [0.02, 0.02])                 # 0.2 scaled to -0.01 .. 0.04, one mimic target
        self.assertEqual(values[9:], [0.0] * 9)                      # the fake clears qvel
        self.assertEqual((output["reward"], output["terminated"], output["truncated"], output["tick"]),
                         (0.0, False, False, 1))

    def test_the_controllers_scale_the_action(self) -> None:
        client = self.serve()
        values = [1.0, -1.0, 0.5, -0.5, 0.25, 0.0, 0.0, 1.0]
        output = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"values": values}}, **self.ids)["output"]
        arm = [0.1, -0.1, 0.05, -0.05, 0.025, 0.0, 0.0]                 # 0.1 per unit: the arm joint deltas
        self.assertEqual(output["observation"]["values"][:9], arm + [0.04, 0.04])
        # The gripper value is a target, not a delta: -1 and 0 set -0.01 and 0.015 whatever came before.
        for gripper, target in ((-1.0, -0.01), (0.0, 0.015), (0.0, 0.015)):
            qpos = self.step(client, gripper=gripper)["output"]["observation"]["values"]
            self.assertAlmostEqual(qpos[7], target, places=12)
            self.assertAlmostEqual(qpos[8], target, places=12)
            self.assertEqual(qpos[:7], arm)                              # a zero arm value adds nothing

    def test_ticks_advance_without_a_terminal_state(self) -> None:
        client = self.serve()
        output = self.step(client, arm=0.25, ticks=4)["output"]
        self.assertEqual(output["tick"], 4)
        self.assertEqual(output["observation"]["values"][:7], [0.1] * 7)   # four deltas of 0.025
        self.assertEqual((output["terminated"], output["truncated"], output["reward"]), (False, False, 0.0))

    def test_a_reset_starts_the_next_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, arm=0.05)["output"]["tick"], 1)
        reset = self.reset(client, seed=7)
        self.assertEqual(reset["status"], "completed")
        self.assertEqual(reset["output"]["seed"], 7)
        self.assertEqual(reset["output"]["observation"]["values"], [0.0] * 18)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        self.assertEqual(self.reset(client)["output"]["seed"], 21)

    def test_the_state_hash_changes_with_a_step(self) -> None:
        client = self.serve()
        first = self.step(client, arm=0.01)
        second = self.step(client, arm=0.02)
        self.assertNotEqual(first["output"]["state_hash"], second["output"]["state_hash"])
        self.assertEqual(self.state(client)["tick"], 2)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("analytic:Empty-v1", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, arm=0.5)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, arm=0.5), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        state = self.state(client)
        self.assertEqual(state["tick"], 1)                           # readable, and not advanced
        self.assertEqual(state["observation"]["values"][:7], [0.05] * 7)


if __name__ == "__main__":
    unittest.main()

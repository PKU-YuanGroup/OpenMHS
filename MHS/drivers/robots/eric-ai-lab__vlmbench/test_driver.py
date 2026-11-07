"""Acceptance run of the VLMbench package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  Every case runs on the fake backend (fake.py): the upstream environment
needs CoppeliaSim 4.1.0 and PyRep (README.md:20) and is neither installed nor imported here, so nothing compares the
fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
#: The fake's step interval: the clone's module constant _DT = 0.05 (amsolver/task_environment.py:27).
DT = 0.05
ACTION = [0.0] * 8


def action(*values):
    """An 8-element action: 7 arm joint velocities and the gripper value (vlmbench_env.py:40-41)."""
    padded = list(values) + [0.0] * (8 - len(values))
    return {"values": padded}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class VLMBenchCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action(*values)}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.step(client, [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0])["status"], "completed")
        for values in ([1.5] + [0.0] * 7, [-1.5] + [0.0] * 7):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        short = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"values": [0.0] * 7}}, **self.ids)
        self.assertEqual(short["status"], "rejected")
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    def test_the_first_step_integrates_the_joints(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=5)["output"]["observation"]["values"]
        self.assertEqual(len(before), 29)
        values = [1.0, -0.5, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0]
        receipt = self.step(client, values)
        self.assertEqual(receipt["status"], "completed")
        after = receipt["output"]["observation"]["values"]
        # observation.py:72-84 order: gripper_open, velocities (7), positions (7), forces (7), gripper pose (7)
        self.assertEqual(after[0], 0.0)                                    # task_environment.py:251-254
        for index, velocity in enumerate(values[:7]):
            self.assertAlmostEqual(after[1 + index], velocity, places=12)
            self.assertAlmostEqual(after[8 + index], before[8 + index] + DT * velocity, places=12)
            self.assertEqual(after[15 + index], 0.0)                       # the kinematic model has no forces
        self.assertAlmostEqual(after[22], after[8], places=12)             # pose = first three positions
        self.assertEqual(after[23:29], [after[9], after[10], 0.0, 0.0, 0.0, 1.0])
        self.assertEqual((receipt["output"]["reward"], receipt["output"]["terminated"],
                          receipt["output"]["truncated"]), (0.0, False, False))

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, [0.5, -0.5, 0.25, 0.0, 0.0, 0.0, 0.0, 1.0])["output"]["state_hash"]
                    for _ in range(3)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        other = self.serve()
        self.assertEqual(self.reset(other, seed=21)["output"]["observation"], first["observation"])

    def test_a_gripper_command_opens_and_closes(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        opened = self.step(client, [0.0] * 7 + [1.0])
        self.assertEqual(opened["output"]["observation"]["values"][0], 1.0)
        closed = self.step(client, [0.0] * 7 + [0.0])
        self.assertEqual(closed["output"]["observation"]["values"][0], 0.0)
        kept = self.step(client, [0.0] * 7 + [0.5])                # task_environment.py:251-254
        self.assertEqual(kept["output"]["observation"]["values"][0], 0.0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("gymnasium:drop_pen_color-state-v0 (AMSolver/CoppeliaSim)", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 8)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * 8), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)            # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the RLBench package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): RLBench itself needs
CoppeliaSim and PyRep and is not installed or imported here, so nothing compares the fake with a real run.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_ACTION = [0.0] * 8


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RLBenchCases(unittest.TestCase):
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

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        for values in ([0.11] + ZERO_ACTION[1:], ZERO_ACTION[:7] + [-0.01]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                  # the refused steps changed nothing

    def test_the_kinematic_step_moves_the_joints(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=5)["output"]["observation"]
        positions = before["joint_positions"]["values"]
        receipt = self.step(client, [0.1] * 7 + [0.04])
        self.assertEqual(receipt["status"], "completed")
        after = receipt["output"]["observation"]
        for old, new in zip(positions, after["joint_positions"]["values"]):
            self.assertAlmostEqual(new, old + 0.1, places=9)
        self.assertEqual(after["gripper_joint_positions"]["values"], [0.04, 0.04])
        self.assertEqual(after["gripper_open"]["values"], [1.0])
        self.assertEqual((receipt["output"]["reward"], receipt["output"]["tick"]), (0.0, 1))

    def test_a_seed_repeats_the_initial_state(self) -> None:
        def observation(seed):
            client = self.serve()                                  # a fresh endpoint: the state hash counts episodes
            output = self.reset(client, seed=seed)["output"]
            self.assertEqual(output["seed"], seed)
            return output["observation"]

        first = observation(11)
        self.assertEqual(observation(11), first)
        self.assertNotEqual(observation(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_reaching_the_target_terminates_the_episode(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=3)["output"]["observation"]
        output = None
        for _ in range(20):
            tip = observation["gripper_pose"]["values"][:3]
            target = observation["task_low_dim_state"]["values"]
            if math.dist(tip, target) < 0.05:                        # the fake's success radius (placeholder)
                break
            action = [max(-0.1, min(0.1, goal - now)) for goal, now in zip(target, tip)]
            receipt = self.step(client, action + [0.0] * 5)
            self.assertEqual(receipt["status"], "completed", receipt)
            output = receipt["output"]
            observation = output["observation"]
        self.assertIsNotNone(output)
        self.assertTrue(output["terminated"])
        self.assertEqual(output["reward"], 1.0)
        ended = self.step(client, ZERO_ACTION)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("rlbench:reach_target-state-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

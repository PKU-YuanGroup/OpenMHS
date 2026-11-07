"""Acceptance run of the UR5TaskSpaceEnv-v0 package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream ROS/Gazebo
environment is not installed where the gate runs and package code never imports or runs the clone, so nothing here
compares the fake with the upstream simulator.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ZERO = [0.0, 0.0, 0.0]
# ur5_task_space.py:190: a unit action is 0.001 m of end-effector translation.
TRANSLATION = 0.001
# task_space.yaml:7: agent_control_dt is 0.005 s.
DT = 0.005


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class UR5TaskSpaceCases(unittest.TestCase):
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
    def observation(state):
        return state["observation"]["values"]

    def test_the_action_box_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        for values in ([1.5, 0.0, 0.0], [0.0, -1.5, 0.0], [0.0, 0.0, 1.5]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        for values in ([0.0, 0.0], [0.0, 0.0, 0.0, 0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, values)
        self.assertEqual(self.state(client)["tick"], 1)                   # the refused steps changed nothing

    def test_a_unit_action_is_0_001_m_of_translation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        started = self.observation(self.state(client))
        self.assertEqual(started[6:9], ZERO)                              # the fake's start position (placeholder)
        receipt = self.step(client, [1.0, -0.5, 0.25])
        self.assertEqual(receipt["status"], "completed")
        after = self.observation(self.state(client))
        self.assertEqual(after[6:9], [TRANSLATION, -0.5 * TRANSLATION, 0.25 * TRANSLATION])
        self.assertEqual(after[26:29], [TRANSLATION / DT, -0.5 * TRANSLATION / DT, 0.25 * TRANSLATION / DT])
        distance = math.sqrt(sum((after[13 + index] - after[6 + index]) ** 2 for index in range(3)))
        self.assertAlmostEqual(receipt["output"]["reward"], -distance * 1000.0, places=9)
        self.assertFalse(receipt["output"]["terminated"])

    def test_reaching_the_target_terminates_with_reward_100(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=7)["status"], "completed")
        output = None
        for _ in range(100):
            state = self.state(client)
            values = self.observation(state)
            position, target = values[6:9], values[13:16]
            action = [max(-1.0, min(1.0, (target[index] - position[index]) / TRANSLATION))
                      for index in range(3)]
            receipt = self.step(client, action)
            self.assertEqual(receipt["status"], "completed")
            output = receipt["output"]
            if output["terminated"]:
                break
        self.assertTrue(output["terminated"])
        self.assertEqual((output["reward"], output["truncated"]), (100.0, False))
        ended = self.step(client, ZERO)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=7)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_upstream_step_count_truncates_after_200_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=11)["status"], "completed")
        receipt = self.step(client, ZERO, ticks=201)
        output = receipt["output"]
        # robot_env.py:76 sets truncated when step_count >= 200 before incrementing it.
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 201))
        ended = self.step(client, ZERO)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.state(client)["tick"], 201)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["status"], "completed")
            return [self.step(client, [0.2, -0.1, 0.05])["output"]["state_hash"] for _ in range(4)]

        first = trajectory(31)
        self.assertEqual(trajectory(31), first)
        self.assertNotEqual(trajectory(32), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        second = self.reset(client, seed=21)["output"]
        self.assertEqual(second["observation"], first["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("analytic", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (5.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                   # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

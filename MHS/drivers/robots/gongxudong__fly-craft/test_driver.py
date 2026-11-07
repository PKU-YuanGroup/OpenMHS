"""Acceptance run of the FlyCraft package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py).  The upstream environment needs platform-specific compiled libraries
and was never imported or run here, so nothing here compares the fake with it.
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

OBSERVATION_LOW = [-180.0, -90.0, -180.0, 0.0, -90.0, -180.0, -300.0, 0.0]
OBSERVATION_HIGH = [180.0, 90.0, 180.0, 1000.0, 90.0, 180.0, 300.0, 20000.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FlyCraftCases(unittest.TestCase):
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

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.5])["status"], "completed")
        for values in ([181.0, 0.0, 0.5], [-181.0, 0.0, 0.5], [0.0, 10.0, 0.5],
                       [0.0, 0.0, -0.1], [0.0, 0.0, 1.1]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                  # the refused steps changed nothing

    def test_a_reset_publishes_the_three_part_observation(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=11)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 11)
        observation = receipt["output"]["observation"]
        self.assertEqual(sorted(observation), ["achieved_goal", "desired_goal", "observation"])
        state = observation["observation"]["values"]
        goal = observation["desired_goal"]["values"]
        self.assertEqual((len(state), len(goal)), (8, 3))
        self.assertEqual(observation["achieved_goal"]["values"], state[3:6])  # [v, mu, chi]
        for value, low, high in zip(state, OBSERVATION_LOW, OBSERVATION_HIGH):
            self.assertGreaterEqual(value, low)
            self.assertLessEqual(value, high)
        for value, low, high in zip(goal, [0.0, -90.0, -180.0], [1000.0, 90.0, 180.0]):
            self.assertGreaterEqual(value, low)
            self.assertLessEqual(value, high)

    def test_a_step_updates_the_achieved_goal_and_keeps_the_desired_goal(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=5)["output"]["observation"]
        receipt = self.step(client, [10.0, 1.0, 0.5])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        observation = output["observation"]
        self.assertEqual(output["tick"], 1)
        self.assertTrue(math.isfinite(output["reward"]))
        self.assertEqual(observation["desired_goal"], first["desired_goal"])
        self.assertEqual(observation["achieved_goal"]["values"], observation["observation"]["values"][3:6])
        self.assertNotEqual(observation["achieved_goal"], first["achieved_goal"])

    def test_a_seed_repeats_the_goal_draw(self) -> None:
        def goal(seed):
            client = self.serve()                                    # a fresh world: the fake keeps its RNG
            return self.reset(client, seed=seed)["output"]["observation"]["desired_goal"]["values"]

        first = goal(7)
        self.assertEqual(goal(7), first)
        self.assertNotEqual(goal(8), first)

    def test_the_timeout_truncates_at_the_default_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=0)["status"], "completed")
        receipt = self.step(client, [0.0, 0.0, 0.0], ticks=400)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # max_episode_steps = max_simulate_time * step_frequence = 40 * 10; the timeout termination fires at
        # step_cnt >= max_episode_steps - 1 and reports both terminated and truncated
        # (termination_base.py:106-107, timeout_termination.py:22-26)
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (399, True, True))
        ended = self.step(client, [0.0, 0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "flycraft:analytic-stand-in (F16 flight model absent)")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (100.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

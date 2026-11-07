"""Acceptance run of the CaT Solo12 package: the gate, plus cases for this driver's interface.

Add cases, never remove the ``check_driver`` call.  The cases run on the fake backend (``fake.py``); Isaac Lab, Isaac
Sim and the upstream environment are not installed where the gate runs, so nothing here compares the fake with
upstream.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ACTION = [0.1] * 12


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Solo12Cases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def step(self, client, values=None, ticks=1):
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": {"values": list(ACTION if values is None else values)}},
                             **self.ids)

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_reset_returns_the_policy_observation_and_a_seed(self) -> None:
        client = self.serve()
        receipt = self.reset(client)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 0)
        policy = receipt["output"]["observation"]["policy"]
        self.assertEqual(len(policy), 45)
        state = self.state(client)
        self.assertEqual((state["tick"], state["episode"]), (0, 1))
        self.assertEqual((state["terminated"], state["timed_out"]), (False, False))

    def test_a_supplied_seed_is_echoed_but_the_reset_stays_deterministic(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=7)["output"]["seed"], 7)
        first = self.reset(client)["output"]["observation"]
        second = self.reset(client)["output"]["observation"]
        self.assertEqual(first, second)

    def test_a_step_advances_the_joint_and_the_tick(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, ticks=1)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        # The fake moves the first joint-position action by STEP_DELTA: the policy vector's member 9 is the first
        # joint position (three base values, three commands, three gravity values before it).
        self.assertAlmostEqual(output["observation"]["policy"][9], 0.001, places=9)
        state = self.state(client)
        self.assertEqual(state["tick"], 1)
        self.assertEqual(state["reward"], output["reward"])

    def test_the_constraint_probability_is_not_a_termination_flag(self) -> None:
        client = self.serve()
        self.reset(client)
        self.step(client)
        state = self.state(client)
        self.assertEqual(state["constraint_probability"], 0.0)
        self.assertEqual((state["terminated"], state["timed_out"]), (False, False))

    def test_ticks_apply_the_action_once_per_tick(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, ticks=3)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 3)
        self.assertAlmostEqual(self.state(client)["observation"]["policy"][9], 0.003, places=9)

    def test_the_action_needs_twelve_values(self) -> None:
        client = self.serve()
        self.reset(client)
        for values in ([0.0] * 11, [0.0] * 13, []):
            refused = self.step(client, values=values)
            self.assertEqual(refused["status"], "rejected", len(values))
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, len(values))
        missing = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {}}, **self.ids)
        self.assertEqual(missing["status"], "rejected")
        self.assertEqual(missing["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_time_out_ends_the_episode(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, ticks=500)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"]), (False, True))
        self.assertEqual(output["tick"], 500)
        ended = self.step(client)
        self.assertEqual(ended["status"], "failed")
        self.assertEqual(ended["error"]["mhs_code"], PRECONDITION)
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_ticks_outside_the_class_bound_are_refused(self) -> None:
        client = self.serve()
        self.reset(client)
        for ticks in (0, 10001):
            refused = self.step(client, ticks=ticks)
            self.assertEqual(refused["status"], "rejected", ticks)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, ticks)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.reset(client)
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        state = self.state(client)
        self.assertEqual(state["tick"], 1)
        self.assertEqual(len(state["observation"]["policy"]), 45)


if __name__ == "__main__":
    unittest.main()

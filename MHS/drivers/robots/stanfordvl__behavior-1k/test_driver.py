"""Acceptance run of the BEHAVIOR-1K package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (``fake.py``): the upstream OmniGibson environment needs Isaac Sim on an NVIDIA RTX
GPU (``docs/getting_started/installation.md:9-10``) and was never imported or run, so nothing here compares the fake
with it.  The wire action of this environment is ``{"robot": [q0, q1]}``: the action space is a Dict of robot name to
robot action space (``OmniGibson/omnigibson/envs/env_base.py:429``), and the fake reduces the robot to two
position-controlled joints.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ZERO_ACTION = {"robot": [0.0, 0.0]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Behavior1KCases(unittest.TestCase):
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

    def step(self, client, action, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_a_step_applies_the_position_command(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["output"]["observation"],
                         {"robot": {"proprio": {"values": [0.0, 0.0]}}})
        receipt = self.step(client, {"robot": [0.25, -0.5]})
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # the fake models a null position controller: the commanded joint positions are the observed positions
        self.assertEqual(output["observation"], {"robot": {"proprio": {"values": [0.25, -0.5]}}})
        self.assertEqual((output["reward"], output["terminated"], output["truncated"], output["tick"]),
                         (0.0, False, False, 1))

    def test_the_ticks_advance_one_transition_each(self) -> None:
        client = self.serve()
        receipt = self.step(client, {"robot": [0.5, 0.5]}, ticks=4)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 4)
        self.assertEqual(self.state(client)["tick"], 4)
        self.assertEqual(self.state(client)["observation"],
                         {"robot": {"proprio": {"values": [0.5, 0.5]}}})

    def test_the_per_element_action_bounds_are_enforced(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, {"robot": [0.0, 0.0]})["status"], "completed")
        # the fake's placeholder bounds are -1.0 to 1.0 per element; each element is refused on its own
        for action in ({"robot": [1.5, 0.0]}, {"robot": [0.0, -1.5]}):
            refused = self.step(client, action)
            self.assertEqual(refused["status"], "rejected", action)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, action)
        # a wrong length is a schema error, not an envelope violation
        for action in ({"robot": [0.0]}, {"robot": [0.0, 0.0, 0.0]}):
            refused = self.step(client, action)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, action)
        self.assertEqual(self.state(client)["tick"], 1)               # the refused steps changed nothing

    def test_reset_starts_a_new_episode_from_the_default_pose(self) -> None:
        client = self.serve()
        self.step(client, {"robot": [0.75, -0.25]}, ticks=2)
        receipt = self.reset(client, seed=5)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 5)
        self.assertEqual(receipt["output"]["observation"],
                         {"robot": {"proprio": {"values": [0.0, 0.0]}}})
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_seed_class_sets_the_next_reset_seed(self) -> None:
        client = self.serve()
        seed_receipt = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual((seed_receipt["status"], seed_receipt["output"]),
                         ("completed", {"seed": 21, "accepted": True}))
        self.assertEqual(self.reset(client)["output"]["seed"], 21)
        # the environment echoes the seed but does not read it: reset declares no seed parameter
        # (env_base.py:838), so two seeds start from the same pose; the fidelity declares no determinism
        first = self.reset(client, seed=5)["output"]["observation"]
        self.assertEqual(self.reset(client, seed=9)["output"]["observation"], first)

    def test_the_default_task_does_not_terminate(self) -> None:
        client = self.serve()
        receipt = self.step(client, ZERO_ACTION, ticks=20)
        output = receipt["output"]
        # DummyTask creates no termination condition and no reward function (dummy_task.py:15-21)
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, False, 20))
        self.assertEqual(output["reward"], 0.0)
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:OmniGibson-fake", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 30.0, places=9)
        self.assertGreaterEqual(len(fidelity["gaps"]), 7)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, {"robot": [0.25, 0.25]})["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                # readable, and not advanced
        self.assertEqual(self.state(client)["observation"],
                         {"robot": {"proprio": {"values": [0.25, 0.25]}}})


if __name__ == "__main__":
    unittest.main()

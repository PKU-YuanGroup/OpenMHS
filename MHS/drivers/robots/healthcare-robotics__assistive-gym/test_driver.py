"""Acceptance run of the Assistive Gym HumanTesting package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): PyBullet and the
upstream assets are not installed where the gate runs, so nothing here compares the fake with the upstream
environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_ACTION = [0.0] * 20


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class HumanTestingCases(unittest.TestCase):
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

    def step(self, client, values=None, ticks=1):
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": {"values": ZERO_ACTION if values is None else values}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_twenty_human_arm_joints(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 1)
        too_high = list(ZERO_ACTION)
        too_high[3] = 1.5
        for values in (too_high, ZERO_ACTION[:19], ZERO_ACTION + [0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", len(values))
        self.assertEqual(self.step(client, too_high)["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 1)                      # the refused steps changed nothing

    def test_reset_and_step_expose_the_empty_observation(self) -> None:
        client = self.serve()
        reset = self.reset(client, seed=9)
        self.assertEqual(reset["status"], "completed")
        self.assertEqual(reset["output"]["seed"], 9)
        self.assertEqual(reset["output"]["observation"], {"values": []})
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["observation"], {"values": []})
        self.assertEqual((output["reward"], output["terminated"], output["truncated"], output["tick"]),
                         (0.0, False, False, 1))
        self.assertEqual(self.state(client)["observation"], {"values": []})

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual((accepted["status"], accepted["output"]["accepted"]), ("completed", True))
        self.assertEqual(self.reset(client)["output"]["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], {"values": []})

    def test_the_200_step_time_limit_truncates(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, ticks=200)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # assistive_gym/__init__.py:22-26: HumanTesting-v1 is registered with max_episode_steps=200.
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (200, False, True))
        ended = self.step(client)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("pybullet:assistive_gym:HumanTesting-v1", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (100.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                      # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

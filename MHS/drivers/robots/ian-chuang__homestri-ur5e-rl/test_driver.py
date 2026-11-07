"""Acceptance run of the homestri-ur5e-rl package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): gymnasium,
gymnasium-robotics and mujoco are not installed where the gate runs, so nothing here compares the fake with the
upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ZERO = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class BaseRobotCases(unittest.TestCase):
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
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        for values in ([1.5] + ZERO[1:], [-1.5] + ZERO[1:]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 0)                 # the refused steps changed nothing
        self.assertEqual(self.step(client, ZERO)["status"], "completed")

    def test_step_moves_the_stand_in_state_and_the_read_agrees(self) -> None:
        client = self.serve()
        start = self.reset(client, seed=5)["output"]["observation"]["values"]
        self.assertEqual(len(start), 28)
        values = [0.5, -0.25, 0.0, 0.0, 0.0, 0.0, 0.1]
        receipt = self.step(client, values)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["reward"], output["terminated"], output["truncated"], output["tick"]),
                         (0.0, False, False, 1))
        observation = output["observation"]["values"]
        self.assertEqual(len(observation), 28)
        self.assertAlmostEqual(observation[0], start[0] + 0.5 * 0.08, places=9)
        self.assertAlmostEqual(observation[7], 0.5, places=9)            # the velocity is the applied value
        self.assertAlmostEqual(observation[8], -0.25, places=9)
        self.assertAlmostEqual(observation[1], start[1] - 0.25 * 0.08, places=9)
        self.assertAlmostEqual(observation[2], start[2], places=9)       # a zero action did not move joint 2
        world = self.state(client)
        self.assertEqual(world["observation"], output["observation"])
        self.assertEqual((world["reward"], world["tick"]), (0.0, 1))

    def test_a_seed_repeats_the_start_state(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]
        second = self.reset(client, seed=11)["output"]
        self.assertEqual(first["seed"], 11)
        self.assertEqual(first["observation"], second["observation"])
        other = self.reset(client, seed=12)["output"]
        self.assertNotEqual(first["observation"], other["observation"])

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        seeded = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(seeded["status"], "completed")
        self.assertEqual(seeded["output"], {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:BaseRobot-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (80.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                 # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

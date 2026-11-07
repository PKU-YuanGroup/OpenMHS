"""Acceptance run of the gripper-env-v0 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream package
needs gym 0.19.0, pybullet 3.2.5 and tensorflow 1.14.0 (setup.py:6-24) and is not installed where the gate runs, so
nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
OPEN = [0.0, 0.0, 0.0, 0.0, 0.0]
CLOSE = [0.0, 0.0, 0.0, 0.0, -1.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class GripperEnvCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, OPEN)["status"], "completed")
        for values in ([1.5, 0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0, -2.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_the_observation_stand_in_has_depth_and_actuator_channels(self) -> None:
        client = self.serve()
        response = self.reset(client, seed=3)
        self.assertEqual(response["status"], "completed")
        observation = response["output"]["observation"]["values"]
        # The real space is 64 x 64 x 2 (tests_gripper/test_sim.py:39-40); the fake returns 8 x 8 x 2.
        self.assertEqual((len(observation), len(observation[0]), len(observation[0][0])), (8, 8, 2))
        self.assertTrue(all(0.0 <= pixel[0] <= 255.0 for row in observation for pixel in row))
        self.assertEqual(observation[0][0][1], 1.0)                              # the gripper starts open
        receipt = self.step(client, CLOSE)
        self.assertEqual(receipt["status"], "completed")
        closed = receipt["output"]["observation"]["values"]
        self.assertEqual(closed[0][0][1], 0.0)                                   # the close action reaches the fake

    def test_translation_changes_the_depth_channel(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=1)["output"]["observation"]["values"]
        receipt = self.step(client, [1.0, 0.0, 0.0, 0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        after = receipt["output"]["observation"]["values"]
        self.assertNotEqual(before, after)
        self.assertEqual(receipt["output"]["tick"], 1)

    def test_a_seed_repeats_the_start_state(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=5)["output"]
        second = self.reset(client, seed=5)["output"]
        self.assertEqual(first["seed"], 5)
        self.assertEqual(first["observation"], second["observation"])
        self.assertNotEqual(self.reset(client, seed=6)["output"]["observation"], first["observation"])

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(first["observation"], self.reset(client, seed=21)["output"]["observation"])

    def test_an_episode_ends_at_the_time_horizon(self) -> None:
        client = self.serve()
        receipt = self.step(client, OPEN, ticks=150)                            # fake horizon, not a device bound
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual((receipt["output"]["terminated"], receipt["output"]["tick"]), (True, 150))
        ended = self.step(client, OPEN)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("analytic", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 240.0, places=9)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertTrue(any("64 x 64 x 2" in gap for gap in fidelity["gaps"]), fidelity["gaps"])
        self.assertTrue(any("8 x 8 x 2" in gap for gap in fidelity["gaps"]), fidelity["gaps"])

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, OPEN)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, OPEN), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the racecar_gym package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream package
needs pybullet, numpy and a first-use track download, so nothing here compares the fake with the upstream model.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
FAULTED = "MHS.DEVICE.FAULTED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RacecarCases(unittest.TestCase):
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

    def step(self, client, motor=0.0, steering=0.0, ticks=1):
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": {"motor": [motor], "steering": [steering]}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, motor=1.0)["status"], "completed")
        for motor, steering in ((2.0, 0.0), (-2.0, 0.0), (0.0, 1.5), (0.0, -1.5)):
            refused = self.step(client, motor=motor, steering=steering)
            self.assertEqual(refused["status"], "rejected", (motor, steering))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (motor, steering))
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    def test_reset_returns_the_sensor_observation(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=7)
        self.assertEqual(receipt["status"], "completed")
        observation = receipt["output"]["observation"]
        self.assertEqual(sorted(observation), ["acceleration", "lidar", "pose", "time", "velocity"])
        self.assertEqual(len(observation["pose"]["values"]), 6)
        self.assertEqual(len(observation["velocity"]["values"]), 6)
        self.assertEqual(len(observation["acceleration"]["values"]), 6)
        # the real lidar has 1080 rays (models/vehicles/racecar/racecar.yml:55); the fake keeps that length
        self.assertEqual(len(observation["lidar"]["values"]), 1080)
        self.assertEqual(receipt["output"]["seed"], 7)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_step_advances_time_and_pays_progress(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, motor=1.0, steering=0.5)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertFalse(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertGreater(output["reward"], 0.0)
        self.assertRegex(output["state_hash"], r"^sha256:[0-9a-f]{64}$")
        # the fake advances one 10 ms placeholder step per tick
        self.assertAlmostEqual(output["observation"]["time"]["values"][0], 0.02, places=9)
        self.assertEqual(self.state(client)["tick"], 1)
        self.assertGreater(self.state(client)["reward"], 0.0)

    def test_a_seed_repeats_a_fresh_episode(self) -> None:
        def trajectory(seed):
            client = self.serve()
            self.reset(client, seed=seed)
            return [self.step(client, motor=action)["output"]["state_hash"] for action in (1.0, 0.5, 0.0)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        first = self.reset(client)
        self.assertEqual(first["output"]["seed"], 21)
        second = self.reset(client, seed=21)
        self.assertEqual(first["output"]["observation"], second["output"]["observation"])

    def test_the_reset_mode_is_checked(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, options={"mode": "random"})["status"], "completed")
        refused = self.reset(client, options={"mode": "not-a-mode"})
        self.assertEqual(refused["status"], "failed")
        self.assertEqual(refused["error"]["mhs_code"], FAULTED)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("pybullet", "F2"))
        self.assertEqual(fidelity["determinism"]["kind"], "statistical")
        self.assertEqual(fidelity["timestep_ms"], 10.0)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

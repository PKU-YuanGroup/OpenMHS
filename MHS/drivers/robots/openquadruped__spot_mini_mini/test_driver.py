"""Acceptance run of the spot_mini_mini package: the gate, plus cases for the SpotMicroEnv-v0 driver.

The cases run on the package's fake backend (fake.py).  They check the contract the bridge derives from the fake's
spaces and the behaviour the fake implements; nothing here compares the fake with PyBullet or the upstream
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
ZERO_ACTION = [0.0] * 12


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SpotMicroCases(unittest.TestCase):
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
        for bad in (-1.5, 1.5):
            values = list(ZERO_ACTION)
            values[0] = bad
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", bad)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, bad)
        self.assertEqual(self.state(client)["tick"], 1)                  # the refused steps changed nothing

    def test_the_observation_has_the_upstream_layout(self) -> None:
        client = self.serve()
        output = self.reset(client, seed=5)["output"]
        values = output["observation"]["values"]
        self.assertEqual(len(values), 16)                                # spot.py:688-703 with contacts enabled
        self.assertTrue(all(0.0 <= value < 2.0 for value in values[8:12]), values[8:12])
        self.assertTrue(all(value in (0, 1) for value in values[12:16]), values[12:16])
        receipt = self.step(client, ZERO_ACTION)["output"]
        self.assertEqual(receipt["tick"], 1)
        self.assertEqual(len(receipt["observation"]["values"]), 16)
        self.assertEqual(receipt["reward"], 1.0)                         # the fake's placeholder reward

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                        # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, values)["output"]["state_hash"]
                    for values in (ZERO_ACTION, [1.0] + [0.0] * 11, [0.0, -1.0] + [0.0] * 10)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]
        self.assertEqual(accepted, {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_constant_tilt_ends_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        values = [1.0, 0.0, 0.0, -1.0] + [0.0] * 8
        output = self.step(client, values, ticks=50)["output"]
        # the fake integrates its placeholder tilt until is_fallen reaches the 0.55 up-vector threshold
        self.assertTrue(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertLess(output["tick"], 50)
        ended = self.step(client, values)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")  # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_registered_limit_truncates_at_1000_steps(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        output = self.step(client, ZERO_ACTION, ticks=1000)["output"]
        self.assertEqual(output["tick"], 1000)
        self.assertFalse(output["terminated"])
        self.assertTrue(output["truncated"])                             # spot_gym_env.py:50
        self.assertEqual(self.step(client, ZERO_ACTION)["error"]["mhs_code"], PRECONDITION)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["safety"]["risk_class"], "R0")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("pybullet:SpotMicroEnv-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (10.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

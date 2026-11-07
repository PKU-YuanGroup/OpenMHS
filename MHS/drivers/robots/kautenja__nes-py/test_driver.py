"""Acceptance run of the nes-py package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream package
needs its native C++ extension and a .nes ROM, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class NESPyCases(unittest.TestCase):
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

    def step(self, client, index, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"index": index}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 255)["status"], "completed")
        for index in (-1, 256):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)                 # the refused steps changed nothing

    def test_one_frame_is_advanced_per_tick(self) -> None:
        client = self.serve()
        receipt = self.step(client, 3, ticks=3)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # The base NESEnv hooks pay reward 0 and never terminate or truncate (nes_env.py:336-351); the bridge
        # counts one environment step per tick.
        self.assertEqual((output["tick"], output["reward"]), (3, 0.0))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertEqual(self.state(client)["tick"], 3)

    def test_reset_returns_the_start_frame_and_the_seed(self) -> None:
        client = self.serve()
        output = self.reset(client, seed=7)["output"]
        self.assertEqual(output["seed"], 7)
        values = output["observation"]["values"]
        self.assertEqual((len(values), len(values[0]), len(values[0][0])), (24, 32, 3))
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_seed_controls_the_next_reset(self) -> None:
        client = self.serve()
        seeded = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(seeded["output"], {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])
        # The base NESEnv passes the seed to gym.Env's RNG but resets the native emulator without it
        # (nes_env.py:278, :285), so another seed starts from the same reset frame in the fake as upstream.
        self.assertEqual(self.reset(client, seed=22)["output"]["observation"], first["observation"])

    def test_the_observation_is_a_downscaled_frame(self) -> None:
        client = self.serve()
        values = self.reset(client, seed=1)["output"]["observation"]["values"]
        flat = [channel for row in values for pixel in row for channel in pixel]
        self.assertEqual(len(flat), 24 * 32 * 3)                        # placeholder fake resolution
        self.assertTrue(all(isinstance(value, int) and 0 <= value <= 255 for value in flat), flat[:6])
        after = self.step(client, 5)["output"]["observation"]["values"]
        self.assertNotEqual(after, values)                              # a tick leaves an observable effect

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("nes-py:NESEnv", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 60.0, places=6)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                 # readable, and not advanced

    def test_the_fake_refuses_step_before_reset(self) -> None:
        driver = load_driver(HERE, backend="fake")
        self.addCleanup(driver.close)
        with self.assertRaises(ValueError):                              # nes_env.py:313-315
            driver.native.step(0)


if __name__ == "__main__":
    unittest.main()

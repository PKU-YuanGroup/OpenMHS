"""Acceptance run of the Fixedwing-Airsim package: the gate, plus cases for this driver.

The cases run on the fake backend only.  The upstream environment needs AirSim, JSBSim and a JSBSim aircraft
directory (README.md:6-10), so nothing here compares the fake with a live JSBSim/AirSim run.  Add cases, never remove
the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
IMAGE_SHAPE = (3, 8, 8)          # placeholder shape of fake.py, not an upstream fact


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FixedwingCases(unittest.TestCase):
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

    def step(self, client, heading, pitch, ticks=1):
        action = {"values": [heading, pitch]}
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 45.0, 0.0)["status"], "completed")
        self.assertEqual(self.step(client, -45.0, -30.0)["status"], "completed")
        for heading, pitch in ((45.1, 0.0), (-45.1, -10.0), (0.0, 0.1), (0.0, -30.1)):
            refused = self.step(client, heading, pitch)
            self.assertEqual(refused["status"], "rejected", (heading, pitch))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (heading, pitch))
        self.assertEqual(self.state(client)["tick"], 2)                  # the refused steps changed nothing

    def test_a_step_returns_the_placeholder_image(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, 10.0, -10.0)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        self.assertEqual(output["reward"], 0.0)
        values = output["observation"]["values"]
        self.assertEqual((len(values), len(values[0]), len(values[0][0])), IMAGE_SHAPE)
        flat = [pixel for channel in values for row in channel for pixel in row]
        self.assertTrue(all(isinstance(pixel, int) and 0 <= pixel <= 255 for pixel in flat))

    def test_the_seed_is_echoed_and_the_reset_repeats(self) -> None:
        def trajectory(seed):
            client = self.serve()                    # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, 5.0, -5.0)["output"]["state_hash"] for _ in range(3)]

        first = trajectory(21)
        self.assertEqual(trajectory(21), first)
        self.assertEqual(trajectory(22), first)      # the seed does not change the reset state (facts.md)
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"],
                         {"seed": 21, "accepted": True})
        self.assertEqual(self.reset(client)["output"]["seed"], 21)

    def test_the_airport_collision_terminates_the_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, 0.0, 0.0, ticks=50)                  # fake.py: airport collision on step 50
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 50))
        self.assertEqual(output["reward"], 1.0)
        ended = self.step(client, 0.0, 0.0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")  # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("jsbsim+airsim", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 240.0, places=9)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0.0, 0.0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 0.0, 0.0), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

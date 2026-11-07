"""Acceptance run of the iCubReach package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Gym, PyBullet and the
upstream package are not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class iCubReachCases(unittest.TestCase):
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

    def test_the_action_box_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [1.0, 0.0, 0.0])["status"], "completed")
        for values in ([1.5, 0.0, 0.0], [0.0, -2.0, 0.0], [0.0, 0.0, 2.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_a_position_action_moves_the_hand(self) -> None:
        client = self.serve()
        start = self.reset(client, seed=3)["output"]["observation"]["values"]
        receipt = self.step(client, [1.0, 0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        after = receipt["output"]["observation"]["values"]
        # icub_reach_gym_env.py:204-208: +1 * 0.005 is added to the hand x position
        self.assertAlmostEqual(after[0] - start[0], 0.005, places=9)
        self.assertEqual(after[1:3], start[1:3])
        self.assertEqual(receipt["output"]["tick"], 1)

    def test_a_downward_action_reaches_the_object(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        receipt = self.step(client, [0.0, 0.0, -1.0], ticks=30)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # the fake's object is 0.1 m below the home hand (placeholder), so the 0.005 m step reaches it in 20 ticks
        self.assertTrue(1 <= output["tick"] <= 20, output["tick"])
        self.assertTrue(output["terminated"])
        self.assertGreater(output["reward"], 1000.0)
        ended = self.step(client, [0.0, 0.0, -1.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)                           # a reset starts the next episode

    def test_a_seed_repeats_the_start(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]["observation"]
        second = self.reset(client, seed=7)["output"]["observation"]
        third = self.reset(client, seed=8)["output"]["observation"]
        self.assertEqual(first, second)
        self.assertNotEqual(first, third)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [1.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [1.0, 0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                           # readable, and not advanced

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("pybullet:iCubReach-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 240.0, places=9)
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)


if __name__ == "__main__":
    unittest.main()

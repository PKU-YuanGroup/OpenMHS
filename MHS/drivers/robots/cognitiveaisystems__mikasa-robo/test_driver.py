"""Acceptance run of the MIKASA-Robo BunchOfColors3-v0 package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream ManiSkill
stack is not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_ACTION = {"values": [0.0] * 7}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class BunchOfColors3Cases(unittest.TestCase):
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

    def step(self, client, action=None, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action or ZERO_ACTION}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, {"values": [1.0, -1.0, 0.5, 0.0, 0.0, 1.0, -1.0]})["status"], "completed")
        for values in ([2.0] + [0.0] * 6, [-2.0] + [0.0] * 6):
            refused = self.step(client, {"values": values})
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                  # the refused steps changed nothing

    def test_the_step_uses_the_documented_action_mapping(self) -> None:
        client = self.serve()
        start = self.reset(client, seed=3)["output"]["observation"]["values"]
        action = {"values": [0.5, -0.25, 1.0, 0.5, -0.5, 0.0, 1.0]}
        receipt = self.step(client, action)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        values = output["observation"]["values"]
        # docs/source/observation_space.rst:158-172: xyz maps to 0.1 m and rpy to 0.1 rad per normalized unit,
        # and the gripper command +1 maps to the open position 0.08 m (docs/source/observation_space.rst:174-176)
        self.assertAlmostEqual(values[0], start[0] + 0.05, places=7)
        self.assertAlmostEqual(values[1], start[1] - 0.025, places=7)
        self.assertAlmostEqual(values[2], start[2] + 0.1, places=7)
        self.assertAlmostEqual(values[3], 0.05, places=7)
        self.assertAlmostEqual(values[4], -0.05, places=7)
        self.assertAlmostEqual(values[5], 0.0, places=7)
        self.assertAlmostEqual(values[6], 0.08, places=7)
        self.assertEqual((output["reward"], output["tick"]), (0.0, 1))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertEqual(self.state(client)["tick"], 1)

    def test_a_seed_repeats_the_initial_pose(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]["observation"]["values"]
        self.assertEqual(self.reset(client, seed=11)["output"]["observation"]["values"], first)
        self.assertNotEqual(self.reset(client, seed=12)["output"]["observation"]["values"], first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_registered_step_limit_truncates_the_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, ticks=120)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # bunch_of_colors.py:381 registers BunchOfColors3-v0 with max_episode_steps=120
        self.assertEqual((output["truncated"], output["tick"]), (True, 120))
        ended = self.step(client)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")   # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:BunchOfColors3-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

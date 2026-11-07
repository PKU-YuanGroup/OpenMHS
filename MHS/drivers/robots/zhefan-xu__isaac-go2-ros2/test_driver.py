"""Acceptance run of the Isaac Lab Go2 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Isaac Sim, Isaac Lab,
ROS 2 and the RSL-RL checkpoint are absent where the gate runs, so nothing here compares the fake with the upstream
environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
JOINTS = 12          # placeholder, the same fake dimension as fake.py
ZERO_ACTION = [0.0] * JOINTS


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Go2Cases(unittest.TestCase):
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
        for values in ([1.5] * JOINTS, [0.0] * (JOINTS - 1) + [-1.5]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values[:1])
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    def test_step_echoes_the_action_and_advances_ticks(self) -> None:
        client = self.serve()
        receipt = self.step(client, [0.5] * JOINTS, ticks=3)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["reward"]), (3, 0.0))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        observation = output["observation"]
        self.assertEqual(observation["actions"]["values"], [0.5] * JOINTS)
        # the fake divides the scaled action by one 40 ms environment transition (go2/go2_env.py:161,164,173)
        self.assertAlmostEqual(observation["joint_vel"]["values"][0], 0.25 * 0.5 / 0.04, places=9)
        self.assertGreaterEqual(len(observation["height_scan"]["values"]), 1)

    def test_a_seed_repeats_a_reset(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]
        second = self.reset(client, seed=7)["output"]
        self.assertEqual(first["observation"], second["observation"])
        third = self.reset(client, seed=8)["output"]
        self.assertNotEqual(first["observation"], third["observation"])
        self.assertEqual((first["seed"], third["seed"]), (7, 8))

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        seeded = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual((seeded["status"], seeded["output"]["accepted"]), ("completed", True))
        pending = self.reset(client)["output"]
        self.assertEqual(pending["seed"], 21)
        explicit = self.reset(client, seed=21)["output"]
        self.assertEqual(pending["observation"], explicit["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("isaaclab:Isaac-Velocity-Rough-Unitree-Go2-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (40.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

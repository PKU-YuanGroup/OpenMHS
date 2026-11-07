"""Acceptance run of the nav-suite package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Isaac Sim, Isaac Lab and
the GPU/lfs assets are not available where the gate runs, so nothing here compares the fake with the upstream
environment.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class NavSuiteCases(unittest.TestCase):
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

    def test_the_action_is_an_unbounded_three_vector(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        refused = self.step(client, [1.0, 0.0])                       # the action space has three elements
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 1)                # the refused step changed nothing

    def test_the_planar_pose_integrates_the_velocity_command(self) -> None:
        client = self.serve()
        pose = self.reset(client, seed=3)["output"]["observation"]["values"]
        x, y, yaw = pose
        self.assertEqual((x, y), (0.0, 0.0))
        self.assertTrue(-3.0 <= yaw <= 3.0)
        receipt = self.step(client, [0.5, 0.0, 0.25])
        self.assertEqual(receipt["status"], "completed")
        # one environment step is 0.1 s (env_cfg_base.py:424-428); the fake integrates the body-frame command
        expected = [0.5 * 0.1 * math.cos(yaw), 0.5 * 0.1 * math.sin(yaw), yaw + 0.25 * 0.1]
        for got, want in zip(receipt["output"]["observation"]["values"], expected):
            self.assertAlmostEqual(got, want, places=9)
        self.assertEqual((receipt["output"]["reward"], receipt["output"]["tick"]), (0.0, 1))

    def test_ticks_advance_the_same_command(self) -> None:
        client = self.serve()
        yaw = self.reset(client, seed=9)["output"]["observation"]["values"][2]
        output = self.step(client, [0.0, 0.0, 0.0], ticks=3)["output"]
        self.assertEqual(output["tick"], 3)
        self.assertEqual(output["observation"]["values"], [0.0, 0.0, yaw])  # zero command, zero motion

    def test_a_seed_repeats_the_reset(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]["observation"]
        second = self.reset(client, seed=11)["output"]["observation"]
        other = self.reset(client, seed=12)["output"]["observation"]
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertTrue(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"])
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_episode_truncates_at_the_configured_length(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        output = self.step(client, [0.0, 0.0, 0.0], ticks=200)["output"]
        # 20 s episode (env_cfg_base.py:422) divided by the 0.1 s step (env_cfg_base.py:426) is 200 steps
        self.assertEqual((output["truncated"], output["terminated"], output["tick"]), (True, False, 200))
        ended = self.step(client, [0.0, 0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (100.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                 # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the learn2walk package: the gate, plus cases for this analytic fake.

The cases run on the fake backend only.  They exercise the environment-step interface (reset, step, seed), the
derived control envelope, the fake's deterministic seed handling, its terminal conditions and the software e-stop
latch.  Nothing here compares the fake with MuJoCo or the upstream environment, which cannot be constructed at the
pinned commit (see driver.py and RESULT.json).
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO = [0.0] * 8
ONE = [1.0] * 8
NEGATIVE_ONE = [-1.0] * 8


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MimicWalker3dCases(unittest.TestCase):
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

    def test_the_placeholder_fake_control_range_is_enforced(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        self.assertEqual(self.step(client, [300.0] * 8)["status"], "completed")
        for values in ([-300.1] + ZERO[:-1], [300.1] + ZERO[:-1]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values[0])
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 1)              # refused steps changed nothing

    def test_a_seed_repeats_the_reset_and_the_dynamics(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]["observation"]
        self.assertEqual(self.reset(client, seed=7)["output"]["observation"], first)
        other = self.reset(client, seed=8)["output"]["observation"]
        self.assertNotEqual(other, first)
        self.reset(client, seed=7)
        first_step = self.step(client, ZERO)["output"]["observation"]
        self.reset(client, seed=7)
        second_step = self.step(client, ZERO)["output"]["observation"]
        self.assertEqual(first_step, second_step)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_step_advances_one_control_period(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        first = self.step(client, ZERO)["output"]
        second = self.step(client, ZERO)["output"]
        self.assertEqual((first["tick"], second["tick"]), (1, 2))
        self.assertEqual(len(second["observation"]["values"]), 29)   # phase, speed, 13 qpos and 14 qvel values
        self.assertAlmostEqual(second["observation"]["values"][0] - first["observation"]["values"][0], 0.01, places=12)
        self.assertEqual((second["terminated"], second["truncated"]), (False, False))

    def test_an_action_changes_the_observation(self) -> None:
        client = self.serve()
        self.reset(client, seed=7)
        zero = self.step(client, ZERO)["output"]["observation"]
        self.reset(client, seed=7)
        pull = self.step(client, ONE)["output"]["observation"]
        self.assertNotEqual(zero, pull)

    def test_extreme_actions_terminate_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=7)
        receipt = self.step(client, ONE, ticks=100)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertTrue(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertLess(output["tick"], 100)                          # the fake ends at an early-termination threshold
        ended = self.step(client, ZERO)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))

    def test_the_walking_distance_terminates_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        output = self.step(client, ZERO, ticks=2000)["output"]
        self.assertTrue(output["terminated"])
        self.assertGreater(output["tick"], 1300)                      # 10.01 m at 1.5 m/s in 5 ms steps
        self.assertLess(output["tick"], 1400)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("analytic:learn2walk-walker3d", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (5.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)              # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

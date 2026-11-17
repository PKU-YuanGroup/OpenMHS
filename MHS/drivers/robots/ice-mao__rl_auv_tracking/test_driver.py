"""Acceptance run of the AUVTracking_v0 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): HoloOcean and the
upstream clone are not installed where the gate runs, so nothing here compares the fake with the upstream
environment.  The motion and reward assertions check the arithmetic of the fake's own analytic model.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"

#: WorldAuvV0's observation bounds for one target (world_auv_v0.py:61-67), repeated here for the check.
OBS_LOW = [0.0, -math.pi, -50.0, 0.0, 0.0, -math.pi]
OBS_HIGH = [600.0, math.pi, 50.0, 2.0, 4.0, math.pi]


def _angle_difference(after, before):
    """The signed smallest difference after - before, in [-pi, pi]."""
    return (after - before + math.pi) % (2 * math.pi) - math.pi


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AuvTrackingCases(unittest.TestCase):
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

    def test_the_pid_action_box_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [1.0, 1.0])["status"], "completed")
        for values in ([-1.000001, 0.0], [0.0, 1.000001]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_a_pure_yaw_action_rotates_only_the_bearing(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=5)["output"]["observation"]["values"]
        receipt = self.step(client, [0.0, 1.0])
        self.assertEqual(receipt["status"], "completed")
        after = receipt["output"]["observation"]["values"]
        self.assertAlmostEqual(after[0], before[0], places=9)                    # speed is zero: distance is kept
        # yaw += 0.5 rad/s * 0.2 s = 0.1 rad, so the target bearing decreases by 0.1 rad (fake.py, PID path)
        self.assertAlmostEqual(_angle_difference(after[1], before[1]), -0.1, places=9)

    def test_the_observation_is_the_six_element_v0_state(self) -> None:
        client = self.serve()
        values = self.reset(client, seed=2)["output"]["observation"]["values"]
        self.assertEqual(len(values), 6)
        for value, low, high in zip(values, OBS_LOW, OBS_HIGH):
            self.assertGreaterEqual(value, low)
            self.assertLessEqual(value, high)
        self.assertEqual(values[3], 1.0)                                         # the initial target is in view
        self.assertEqual((values[4], values[5]), (4.0, 0.0))                     # no obstacle: sensor_r at angle 0

    def test_a_seed_repeats_the_fake_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                                # a fresh world: state_hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            first = self.reset(client, seed=seed)["output"]["observation"]
            return first, [self.step(client, action)["output"]["state_hash"] for action in ([0.5, 0.2], [0.5, -0.2],
                                                                                            [-0.5, 0.0])]

        first_observation, first_hashes = trajectory(11)
        again_observation, again_hashes = trajectory(11)
        self.assertEqual(again_observation, first_observation)
        self.assertEqual(again_hashes, first_hashes)
        self.assertNotEqual(trajectory(12)[1], first_hashes)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_wall_collision_ends_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        receipt = self.step(client, [1.0, 0.0], ticks=400)                       # drive straight until the 100-step rule fires
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertTrue(output["terminated"], output)
        self.assertFalse(output["truncated"])
        self.assertLessEqual(output["tick"], 400)
        ended = self.step(client, [0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")      # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertTrue(fidelity["engine"].startswith("analytic"))
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

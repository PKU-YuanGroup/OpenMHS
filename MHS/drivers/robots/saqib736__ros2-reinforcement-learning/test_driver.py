"""Acceptance run of the RacingBotEnv-v0 package: the gate plus cases specific to this driver.

The cases run on the fake backend (fake.py).  The upstream environment needs ROS 2, Gazebo,
rclpy and numpy; the clone is never imported or run here, so nothing compares the fake with a
Gazebo run.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ZERO = [0.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RacingBotCases(unittest.TestCase):
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
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        for values in ([1.5, 0.0], [0.0, -1.5]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        for values in ([0.0], [0.0, 0.0, 0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, values)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_observation_has_the_upstream_sixty_beams(self) -> None:
        client = self.serve()
        output = self.reset(client, seed=2)["output"]
        values = output["observation"]["values"]
        self.assertEqual(len(values), 60)
        self.assertTrue(all(0.0 <= value <= 1.0 for value in values), values)

    def test_the_reward_terms_follow_the_upstream_formula(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        # action [0, 0] maps to linear 0.5 and angular 0; the cleared last_action is [0, 0],
        # so the first step also takes the repeat penalty: 2.5 + 0.1 - 2.0.  The fake reports the
        # commanded linear velocity where the upstream reads odometry, so these values are the
        # upstream formula applied to the fake's placeholder velocity, not a Gazebo reward.
        self.assertAlmostEqual(self.step(client, ZERO)["output"]["reward"], 0.6)
        self.assertAlmostEqual(self.step(client, ZERO)["output"]["reward"], 0.6)
        # action [0.2, 0] maps to linear 0.6 and angular 0.2: 3.0 + 0.1.
        self.assertAlmostEqual(self.step(client, [0.2, 0.0])["output"]["reward"], 3.1)
        # The same action again adds the repeat penalty.
        self.assertAlmostEqual(self.step(client, [0.2, 0.0])["output"]["reward"], 1.1)

    def test_a_full_forward_action_terminates_on_a_crash(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        output = None
        for _ in range(70):
            receipt = self.step(client, [1.0, 0.0])
            self.assertEqual(receipt["status"], "completed", receipt)
            output = receipt["output"]
            if output["terminated"]:
                break
        self.assertIsNotNone(output)
        self.assertTrue(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertLess(output["reward"], -10.0)
        ended = self.step(client, ZERO)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))

    def test_a_seed_repeats_the_trajectory(self) -> None:
        # Fake-only: the upstream reset(seed) creates np_random, which no upstream code uses, so a live
        # Gazebo run does not repeat for a repeated seed; this checks only the fake's own seeding.
        def trajectory(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["status"], "completed")
            return [self.step(client, [0.2, -0.1])["output"]["state_hash"] for _ in range(3)]

        first = trajectory(31)
        self.assertEqual(trajectory(31), first)
        self.assertNotEqual(trajectory(32), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        # Fake-only for the observation: the upstream seed does not reach the Gazebo world.
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        second = self.reset(client, seed=21)["output"]
        self.assertEqual(second["observation"], first["observation"])

    def test_the_reset_options_are_forwarded(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=5, options={"note": "ignored by the fake"})
        self.assertEqual(receipt["status"], "completed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["resources"][0]["kind"], "world.sim")
        self.assertEqual(fidelity["engine"], "analytic:kinematic scan stand-in (no Gazebo physics)")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)


if __name__ == "__main__":
    unittest.main()

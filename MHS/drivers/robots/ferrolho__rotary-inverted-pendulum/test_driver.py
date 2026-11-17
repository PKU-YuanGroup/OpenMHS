"""Acceptance run of the rotary-inverted-pendulum package: the gate plus cases for this driver.

The cases run on the fake backend (fake.py). gymnasium and mujoco were not importable where the gate ran, so
nothing here compares the fake with the upstream environment or the physical rig. The physics-timing cases use the
declared 20 physics ticks per native step and the fake's 1 ms clock.
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
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
CONTROL_TICKS = 20
MOTOR_SAFE_LIMIT_RAD = math.radians(125.0)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RotaryInvertedPendulumCases(unittest.TestCase):
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

    def step(self, client, value, ticks=CONTROL_TICKS):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": [value]}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1.0)["status"], "completed")
        for value in (-1.5, 1.5):
            refused = self.step(client, value)
            self.assertEqual(refused["status"], "rejected", value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["tick"], CONTROL_TICKS)      # the refused steps changed nothing

    def test_a_step_reports_the_physics_tick_unit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, 0.0, ticks=40)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 40)
        values = receipt["output"]["observation"]["values"]
        self.assertEqual(len(values), 24)                                # 4 frames of 6 values (line 426)
        self.assertTrue(all(isinstance(value, (int, float)) for value in values))
        self.assertNotEqual(receipt["output"]["state_hash"], "")
        # ticks is a whole number of 20-tick control periods
        refused = self.step(client, 0.0, ticks=19)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)

    def test_the_first_frame_is_the_hanging_start(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=4)["output"]["observation"]["values"]
        self.assertEqual(len(observation), 24)
        motor_pos, sin_theta, cos_theta, motor_vel, pen_vel, prev_action = observation[:6]
        self.assertLessEqual(abs(motor_pos), 0.7 * MOTOR_SAFE_LIMIT_RAD)
        self.assertLess(abs(cos_theta + 1.0), 0.002)                     # phi near 0 is hanging down
        self.assertLess(abs(sin_theta), 0.06)
        self.assertEqual((motor_vel, pen_vel, prev_action), (0.0, 0.0, 0.0))

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                       # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, value)["output"]["state_hash"] for value in (0.5, -0.25, 0.75)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_an_episode_truncates_at_the_configured_length(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        # episode_length_s 8.0 at 50 Hz is 400 control steps (line 681), so 400 * 20 physics ticks
        receipt = self.step(client, 0.0, ticks=8000)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (8000, False, True))
        ended = self.step(client, 0.0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")   # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "analytic:rotary-inverted-pendulum")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (1.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0.0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 0.0), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], CONTROL_TICKS)       # readable, and not advanced

    def test_the_fake_copies_the_action_space_of_the_entry(self) -> None:
        # The bridge derives the bound from the fake's Box; action_space_ref cites the line that defines it.
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        capabilities = device.get("capabilities") or []
        step = next(item for item in capabilities if item["capability_id"] == "cap.world.step.v1")
        values = step["input_schema"]["properties"]["action"]["properties"]["values"]
        self.assertEqual((values["minItems"], values["maxItems"]), (1, 1))
        limit = step["limits"]["action.values"]
        self.assertEqual((limit["min"], limit["max"]), ([-1.0], [1.0]))
        self.assertEqual(limit["source"], "upstream_code")
        self.assertEqual(limit["ref"], "policy/pendulum_env.py:731-733")


if __name__ == "__main__":
    unittest.main()

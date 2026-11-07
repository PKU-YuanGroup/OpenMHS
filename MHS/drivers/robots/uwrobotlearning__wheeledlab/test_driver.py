"""Acceptance run of this driver package: the gate, plus cases for the MuSHR drift fake.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream Isaac Lab task
needs Isaac Sim and a GPU, so nothing here compares the fake with it.
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
VELOCITY_SCALE = 3.0        # common/actions.py:20
CONTROL_PERIOD = 0.02       # sim.dt 0.005 * decimation 4, mushr_drift_env_cfg.py:393-394
EPISODE_STEPS = 250         # 5 s episode / 0.02 s control period, mushr_drift_env_cfg.py:396


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MushrDriftCases(unittest.TestCase):
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

    def step(self, client, throttle, steering, ticks=1):
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": {"values": [throttle, steering]}}, **self.ids)

    def observation(self, receipt):
        return receipt["output"]["observation"]["values"]

    def test_the_observation_is_the_five_concatenated_terms(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=3)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 3)
        values = self.observation(receipt)
        self.assertEqual(len(values), 14)
        # root position at the origin, no roll or pitch, no body side or vertical speed, no roll or pitch rate
        self.assertEqual((values[0], values[1], values[2]), (0.0, 0.0, 0.0))
        self.assertEqual((values[3], values[4]), (0.0, 0.0))
        self.assertEqual((values[7], values[8]), (0.0, 0.0))
        self.assertEqual((values[9], values[10]), (0.0, 0.0))
        self.assertEqual((values[12], values[13]), (0.0, 0.0))

    def test_the_first_step_uses_the_control_period_and_the_action_scale(self) -> None:
        client = self.serve()
        start = self.observation(self.reset(client, seed=2))
        yaw = start[5]
        receipt = self.step(client, 1.0, 0.0)
        self.assertEqual(receipt["status"], "completed")
        values = self.observation(receipt)
        self.assertAlmostEqual(values[0], VELOCITY_SCALE * math.cos(yaw) * CONTROL_PERIOD, places=9)
        self.assertAlmostEqual(values[1], VELOCITY_SCALE * math.sin(yaw) * CONTROL_PERIOD, places=9)
        self.assertAlmostEqual(values[5], yaw, places=9)                    # no steering: heading unchanged
        self.assertAlmostEqual(values[6], VELOCITY_SCALE, places=9)
        self.assertAlmostEqual(values[11], 0.0, places=9)
        self.assertEqual((receipt["output"]["tick"], receipt["output"]["terminated"],
                          receipt["output"]["truncated"]), (1, False, False))
        self.assertEqual((values[12], values[13]), (1.0, 0.0))

    def test_no_reverse_clamps_the_throttle_component(self) -> None:
        client = self.serve()
        start = self.observation(self.reset(client, seed=5))
        values = self.observation(self.step(client, -1.0, 0.0))
        self.assertEqual((values[0], values[1]), (start[0], start[1]))      # the car did not move
        self.assertEqual(values[6], 0.0)                                    # ackermann_actions.py:132-133

    def test_the_action_envelope_is_the_clip_range(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        for throttle, steering in ((1.5, 0.0), (-1.5, 0.0), (0.0, 1.5), (0.0, -1.5)):
            refused = self.step(client, throttle, steering)
            self.assertEqual(refused["status"], "rejected", (throttle, steering))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (throttle, steering))
        self.assertEqual(client.read("world", **self.ids)["state"]["tick"], 0)

    def test_a_seed_repeats_the_observation_sequence(self) -> None:
        client = self.serve()

        def trajectory(seed):
            self.assertEqual(self.reset(client, seed=seed)["status"], "completed")
            return [self.observation(self.step(client, throttle, steering))
                    for throttle, steering in ((0.8, 0.2), (0.5, -0.3), (1.0, 0.0))]

        self.assertEqual(trajectory(11), trajectory(11))
        self.assertNotEqual(trajectory(11), trajectory(12))

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"],
                         {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(first["observation"], self.reset(client, seed=21)["output"]["observation"])

    def test_the_episode_truncates_after_250_control_steps(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, 1.0, 0.0, ticks=EPISODE_STEPS)
        output = receipt["output"]
        self.assertEqual((receipt["status"], output["tick"]), ("completed", EPISODE_STEPS))
        self.assertEqual((output["terminated"], output["truncated"]), (False, True))
        ended = self.step(client, 1.0, 0.0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(client.read("world", **self.ids)["state"]["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertIn("isaaclab", fidelity["engine"])
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (5.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1.0, 0.0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1.0, 0.0), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(client.read("world", **self.ids)["state"]["tick"], 1)


if __name__ == "__main__":
    unittest.main()

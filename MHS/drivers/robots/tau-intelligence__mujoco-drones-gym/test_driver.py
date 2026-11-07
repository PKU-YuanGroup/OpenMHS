"""Acceptance run of the muJoCo-drones-gym HoverAviary package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  Everything here runs on the fake backend (fake.py): MuJoCo and the
upstream package are not installed where the gate runs, so nothing here compares the fake with the upstream
environment.
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
ZERO = [0.0, 0.0, 0.0, 0.0]
POSITIVE = [1.0, 1.0, 1.0, 1.0]
NEGATIVE = [-1.0, -1.0, -1.0, -1.0]
ROLL = [1.0, -1.0, 1.0, -1.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class HoverAviaryCases(unittest.TestCase):
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

    def observation(self, receipt):
        return receipt["output"]["observation"]["values"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [1.0, 0.0, 0.0, 0.0])["status"], "completed")
        for values in ([1.5, 0.0, 0.0, 0.0], [-1.5, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertIn(refused["error"]["mhs_code"], (ENVELOPE, "MHS.CAPABILITY.INPUT_INVALID"), values)
        self.assertEqual(self.state(client)["tick"], 1)                 # the refused steps changed nothing

    def test_a_zero_action_hovers_and_pays_the_dense_reward(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, ZERO)
        self.assertEqual(receipt["status"], "completed")
        # hover_aviary.py:83-88 with pos [0, 0, 0.1], target 1.0 and a zero velocity: -(0.9) - 0.1*0 - 0.05*0 - 0
        output = receipt["output"]
        self.assertEqual(output["reward"], -0.9)
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, False, 1))
        self.assertEqual(self.observation(receipt), [0.0, 0.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        self.assertEqual(self.state(client)["info"]["height_error"], 0.9)

    def test_positive_thrust_terminates_above_three_metres(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, POSITIVE, ticks=100)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # by hand with the fake gains and 1/48 s control period: altitude = 0.1 + n(n+1)/1152, which first exceeds
        # 3.0 at n = 82; the bridge stops at the terminal state and the terminal reward carries the -100 penalty
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 82))
        self.assertGreater(self.observation(receipt)[2], 3.0)
        ended = self.step(client, POSITIVE)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")  # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_negative_thrust_terminates_below_zero(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, NEGATIVE, ticks=50)
        # altitude = 0.1 - n(n+1)/1152, below 0 for the first time at n = 15
        self.assertEqual((receipt["output"]["terminated"], receipt["output"]["tick"]), (True, 15))
        self.assertLess(self.observation(receipt)[2], 0.0)

    def test_a_flip_terminates_on_the_attitude_limit(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, ROLL, ticks=100)
        # the fake's placeholder roll rate is 2 rad/s, so |roll| = n/24 passes pi/2 at n = 38
        self.assertEqual((receipt["output"]["terminated"], receipt["output"]["tick"]), (True, 38))
        self.assertGreater(abs(self.observation(receipt)[3]), math.pi / 2)

    def test_a_quiet_episode_is_truncated_at_ten_seconds(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        receipt = self.step(client, ZERO, ticks=480)
        output = receipt["output"]
        # 480 control steps of 5 physics sub-steps at 240 Hz are 10 s (hover_aviary.py:32, 113-115)
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 480))
        self.assertAlmostEqual(output["reward"], -432.0, places=6)
        self.assertEqual(self.step(client, ZERO)["error"]["mhs_code"], PRECONDITION)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, values)["output"]["state_hash"]
                    for values in (ZERO, POSITIVE, ROLL, NEGATIVE, ZERO)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertTrue(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"])
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:HoverAviary", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 240.0, places=6)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                 # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

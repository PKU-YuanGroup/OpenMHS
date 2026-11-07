"""Acceptance run of the NavGym-v0 package: the gate plus cases specific to this driver.

The cases run on the fake backend (fake.py).  The upstream environment is not opened: its constructor imports
torch, OpenCV, pyastar2d, range_libc, CMap2D and pose2d and loads a Torch policy, and package code never imports or
runs the clone.  Nothing here compares the fake with the upstream simulator.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
FORWARD = [0.5, 0.0]          # placeholder: a legal action at the max linear velocity
STOP = [0.0, 0.0]             # placeholder
SCAN_SIZE = 512               # placeholder: KetiRobot.n_angles
OBSERVATION_SIZE = 519        # placeholder: scan 512 + prev_pose 2 + pose 2 + vel 2 + yaw 1


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class NavGymCases(unittest.TestCase):
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
        return receipt["output"]["observation"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, FORWARD)["status"], "completed")
        for values in ([0.6, 0.0], [-0.1, 0.0], [0.0, 0.7], [0.0, -0.7]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)             # the refused steps changed nothing

    def test_the_reset_observation_has_the_upstream_shape(self) -> None:
        client = self.serve()
        output = self.reset(client, seed=3)["output"]
        observation = output["observation"]
        scan = observation["observation"]["values"]
        self.assertEqual(len(scan), OBSERVATION_SIZE)
        self.assertEqual(scan[:SCAN_SIZE], [25.0] * SCAN_SIZE)     # placeholder: constant max-range scan
        self.assertEqual(scan[SCAN_SIZE:SCAN_SIZE + 2], [0.0, 0.0])  # prev_pose
        self.assertEqual(scan[SCAN_SIZE + 2:SCAN_SIZE + 4], [0.0, 0.0])  # pose
        self.assertEqual(scan[SCAN_SIZE + 4:SCAN_SIZE + 6], [0.0, 0.0])  # previous action
        self.assertEqual(scan[-1], 0.0)                            # yaw
        self.assertEqual(observation["achieved_goal"]["values"], [0.0, 0.0])
        self.assertEqual(observation["desired_goal"]["values"], [10.0, 0.0])  # placeholder: fixed fake goal
        self.assertEqual(output["seed"], 3)

    def test_the_first_step_matches_the_kinematic_rule(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        receipt = self.step(client, FORWARD)
        self.assertEqual(receipt["status"], "completed")
        output = self.receipt_output(receipt)
        values = output["observation"]["observation"]["values"]
        # KetiRobot.set_vel with dt 0.2 s and linvel 0.5 m/s: x advances by 0.1 m, y and yaw stay 0.
        self.assertAlmostEqual(values[SCAN_SIZE + 2], 0.1, places=9)
        self.assertAlmostEqual(values[SCAN_SIZE + 3], 0.0, places=9)
        self.assertEqual(values[SCAN_SIZE:SCAN_SIZE + 2], [0.0, 0.0])
        self.assertEqual(values[SCAN_SIZE + 4:SCAN_SIZE + 6], [0.0, 0.0])
        self.assertAlmostEqual(values[-1], 0.0, places=9)
        self.assertAlmostEqual(output["reward"], 0.1 * 0.001 * 15.0, places=9)
        self.assertEqual((output["terminated"], output["tick"]), (False, 1))
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_goal_terminal_stops_the_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, FORWARD, ticks=120)
        output = self.receipt_output(receipt)
        # 10 m at 0.1 m per step: the 96th step brings the distance (0.4 m) below the 0.5 m threshold.
        self.assertEqual((output["terminated"], output["truncated"]), (True, False))
        self.assertEqual(output["tick"], 96)
        ended = self.step(client, STOP)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        output = self.reset(client)["output"]
        self.assertEqual(output["seed"], 21)
        # The upstream reset() takes no seed and exposes no seed() method: the fake scene is fixed, so the
        # observation repeats even though the seed is recorded by the bridge.
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], output["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic: open-space kinematic stand-in for NavGym-v0 (no crowd or map model)", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "none")
        self.assertAlmostEqual(fidelity["timestep_ms"], 200.0, places=6)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, FORWARD)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, FORWARD), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)             # readable, and not advanced

    @staticmethod
    def receipt_output(receipt):
        assert receipt["status"] == "completed", receipt
        return receipt["output"]


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the Habitat-Lab package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): habitat-lab,
habitat-sim and the legacy gym package are not installed where the gate runs, so nothing here compares the fake with
the upstream environment.
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


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class HabitatPointNavCases(unittest.TestCase):
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

    def step(self, client, index, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"index": index}}, **self.ids)

    def pointgoal(self, receipt):
        return receipt["output"]["observation"]["pointgoal_with_gps_compass"]["values"]

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        for index in (-1, 4):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_a_seed_repeats_the_episode(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)
        self.assertEqual(first["output"]["seed"], 7)
        replay = self.reset(client, seed=7)
        self.assertEqual(replay["output"], first["output"])
        self.assertNotEqual(self.reset(client, seed=8)["output"]["observation"],
                            first["output"]["observation"])

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        first = self.reset(client)
        self.assertEqual(first["output"]["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["output"]["observation"])

    def test_the_four_navigation_actions(self) -> None:
        client = self.serve()
        start = self.reset(client, seed=5)
        self.assertEqual(start["output"]["seed"], 5)
        goal = self.pointgoal(start)
        # The point goal is [distance, azimuth]; a left turn followed by a right turn restores the azimuth, while the
        # forward action moves the agent by forward_step_size 0.25 m
        # (habitat-lab/habitat/config/default_structured_configs.py:1791-1792).
        self.assertEqual(self.step(client, 2)["status"], "completed")
        restored = self.pointgoal(self.step(client, 3))
        self.assertAlmostEqual(restored[1], goal[1], places=9)
        distance = self.pointgoal(self.step(client, 1))[0]
        self.assertNotAlmostEqual(distance, goal[0], places=9)
        stopped = self.step(client, 0)
        self.assertEqual((stopped["status"], stopped["output"]["terminated"]), ("completed", True))
        self.assertEqual(self.step(client, 1)["error"]["mhs_code"], PRECONDITION)

    def test_a_stop_ends_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        stopped = self.step(client, 0)
        self.assertEqual(stopped["output"]["terminated"], True)
        self.assertEqual((stopped["output"]["tick"], stopped["output"]["reward"]), (1, 0.0))
        self.assertEqual(self.step(client, 0)["error"]["mhs_code"], PRECONDITION)
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")    # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_episode_is_capped_at_500_steps(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        # The point-nav test config sets max_episode_steps 500
        # (habitat-lab/habitat/config/benchmark/nav/pointnav/pointnav_habitat_test.yaml:10).
        long = self.step(client, 1, ticks=500)
        self.assertEqual(long["status"], "completed")
        self.assertEqual((long["output"]["terminated"], long["output"]["tick"]), (True, 500))
        self.assertEqual(self.step(client, 1)["error"]["mhs_code"], PRECONDITION)

    def test_the_depth_and_goal_spaces(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=6)["output"]["observation"]
        self.assertEqual(len(observation["rgb"]["values"]), 12)               # a 12-number stand-in for 256 x 256 x 3
        self.assertEqual(len(observation["depth"]["values"]), 4)              # a 4-number stand-in for 256 x 256 x 1
        self.assertEqual(len(observation["pointgoal_with_gps_compass"]["values"]), 2)
        self.assertTrue(all(0.0 <= value <= 10.0 for value in observation["depth"]["values"]))
        self.assertTrue(-math.pi <= observation["pointgoal_with_gps_compass"]["values"][1] <= math.pi)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("habitat-lab:gym.Habitat-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

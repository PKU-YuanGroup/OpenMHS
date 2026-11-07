"""Acceptance run of the DroneNavigation-v0 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream pybullet
environment is not installed where the gate runs and package code never imports or runs the clone, so nothing here
compares the fake with the upstream simulator.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
UP = [0.0, 0.0, 0.1]
DOWN = [0.0, 0.0, -0.1]
ZERO = [0.0, 0.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DroneNavigationV0Cases(unittest.TestCase):
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
        self.assertEqual(self.step(client, UP)["status"], "completed")
        for values in ([0.2, 0.0, 0.0], [-0.2, 0.0, 0.0], [0.0, 0.0, 0.2]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_the_observation_is_the_drone_state_and_the_goal(self) -> None:
        client = self.serve()
        output = self.reset(client, seed=3)["output"]
        values = output["observation"]["values"]
        self.assertEqual(len(values), 9)
        self.assertEqual(values[0:3], [0.0, 0.0, 0.1])                           # drone.py:12 (start position)
        self.assertEqual(values[3:6], ZERO)
        self.assertTrue(-9.0 <= values[6] <= 9.0, values)
        self.assertTrue(-9.0 <= values[7] <= 9.0, values)
        self.assertTrue(5.0 <= values[8] <= 9.0, values)                         # drone_env_v0.py:141
        self.assertEqual(output["seed"], 3)

    def test_the_first_step_matches_the_kinematic_rule(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        receipt = self.step(client, UP)
        self.assertEqual(receipt["status"], "completed")
        # semi-implicit Euler with the base link mass 0.027 kg, dt = 1/30 s and a +0.1 N push on z:
        # v = 0.1 / 0.027 * (1 / 30) = 0.12345679 m/s and z = 0.1 + v * (1 / 30) = 0.10411523 m
        x, y, z, vx, vy, vz, _gx, _gy, _gz = receipt["output"]["observation"]["values"]
        self.assertAlmostEqual(vz, 0.12345679, places=7)
        self.assertAlmostEqual(z, 0.10411523, places=7)
        self.assertEqual((x, y, vx, vy), (0.0, 0.0, 0.0, 0.0))
        self.assertGreater(receipt["output"]["reward"], 0.0)                    # moving up shortens the distance
        self.assertEqual(receipt["output"]["tick"], 1)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"]
                    for action in ([0.0, 0.0, 0.05], [0.02, 0.0, 0.0], ZERO)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_downward_push_ends_the_episode_at_the_z_bound(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, DOWN, ticks=100)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # z starts at 0.1 m and v grows by -0.12345679 m/s per step: z <= 0 on the 7th step (v0:155-157)
        self.assertEqual((output["terminated"], output["truncated"]), (True, False))
        self.assertEqual(output["tick"], 7)
        self.assertLessEqual(output["observation"]["values"][2], 0.0)
        ended = self.step(client, ZERO)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("analytic", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 30.0, places=6)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, UP)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, UP), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

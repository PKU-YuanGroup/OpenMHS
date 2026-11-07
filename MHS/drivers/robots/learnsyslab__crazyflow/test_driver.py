"""Acceptance run of the Crazyflow package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py); JAX, MuJoCo and the
upstream clone are not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"

# The default cf2x_L250 so_rpy parameters (crazyflow/dynamics/so_rpy/params.toml:22-31) and the 500 Hz step
# (crazyflow/envs/drone_env.py:69, crazyflow/sim/sim.py:293).
MASS = 0.0328
CMD_F_COEF = 1.023224599403443
GRAVITY = 9.81
DT = 1.0 / 500.0
THRUST_MIN = 0.012817578393224994 * 4.0


def values(observation, name):
    """The single world's array of an observation member (the upstream arrays keep a leading world dimension)."""
    return observation[name]["values"][0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ReachPosCases(unittest.TestCase):
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

    def step(self, client, action, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": action}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0, 0.2])["status"], "completed")
        tick = self.state(client)["tick"]
        for action in ([0.0, 0.0, 0.0, 0.9], [2.0, 0.0, 0.0, 0.2], [0.0, 0.0, 0.0, 0.0]):
            refused = self.step(client, action)
            self.assertEqual(refused["status"], "rejected", action)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, action)
        self.assertEqual(self.state(client)["tick"], tick)          # the refused steps changed nothing

    def test_a_seed_repeats_the_reset_and_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]
        second = self.reset(client, seed=7)["output"]
        self.assertEqual(first["observation"], second["observation"])
        self.assertEqual((first["seed"], second["seed"]), (7, 7))
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        seeded = self.reset(client)["output"]
        self.assertEqual(seeded["seed"], 21)
        self.assertEqual(seeded["observation"], self.reset(client, seed=21)["output"]["observation"])

    def test_reset_options_bound_the_goal(self) -> None:
        client = self.serve()
        output = self.reset(client, seed=3, options={
            "goal_pos_min": [0.2, 0.3, 0.4],
            "goal_pos_max": [0.2, 0.3, 0.4],
        })["output"]
        observation = output["observation"]
        position = values(observation, "pos")
        difference = values(observation, "difference_to_goal")
        goal = [position[i] + difference[i] for i in range(3)]
        for actual, expected in zip(goal, (0.2, 0.3, 0.4)):
            self.assertAlmostEqual(actual, expected, places=9)

    def test_a_step_matches_the_translational_model(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=5)["output"]["observation"]
        position = values(observation, "pos")
        velocity = values(observation, "vel")
        goal = [position[i] + values(observation, "difference_to_goal")[i] for i in range(3)]
        thrust = 0.2656
        receipt = self.step(client, [0.0, 0.0, 0.0, thrust])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # so_rpy translational dynamics with the zero attitude (crazyflow/dynamics/so_rpy/dynamics.py:149-155),
        # integrated by the fake with the semi-implicit Euler step.
        acceleration = CMD_F_COEF * thrust / MASS - GRAVITY
        expected_velocity = [velocity[0], velocity[1], velocity[2] + acceleration * DT]
        expected_position = [position[0] + expected_velocity[0] * DT,
                             position[1] + expected_velocity[1] * DT,
                             position[2] + expected_velocity[2] * DT]
        self.assertGreater(expected_position[2], 0.0)
        actual_position = values(output["observation"], "pos")
        actual_velocity = values(output["observation"], "vel")
        for index in range(3):
            self.assertAlmostEqual(actual_position[index], expected_position[index], places=9)
            self.assertAlmostEqual(actual_velocity[index], expected_velocity[index], places=9)
        distance = math.sqrt(sum((expected_position[i] - goal[i]) ** 2 for i in range(3)))
        self.assertAlmostEqual(output["reward"], math.exp(-2.0 * distance), places=9)
        self.assertFalse(output["terminated"])

    def test_the_episode_terminates_and_the_bridge_autorestarts(self) -> None:
        client = self.serve()
        self.reset(client, seed=9)
        # Minimum thrust: the drone falls below z=0 and the terminal state restarts the world, because DroneEnv
        # declares autoreset_mode NEXT_STEP (crazyflow/envs/drone_env.py:60) and the driver sets autoreset=True.
        receipt = self.step(client, [0.0, 0.0, 0.0, THRUST_MIN], ticks=5000)
        self.assertEqual(receipt["status"], "completed")
        self.assertGreater(self.state(client)["episode"], 1)        # more than one episode ran in the 5000 ticks
        self.assertLess(receipt["output"]["tick"], 5000)            # the tick counts since the last restart
        before = self.state(client)
        restarted = self.step(client, [0.0, 0.0, 0.0, 0.2])
        self.assertEqual(restarted["status"], "completed")
        self.assertGreaterEqual(self.state(client)["episode"], before["episode"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("crazyflow:DroneReachPos-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (2.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0, 0.2])["status"], "completed")
        tick = self.state(client)["tick"]
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0, 0.0, 0.2]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], tick)          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

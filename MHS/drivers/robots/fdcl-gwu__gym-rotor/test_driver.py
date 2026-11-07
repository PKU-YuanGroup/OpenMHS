"""Acceptance run of the gym-rotor package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): gymnasium, numpy, scipy
and the clone are not imported where the gate runs, so nothing here compares the fake with the upstream environment.
Numbers that are test data carry a comment; the constants reused from the clone cite the upstream line.
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
# Test data: with this seed the fake draws the 20% origin branch of quad.py:342-346 (x, v, roll, pitch and W zero).
ORIGIN_SEED = 4
# quad.py:59-61: 200 Hz, so one step is 0.005 s.
DT = 1.0 / 200.0


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class QuadRotorCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, seed=None, options=None):
        fields = {}
        if seed is not None:
            fields["seed"] = seed
        if options is not None:
            fields["options"] = options
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def step(self, client, values, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        for values in ([1.0, 1.0, 1.0, 1.0], [-1.0, -1.0, -1.0, -1.0], [0.0, 0.0, 0.0, 0.0]):
            self.assertEqual(self.step(client, values)["status"], "completed", values)
        tick = self.state(client)["tick"]
        for values in ([1.0001, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, -1.0001]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], tick)            # the refused steps changed nothing

    def test_the_first_step_matches_the_equations_of_motion(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=ORIGIN_SEED)["output"]["observation"]["values"]
        self.assertTrue(all(value == 0.0 for value in observation[0:6]), observation[0:6])   # the origin branch
        receipt = self.step(client, [0.0, 0.0, 0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        values = receipt["output"]["observation"]["values"]
        # By hand from quad.py:36-42, :225-229 and :321-335 with an all-zero state and a yaw-only attitude:
        # thrust = 4*avrg_act, so v_dot_z = 9.81 - thrust/m and x_dot_z = 0, with no moment and W = 0.
        mass, gravity, c_tw, min_force = 2.15, 9.81, 2.2, 0.5
        hover = mass * gravity / 4.0
        avrg_act = (min_force + c_tw * hover) / 2.0
        acceleration = gravity - 4.0 * avrg_act / mass
        self.assertAlmostEqual(values[5], acceleration * DT, places=9)
        self.assertAlmostEqual(values[2], 0.5 * acceleration * DT * DT, places=9)
        self.assertEqual(values[0:2], [0.0, 0.0])
        self.assertEqual(values[15:18], [0.0, 0.0, 0.0])            # the equal thrusts make no moment
        reward = receipt["output"]["reward"]
        self.assertTrue(math.isfinite(reward))
        self.assertLess(reward, 0.0)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        actions = ([0.2, -0.3, 0.1, 0.0], [0.0, 0.0, 0.0, 0.0], [1.0, 1.0, 1.0, 1.0])

        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"] for action in actions]

        first = trajectory(5)
        self.assertEqual(trajectory(5), first)
        self.assertNotEqual(trajectory(6), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_constant_max_thrust_ends_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, [1.0, 1.0, 1.0, 1.0], ticks=300)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertLess(output["tick"], 300)                       # the state limit, not the 10000-step limit
        ended = self.step(client, [0.0, 0.0, 0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:Quad-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (5.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0, 0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)             # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

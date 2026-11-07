"""Acceptance run of the fancy_gym package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): fancy_gym itself is not
installed where the gate runs, so nothing here compares the fake with the upstream environment.
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
STRAIGHT = {"random_start": False}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SimpleReacherCases(unittest.TestCase):
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
        self.assertEqual(self.reset(client, seed=5, options=STRAIGHT)["status"], "completed")
        self.assertEqual(self.step(client, [1000.0, 1000.0])["status"], "completed")
        for values in ([1000.0001, 0.0], [0.0, -1000.0001]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_the_first_step_integrates_the_torque(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3, options=STRAIGHT)["status"], "completed")
        receipt = self.step(client, [100.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        values = output["observation"]["values"]
        # by hand from base_reacher_torque.py:25-26 and base_reacher.py:21 with dt 0.01 and the straight start:
        # velocity = dt * 100 = 1.0 and the first angle = pi/2 + dt * 1.0; euler uses the new velocity for the angle
        self.assertEqual(len(values), 9)                                        # 3*n_links+3 with n_links=2
        self.assertAlmostEqual(values[0], math.cos(math.pi / 2 + 0.01), places=9)
        self.assertAlmostEqual(values[1], 1.0, places=9)
        self.assertAlmostEqual(values[2], math.sin(math.pi / 2 + 0.01), places=9)
        self.assertAlmostEqual(values[3], 0.0, places=9)
        self.assertAlmostEqual(values[4], 1.0, places=9)
        self.assertAlmostEqual(values[5], 0.0, places=9)
        self.assertAlmostEqual(values[8], 1.0, places=9)
        # simple_reacher.py:63-69: before steps_before_reward the reward is only -sum(action**2)
        self.assertEqual(output["reward"], -10000.0)
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, False, 1))

    def test_the_distance_reward_starts_at_step_199(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=9, options=STRAIGHT)["status"], "completed")
        self.assertEqual(self.step(client, [0.0, 0.0])["output"]["reward"], 0.0)
        receipt = self.step(client, [0.0, 0.0], ticks=199)
        self.assertEqual(receipt["status"], "completed")
        # the 200th transition is the first one whose _steps (199) reached steps_before_reward
        self.assertEqual(receipt["output"]["tick"], 200)
        self.assertLess(receipt["output"]["reward"], 0.0)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, [1.0, -2.0])["output"]["state_hash"] for _ in range(5)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_reset_option_random_start_false_uses_the_straight_arm(self) -> None:
        client = self.serve()
        values = self.reset(client, seed=2, options=STRAIGHT)["output"]["observation"]["values"]
        # base_reacher.py:34: the start is [pi/2, 0], so cos(pi/2)=0, sin(pi/2)=1, cos(0)=1 and sin(0)=0
        self.assertAlmostEqual(values[0], 0.0, places=9)
        self.assertAlmostEqual(values[1], 1.0, places=9)
        self.assertAlmostEqual(values[2], 1.0, places=9)
        self.assertAlmostEqual(values[3], 0.0, places=9)
        self.assertEqual(values[4:6], [0.0, 0.0])                              # velocity is zero after a reset
        self.assertAlmostEqual(values[8], 0.0, places=9)                       # the step count restarts at 0

    def test_the_registered_200_step_limit_truncates(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=7, options=STRAIGHT)["status"], "completed")
        receipt = self.step(client, [0.0, 0.0], ticks=200)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # fancy_gym/envs/__init__.py:42: gymnasium.make wraps the environment in a 200-step TimeLimit
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 200))
        self.assertEqual(self.step(client, [0.0, 0.0])["error"]["mhs_code"], PRECONDITION)
        self.assertEqual(self.reset(client, seed=7, options=STRAIGHT)["status"], "completed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("gymnasium:fancy/SimpleReacher-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (10.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=4, options=STRAIGHT)["status"], "completed")
        self.assertEqual(self.step(client, [1.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [1.0, 0.0]), self.reset(client, seed=4)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

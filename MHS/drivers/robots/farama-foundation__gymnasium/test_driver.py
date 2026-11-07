"""Acceptance run of the Gymnasium package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): gymnasium itself is not
installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_START = {"options": {"low": 0.0, "high": 0.0}}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CartPoleCases(unittest.TestCase):
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

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        for index in (-1, 2):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_the_first_step_matches_the_equations_of_motion(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3, **ZERO_START)["status"], "completed")
        receipt = self.step(client, 1)
        self.assertEqual(receipt["status"], "completed")
        # by hand from cartpole.py:170-190 with the zero state and the +10 push: x_dot = tau * xacc, theta_dot =
        # tau * thetaacc, xacc = 9.7561 and thetaacc = -14.6341
        x, x_dot, theta, theta_dot = receipt["output"]["observation"]["values"]
        self.assertAlmostEqual(x_dot, 0.19512195, places=7)
        self.assertAlmostEqual(theta_dot, -0.29268293, places=7)
        self.assertEqual((x, theta), (0.0, 0.0))                                 # euler: positions use the old speeds
        self.assertEqual((receipt["output"]["reward"], receipt["output"]["tick"]), (1.0, 1))

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"] for action in (1, 0, 0, 1, 1)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_constant_push_ends_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=1, **ZERO_START)
        receipt = self.step(client, 1, ticks=50)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # the steps stop at the terminal state: the pole passes 12 degrees on the 9th step (cartpole.py:199-204),
        # and every step including that one pays +1 (cartpole.py:206-221)
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 9))
        self.assertEqual(output["reward"], 9.0)
        self.assertLess(output["observation"]["values"][2], -0.2094)
        ended = self.step(client, 1)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")       # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_balanced_pole_is_truncated_at_500_steps(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=4)["output"]["observation"]["values"]
        for expected_tick in range(1, 501):
            receipt = self.step(client, 1 if observation[2] * 10 + observation[3] > 0 else 0)
            self.assertEqual(receipt["status"], "completed", expected_tick)
            output = receipt["output"]
            self.assertEqual(output["tick"], expected_tick)
            observation = output["observation"]["values"]
        # CartPole-v1 truncates at max_episode_steps=500 (gymnasium/envs/__init__.py:30), never terminates here
        self.assertEqual((output["terminated"], output["truncated"]), (False, True))
        self.assertEqual(self.step(client, 0)["error"]["mhs_code"], PRECONDITION)

    def test_the_reset_options_set_the_start_bounds(self) -> None:
        client = self.serve()
        values = self.reset(client, seed=2, options={"low": 0.2, "high": 0.3})["output"]["observation"]["values"]
        self.assertTrue(all(0.2 <= value <= 0.3 for value in values), values)
        refused = self.reset(client, options={"low": 0.3, "high": 0.2})           # utils.py:41-44
        self.assertEqual(refused["status"], "failed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:CartPole-v1", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

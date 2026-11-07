"""Acceptance run of the SocialGym-v0 package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): gymnasium, pygame, scipy and torch are not installed where the gate
runs, so nothing here compares the fake with the upstream environment.  Every case starts from a fresh server.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ZERO = [0.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SocialNavCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": list(values)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_is_the_two_number_robot_command(self) -> None:
        client = self.serve()
        receipt = self.step(client, [0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        observation = receipt["output"]["observation"]
        self.assertEqual(len(observation["values"]), 5)             # one human's ObservableState (state.py:24-30)
        refused = self.step(client, [0.0])                          # the action Box has two elements
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 1)              # the refused step changed nothing

    def test_a_seed_repeats_the_observation(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"] for action in ([0.5, 0.0], [0.0, 0.0], [0.25, 0.0])]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_one_step_advances_the_example_robot_time_step(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=3)["output"]["observation"]["values"]
        after = self.step(client, [0.5, 0.0])["output"]["observation"]["values"]
        # the human moves at 0.5 m/s for one 0.25 s robot step (env.config:4; social_nav_gym.py:240-245)
        self.assertAlmostEqual(after[0] - before[0], 0.125, places=9)
        self.assertAlmostEqual(after[1] - before[1], 0.0, places=9)

    def test_a_zero_action_is_truncated_at_the_time_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        output = self.step(client, ZERO, ticks=250)["output"]
        # the example time_limit is 50 s and the reward function truncates at time_limit-1 (env.config:2;
        # social_nav_sim.py:1004-1008); one step is 0.25 s, so the 197th step is the first at or past 49 s
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 197))
        self.assertEqual(output["reward"], 0.0)
        ended = self.step(client, ZERO)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("social_gym:SocialGym-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (250.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)              # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

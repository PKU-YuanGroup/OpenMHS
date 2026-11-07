"""Acceptance run of the OopsieVerse package: the gate, plus cases for this driver.

The cases run on the fake backend (``fake.py``).  RoboCasa, Robosuite, MuJoCo and gymnasium are not installed where
the gate runs, so nothing here compares the fake with an upstream environment or claims a hardware run.
"""

import random
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ZERO = [0.0] * 7


def _server_client():
    server = load(HERE, backend="fake")
    client = client_for(server)
    device_id = client.hello()["devices"][0]["device_id"]
    session = client.open_session(device_ids=[device_id])["session_id"]
    return server, client, {"device_id": device_id, "session_id": session}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CloseDrawerCases(unittest.TestCase):
    def serve(self):
        server, client, ids = _server_client()
        self.addCleanup(close_server, server)
        self.ids = ids
        return client

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def step(self, client, values, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_reduced_observation_members_have_the_published_sizes(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=4)["output"]["observation"]
        self.assertEqual(len(observation["robot0_eef_pos"]["values"]), 3)
        self.assertEqual(len(observation["robot0_gripper_qpos"]["values"]), 2)
        self.assertEqual(len(observation["robot0_proprio"]["values"]), 23)
        self.assertEqual(len(observation["health"]["values"]), 1)
        self.assertTrue(all(value == 100.0 for value in observation["health"]["values"]))

    def test_the_reward_is_ten_times_one_minus_the_door_state(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        # The fake samples the start door state with Python's random.Random(seed); it closes by 0.1 per unit
        # closing action (test data) and pays 10 * (1 - door state), the formula of close_drawer.py:123-129.
        start = random.Random(5).uniform(0.95, 1.0)
        receipt = self.step(client, [-1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        self.assertAlmostEqual(receipt["output"]["reward"], 10.0 * (1.0 - (start - 0.1)), places=9)

    def test_closing_the_drawer_terminates_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, [-1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], ticks=12)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertTrue(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertEqual(output["tick"], 10)                    # seed 1 starts above 0.95: the tenth close ends it
        ended = self.step(client, ZERO)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            server, client, ids = _server_client()
            try:
                self.ids = ids
                self.assertEqual(self.reset(client, seed=seed)["status"], "completed")
                return [self.step(client, [0.2, -0.1, 0.0, 0.0, 0.0, 0.0, 0.5])["output"]["state_hash"]
                        for _ in range(4)]
            finally:
                close_server(server)

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        second = self.reset(client, seed=21)["output"]
        self.assertEqual(second["observation"], first["observation"])

    def test_the_reset_options_are_forwarded(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=3, options={"note": "accepted and ignored by the fake"})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(len(receipt["output"]["observation"]["robot0_proprio"]["values"]), 23)

    def test_the_action_vector_structure_is_enforced(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        for values in ([0.0] * 6, [0.0] * 8):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, values)
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertTrue(fidelity["engine"].startswith("gymnasium:close_drawer"))
        self.assertEqual(fidelity["fidelity_level"], "F1")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

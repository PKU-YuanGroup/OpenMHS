"""Acceptance run of the QuadrotorEnvironment package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream package
needs gym and numpy-quaternion, which are not installed where the gate runs, so nothing here compares the fake with
the upstream environment.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
HOVER = [0.0, 0.0, 0.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class QuadrotorCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, [0.2, -0.1, 0.0, 0.3])["status"], "completed")
        refused = self.step(client, [1.0001, 0.0, 0.0, 0.0])
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE))
        short = self.step(client, [0.0, 0.0, 0.0])
        self.assertEqual((short["status"], short["error"]["mhs_code"]), ("rejected", INPUT_INVALID))
        self.assertEqual(self.state(client)["tick"], 1)                   # neither refusal changed the world

    def test_a_seed_repeats_the_trajectory(self) -> None:
        actions = ([0.2, -0.4, 0.1, 0.3], [-0.3, 0.0, 0.4, 0.0], [0.0, 0.0, 0.0, -0.2])

        def trajectory(seed):
            client = self.serve()                                     # a fresh world: the hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"] for action in actions]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_observation_is_the_default_eighteen_value_vector(self) -> None:
        client = self.serve()
        values = self.reset(client, seed=3)["output"]["observation"]["values"]
        # observation_mapping.py:22-25: 3 position + 3 velocity + 9 rotation-matrix + 3 angular-velocity values
        self.assertEqual(len(values), 18)
        self.assertTrue(all(math.isfinite(value) for value in values))
        matrix = values[6:15]                                            # row-major rotation matrix, :73-74
        for row in range(3):
            for column in range(3):
                dot = sum(matrix[3 * row + k] * matrix[3 * column + k] for k in range(3))
                self.assertAlmostEqual(dot, 1.0 if row == column else 0.0, places=9)

    def test_a_step_pays_the_default_reward(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        receipt = self.step(client, HOVER)
        self.assertEqual((receipt["status"], receipt["output"]["tick"]), ("completed", 1))
        # the state is random, so the negative weighted state reward is strictly negative (reward_function.py:121-129)
        self.assertLess(receipt["output"]["reward"], 0.0)
        self.assertEqual((receipt["output"]["terminated"], receipt["output"]["truncated"]), (False, False))

    def test_an_episode_ends_after_max_time(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, HOVER, ticks=1100)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # max_time 10 s / controller period 0.01 s = 1000 periods; the accumulated float time crosses 10 s on 1001
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 1001))
        ended = self.step(client, HOVER)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("custom:quadrotor_environment", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (10.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, HOVER)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, HOVER), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

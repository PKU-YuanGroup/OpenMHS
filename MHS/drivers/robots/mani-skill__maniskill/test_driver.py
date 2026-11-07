"""Acceptance run of the ManiSkill package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): the upstream SAPIEN environment is not installed where the gate runs, so
nothing here compares the kinematic stand-in with the upstream simulation.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_ACTION = [0.0] * 9


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RotateCubeCases(unittest.TestCase):
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

    def step(self, client, values=None, ticks=1):
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": {"values": list(values or ZERO_ACTION)}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.25] * 9)["status"], "completed")
        for values in ([1.5] * 9, [-1.5] * 9):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_a_step_returns_the_state_observation_and_a_normalised_reward(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=0)["status"], "completed")
        receipt = self.step(client, [0.5] * 9)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        observation = output["observation"]["values"]
        self.assertEqual(len(observation), 32)                                   # 9+9+3+4+3+4
        self.assertTrue(0.0 <= output["reward"] <= 1.0, output["reward"])
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, False, 1))

    def test_a_seed_repeats_the_reset_state(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=3)["output"]["observation"]
        second = self.reset(client, seed=3)["output"]["observation"]
        self.assertEqual(first, second)
        other = self.reset(client, seed=4)["output"]["observation"]
        self.assertNotEqual(first, other)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_episode_is_truncated_at_250_steps(self) -> None:
        client = self.serve()
        receipt = self.step(client, ticks=250)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # TriFingerRotateCubeLevel0-v1 is registered with max_episode_steps=250 (rotate_cube.py:351); the seed 0 goal
        # is far from the placeholder start, so the episode truncates before it can succeed.
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 250))
        ended = self.step(client)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=0)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertIn("TriFingerRotateCubeLevel0-v1", fidelity["engine"])
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

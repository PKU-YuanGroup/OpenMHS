"""Acceptance run of the Factor-World package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py).  MuJoCo 2.1, mujoco_py and gym are not installed where the gate runs, so
nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_ACTION = {"values": [0.0, 0.0, 0.0, 0.0]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FactorWorldCases(unittest.TestCase):
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

    def step(self, client, action=None, ticks=1):
        fields = {"ticks": ticks, "action": dict(action or ZERO_ACTION)}
        return client.invoke("cap.world.step.v1", fields, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    @staticmethod
    def proprio(receipt):
        return receipt["output"]["observation"]["proprio"]["values"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ticks=1)["status"], "completed")
        for value in (1.01, -1.01):
            action = {"values": [value, 0.0, 0.0, 0.0]}
            refused = self.step(client, action=action)
            self.assertEqual(refused["status"], "rejected", value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["tick"], 1)                # the refused steps changed nothing

    def test_a_step_reaches_the_fake_and_moves_the_hand(self) -> None:
        client = self.serve()
        start = self.proprio(self.reset(client, seed=3))
        receipt = self.step(client, action={"values": [1.0, 0.0, 0.0, 0.5]}, ticks=1)
        self.assertEqual(receipt["status"], "completed")
        values = self.proprio(receipt)
        # envs/sawyer_xyz_env.py:207-208: clip to -1..1 and move by action * action_scale (1/100)
        self.assertAlmostEqual(values[0], start[0] + 0.01, places=6)
        self.assertEqual(values[3], 0.5)                               # placeholder gripper position
        self.assertEqual(receipt["output"]["tick"], 1)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_observation_is_the_v2_39_element_shape(self) -> None:
        client = self.serve()
        reset = self.reset(client, seed=4)
        observation = reset["output"]["observation"]
        self.assertEqual(set(observation), {"image", "proprio"})
        self.assertIsNone(observation["image"]["value"])
        self.assertEqual(len(observation["proprio"]["values"]), 39)     # envs/sawyer_xyz_env.py:396
        receipt = self.step(client, ticks=2)
        self.assertEqual(len(self.proprio(receipt)), 39)
        self.assertEqual(len(self.state(client)["observation"]["proprio"]["values"]), 39)

    def test_the_reset_uses_the_legacy_seed_path(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=7)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 7)
        self.assertEqual(len(self.proprio(receipt)), 39)
        # envs/sawyer_xyz_env.py:540-542 has reset(self) with no seed, so the bridge calls seed() then reset()
        self.assertEqual(self.state(client)["seed"], 7)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        seeded = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(seeded["status"], "completed")
        self.assertEqual(seeded["output"]["accepted"], True)
        self.assertEqual(self.reset(client)["output"]["seed"], 21)

    def test_the_episode_ends_at_500_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, ticks=500)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # envs/sawyer_xyz_env.py:100 and :522: max_path_length is 500 and done is set when it is reached
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (500, True, False))
        ended = self.step(client, ticks=1)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "factor-world:assembly-v2/SawyerNutAssemblyEnvV2")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (12.5, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ticks=1)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ticks=1), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                 # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

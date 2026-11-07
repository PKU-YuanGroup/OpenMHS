"""Acceptance run of the Open Duck Mini package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the ``check_driver`` call.  The cases run on the fake backend (``fake.py``): the upstream
environment is not installed or run, so nothing here compares the fake with it.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
N_JOINTS = 13                              # placeholder: the fake's action width (see fake.py)
OBS_DIM = 41                               # env_humanoid.py:92
HEALTHY_REWARD = 5.0                       # env_humanoid.py:101
CTRL_COST_WEIGHT = 0.3                     # env_humanoid.py:100


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class OpenDuckMiniCases(unittest.TestCase):
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

    def test_a_step_returns_the_declared_observation_and_reward_shape(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, [0.0] * N_JOINTS)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        values = output["observation"]["values"]
        self.assertEqual(len(values), OBS_DIM)
        self.assertEqual(values[-2:], [1.0, 1.0])                 # left then right contact placeholder
        # env_humanoid.py:157-165 with zero controls: 5.0 - 0 - 2 * |base x velocity|; the base velocity is the
        # reset noise at observation index 20 (qpos is 20 values)
        expected = HEALTHY_REWARD - 2.0 * abs(values[20])
        self.assertAlmostEqual(output["reward"], expected, places=12)
        self.assertEqual(output["tick"], 1)
        self.assertFalse(output["terminated"])
        self.assertFalse(output["truncated"])

    def test_the_reward_uses_the_control_cost(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        values = [0.5] * N_JOINTS
        output = self.step(client, values)["output"]
        base_velocity = output["observation"]["values"][20]
        expected = HEALTHY_REWARD - CTRL_COST_WEIGHT * sum(value * value for value in values) \
            - 2.0 * abs(base_velocity)
        self.assertAlmostEqual(output["reward"], expected, places=12)
        self.assertAlmostEqual(output["reward"], 4.025 - 2.0 * abs(base_velocity), places=12)

    def test_the_action_box_is_the_envelope(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=7)["status"], "completed")
        refused = self.step(client, [2.0] + [0.0] * (N_JOINTS - 1))
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        refused = self.step(client, [-1.5] * N_JOINTS)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 0)           # the refused steps changed nothing

    def test_a_seed_repeats_the_trajectory(self) -> None:
        actions = [[0.0] * N_JOINTS, [0.25] * N_JOINTS, [-0.5] * N_JOINTS, [0.75] * N_JOINTS]

        def trajectory(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["observation"]["values"] for action in actions]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_base_stays_in_the_healthy_height_range(self) -> None:
        client = self.serve()
        self.reset(client, seed=9)
        for _ in range(20):
            output = self.step(client, [0.0] * N_JOINTS)["output"]
            z = output["observation"]["values"][2]
            self.assertTrue(0.1 < z < 0.2, z)                    # env_humanoid.py:97
            self.assertFalse(output["terminated"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:BDX_env", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)
        self.assertTrue(any("NOT COVERED" in gap for gap in fidelity["gaps"]))

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * N_JOINTS)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * N_JOINTS), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)           # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

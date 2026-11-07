"""Acceptance run of the SceneManipulation-v1 package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py).  The upstream environment is not importable where the gate runs (it needs
SAPIEN, torch, ReplicaCAD assets and a renderer), so nothing here compares the fake with the real simulation.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
N_ACTION = 13
N_OBS = 30


def action(arm=0.0, gripper=0.0, body=0.0, base_forward=0.0, base_turn=0.0):
    """A valid action of the deployed Fetch pd_joint_delta_pos configuration."""
    return [arm] * 7 + [gripper] + [body] * 3 + [base_forward, base_turn]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SceneManipulationCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return client, {"device_id": device_id, "session_id": session}

    def reset(self, client, ids, **fields):
        return client.invoke("cap.world.reset.v1", fields, **ids)

    def step(self, client, ids, values, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values}}, **ids)

    def state(self, client, ids):
        return client.read("world", **ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client, ids = self.serve()
        self.assertEqual(self.step(client, ids, action(
            arm=1.0, gripper=1.0, body=-1.0, base_forward=-1.0, base_turn=1.0))["status"], "completed")
        refused = self.step(client, ids, action(arm=1.1))
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE))
        refused = self.step(client, ids, action(base_turn=-1.1))
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE))
        self.assertEqual(self.state(client, ids)["tick"], 1)          # the refused steps changed nothing

    def test_the_observation_and_action_shapes(self) -> None:
        client, ids = self.serve()
        first = self.reset(client, ids, seed=5)
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["output"]["seed"], 5)
        self.assertEqual(len(first["output"]["observation"]["values"]), N_OBS)
        receipt = self.step(client, ids, action())
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(len(receipt["output"]["observation"]["values"]), N_OBS)
        self.assertEqual((receipt["output"]["reward"], receipt["output"]["tick"]), (0.0, 1))

    def test_a_known_action_moves_the_matching_joint(self) -> None:
        client, ids = self.serve()
        start = self.reset(client, ids, seed=3)["output"]["observation"]["values"]
        moved = self.step(client, ids, action(arm=0.1))["output"]["observation"]["values"]
        self.assertAlmostEqual(moved[0], start[0] + 0.1, places=7)
        self.assertEqual(moved[7:15], start[7:15])                    # the other joints did not move
        self.assertAlmostEqual(moved[15], 0.1, places=7)              # qvel reports the last action

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client, ids = self.serve()                                # a fresh world: the hash counts episodes
            self.assertEqual(self.reset(client, ids, seed=seed)["output"]["seed"], seed)
            return [self.step(client, ids, step)["output"]["state_hash"]
                    for step in (action(arm=0.1), action(), action(gripper=0.01), action(body=-0.1))]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client, ids = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **ids)
        self.assertEqual(accepted["status"], "completed")
        self.assertTrue(accepted["output"]["accepted"])
        first = self.reset(client, ids)["output"]
        self.assertEqual(first["seed"], 21)
        second = self.reset(client, ids, seed=21)["output"]
        self.assertEqual(second["observation"], first["observation"])

    def test_the_episode_truncates_at_200_steps(self) -> None:
        client, ids = self.serve()
        self.reset(client, ids, seed=1)
        output = self.step(client, ids, action(), ticks=200)["output"]
        # base_env.py:19 registers max_episode_steps=200; the environment itself never terminates (base_env.py:142-143)
        self.assertEqual((output["truncated"], output["terminated"], output["tick"]), (True, False, 200))
        refused = self.step(client, ids, action())
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, ids, seed=1)["status"], "completed")
        self.assertEqual(self.state(client, ids)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client, ids = self.serve()
        device = client.inspect(ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("sapien:SceneManipulation-v1", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client, ids = self.serve()
        self.assertEqual(self.step(client, ids, action())["status"], "completed")
        client.estop("test", **ids)
        for refused in (self.step(client, ids, action()), self.reset(client, ids, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client, ids)["tick"], 1)          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

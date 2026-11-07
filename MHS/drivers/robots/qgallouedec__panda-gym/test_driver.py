"""Acceptance run of the panda-gym package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): panda-gym itself is not
installed where the gate runs, so nothing here compares the fake with a PyBullet environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ZERO = [0.0, 0.0, 0.0]
# panda_gym/envs/robots/panda.py:81: one action moves the end-effector by at most 0.05.
DISPLACEMENT = 0.05


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PandaReachCases(unittest.TestCase):
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

    @staticmethod
    def value(observation, member):
        return observation[member]["values"]

    def test_the_action_box_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        for values in ([1.5, 0.0, 0.0], [0.0, -1.5, 0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        for values in ([0.0, 0.0], [0.0, 0.0, 0.0, 0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, values)
        self.assertEqual(self.state(client)["tick"], 1)                   # the refused steps changed nothing

    def test_the_sparse_reward_penalises_a_step_away_from_the_goal(self) -> None:
        client = self.serve()
        output = self.reset(client, seed=5)["output"]
        self.assertEqual(output["seed"], 5)
        receipt = self.step(client, ZERO)
        self.assertEqual(receipt["status"], "completed")
        # reach.py:59-62: -1 outside the distance_threshold and 0 inside it; seed 5 samples a goal farther away
        self.assertEqual((receipt["output"]["reward"], receipt["output"]["terminated"]), (-1.0, False))
        self.assertFalse(self.state(client)["info"]["is_success"])

    def test_reaching_the_goal_terminates_the_episode(self) -> None:
        client = self.serve()
        output = self.reset(client, seed=7)["output"]
        for _ in range(10):
            achieved = self.value(output["observation"], "achieved_goal")
            goal = self.value(output["observation"], "desired_goal")
            values = [max(-1.0, min(1.0, (g - a) / DISPLACEMENT)) for g, a in zip(goal, achieved)]
            receipt = self.step(client, values)
            self.assertEqual(receipt["status"], "completed")
            output = receipt["output"]
            if output["terminated"]:
                break
        self.assertTrue(output["terminated"])
        self.assertEqual((output["reward"], output["truncated"]), (0.0, False))
        self.assertTrue(self.state(client)["info"]["is_success"])
        ended = self.step(client, ZERO)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))

    def test_the_episode_is_truncated_at_50_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=11)["status"], "completed")
        receipt = self.step(client, ZERO, ticks=50)
        output = receipt["output"]
        # panda_gym/__init__.py:21 registers max_episode_steps=50 and gymnasium.make adds the TimeLimit wrapper
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 50))
        self.assertEqual(output["reward"], -50.0)
        ended = self.step(client, ZERO)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.state(client)["tick"], 50)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["status"], "completed")
            return [self.step(client, [0.2, -0.1, 0.05])["output"]["state_hash"] for _ in range(4)]

        first = trajectory(31)
        self.assertEqual(trajectory(31), first)
        self.assertNotEqual(trajectory(32), first)

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
        receipt = self.reset(client, seed=3, options={"note": "accepted and ignored by PandaReachEnv"})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["observation"]["observation"]["values"][3:], [0.0, 0.0, 0.0])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:PandaReach-v3", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (40.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                   # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

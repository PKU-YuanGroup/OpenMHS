"""Acceptance run of the pybullet_multigoal_gym package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream package
is not installed where the gate runs, so nothing here compares the fake with PyBullet or the real environment.
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


class KukaBlockStackCases(unittest.TestCase):
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
        action = {"values": list(values)} if values is not None else dict(ZERO_ACTION)
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_reset_returns_the_four_block_stack_members(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=5)
        self.assertEqual(receipt["status"], "completed")
        observation = receipt["output"]["observation"]
        self.assertEqual(sorted(observation), ["achieved_goal", "desired_goal", "observation", "policy_state"])
        # The arithmetic of the cited composition with num_block=5 (kuka_multi_step_base_env.py:264-283):
        # state 8 + 15*5, policy 4 + 3*5, achieved 3*5, desired 3*5.
        self.assertEqual([len(observation[name]["values"]) for name in
                          ("observation", "policy_state", "achieved_goal", "desired_goal")], [83, 19, 15, 15])
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_step_advances_one_placeholder_transition(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertEqual(len(output["observation"]["observation"]["values"]), 83)
        self.assertIsInstance(output["reward"], float)
        self.assertFalse(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        self.assertEqual(self.step(client)["status"], "completed")
        for values in ([1.1, 0.0, 0.0, 0.0], [0.0, -1.1, 0.0, 0.0], [0.0, 0.0, 0.0, 1.1]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, [0.1, -0.2, 0.0, 0.0])["output"]["state_hash"],
                    self.step(client, [0.0, 0.0, 0.2, 1.0])["output"]["state_hash"]]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_capability_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_registered_horizon_ends_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, ticks=50)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # make_env registers max_episode_steps=50 (__init__.py:6, :131); gym's TimeLimit turns it into done=True.
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 50))
        ended = self.step(client)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_reset_options_are_accepted_and_ignored(self) -> None:
        client = self.serve()
        # The legacy reset(test=False) takes no options; the bridge drops them in its legacy fallback.
        self.assertEqual(self.reset(client, options={"unused": 1})["status"], "completed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["fidelity_level"], fidelity["timestep_ms"], fidelity["realtime_factor"],
                          fidelity["clock"]), ("F0", 40.0, 0, "lockstep"))
        self.assertTrue(fidelity["engine"].startswith("pybullet:"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

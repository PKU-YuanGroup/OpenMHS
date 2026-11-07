"""Acceptance run of the gym-games package: the gate, plus cases for the NChain driver.

Keep the ``check_driver`` call: it is the package's acceptance harness.  The cases run on the fake backend
(fake.py); gymnasium, numpy and the upstream package are not installed where the gate runs, so nothing here
compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class NChainCases(unittest.TestCase):
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

    def test_the_observation_is_the_step_function_of_the_state(self) -> None:
        client = self.serve()
        initial = self.reset(client, seed=1)["output"]["observation"]["values"]
        self.assertEqual(initial, [1, 1, 0, 0, 0, 0, 0, 0, 0, 0])               # state 1 (nchain.py:31-34)
        receipt = self.step(client, 1)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["observation"]["values"],
                         [1, 1, 1, 0, 0, 0, 0, 0, 0, 0])                          # state 2
        self.assertEqual((receipt["output"]["reward"], receipt["output"]["tick"]), (0.0, 1))
        self.assertEqual(receipt["output"]["terminated"], False)

    def test_action_zero_moves_left_and_pays_the_small_reward_at_state_zero(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        receipt = self.step(client, 0, ticks=2)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # the first step leaves state 1 (reward 0), the second starts at state 0 and pays 0.001 (nchain.py:36-42)
        self.assertEqual(output["reward"], 0.001)
        self.assertEqual(output["observation"]["values"], [1, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        self.assertEqual(output["tick"], 2)

    def test_reaching_the_last_state_pays_one(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        receipt = self.step(client, 1, ticks=9)                                 # states 1 -> 9, then stay at 9
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["reward"], 1.0)
        self.assertEqual(output["observation"]["values"], [1] * 10)
        self.assertEqual((output["tick"], output["terminated"]), (9, False))

    def test_the_episode_terminates_at_n_plus_8_and_the_bridge_starts_the_next_one(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        receipt = self.step(client, 1, ticks=18)                                # max_steps = n + 8 (nchain.py:23)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 18))
        self.assertEqual(output["reward"], 10.0)                                # ten steps at state 9
        # autoreset=True: the bridge resets before the next step instead of refusing it; the upstream class
        # itself does not auto-reset (driver.py fidelity gaps).
        continued = self.step(client, 1)
        self.assertEqual(continued["status"], "completed")
        self.assertEqual((continued["output"]["tick"], continued["output"]["terminated"]), (1, False))

    def test_reset_restores_the_chain(self) -> None:
        client = self.serve()
        self.step(client, 1, ticks=4)
        self.assertEqual(self.state(client)["tick"], 4)
        receipt = self.reset(client, seed=5)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 5)
        self.assertEqual(receipt["output"]["observation"]["values"], [1, 1, 0, 0, 0, 0, 0, 0, 0, 0])
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_chain_is_deterministic_for_every_seed(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"] for action in (1, 0, 0, 1, 1)]

        # NChainEnv draws no random numbers (nchain.py:29-30), so both seeds produce the same trajectory.
        self.assertEqual(trajectory(11), trajectory(12))

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        self.assertEqual(self.reset(client)["output"]["seed"], 21)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:NChain-v1", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

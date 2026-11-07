"""Acceptance run of the TabularMDP package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): gym and gymnasium are not
installed where the gate runs, so nothing here compares the fake with the upstream environment.
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


class TabularMDPCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, 4)["status"], "completed")
        for index in (-1, 5):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)                        # the refused steps changed nothing

    def test_a_reset_starts_on_state_zero(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 2, ticks=3)["status"], "completed")
        receipt = self.reset(client, seed=4)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 4)
        values = receipt["output"]["observation"]["values"]
        self.assertEqual(len(values), 10)                                      # num_states from the registration
        self.assertEqual(values[0], 1.0)                                       # mdp.py:57-63
        self.assertEqual(sum(values), 1.0)
        state = self.state(client)
        self.assertEqual(state["tick"], 0)
        self.assertEqual(state["reward"], 0.0)

    def test_a_step_is_one_transition(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        receipt = self.step(client, 3)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        values = output["observation"]["values"]
        self.assertEqual(len(values), 10)
        self.assertEqual(sum(values), 1.0)
        self.assertTrue(all(value in (0.0, 1.0) for value in values), values)
        self.assertEqual(output["tick"], 1)
        self.assertIs(output["terminated"], False)                             # mdp.py:75
        self.assertIs(output["truncated"], False)
        self.assertEqual(self.state(client)["observation"]["values"], values)

    def test_ticks_apply_the_action_once_per_transition(self) -> None:
        client = self.serve()
        self.reset(client, seed=6)
        batch = self.step(client, 1, ticks=4)
        self.assertEqual(batch["status"], "completed")
        self.assertEqual(batch["output"]["tick"], 4)
        batched_hash = batch["output"]["state_hash"]
        single = self.serve()                                                  # a fresh world with the same seed
        self.reset(single, seed=6)
        for _ in range(4):
            receipt = self.step(single, 1)
            self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 4)
        self.assertEqual(receipt["output"]["state_hash"], batched_hash)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                              # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action % 5)["output"]["state_hash"] for action in range(20)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        first_hashes = [self.step(client, action % 5)["output"]["state_hash"] for action in range(10)]
        other = self.serve()                                                   # the same seed through reset(seed)
        second = self.reset(other, seed=21)["output"]
        second_hashes = [self.step(other, action % 5)["output"]["state_hash"] for action in range(10)]
        self.assertEqual(first["observation"], second["observation"])
        self.assertEqual(first_hashes, second_hashes)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:TabularMDP-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                        # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

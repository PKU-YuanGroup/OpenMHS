"""Acceptance run of the MO-Gymnasium package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MO-Gymnasium itself is
not installed where the gate runs, so nothing here compares the fake with the upstream environment.  The fake keeps
the full reward vector in ``info.objectives`` because ``cap.world.step.v1``'s ``reward`` is a scalar.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
FISH, WOOD = 0, 1


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FishWoodCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, WOOD)["status"], "completed")
        for index in (-1, 2):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_the_start_state_is_the_woods_and_the_action_is_the_next_state(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["output"]["observation"]["values"], [WOOD])
        for action in (FISH, WOOD, FISH):
            receipt = self.step(client, action)
            self.assertEqual(receipt["status"], "completed")
            self.assertEqual(receipt["output"]["observation"]["values"], [action])
            self.assertEqual(receipt["output"]["terminated"], False)
            reward = receipt["output"]["reward"]
            self.assertIn(reward, (0.0, 1.0))
        self.assertEqual(self.state(client)["tick"], 3)
        self.assertEqual(self.state(client)["observation"]["values"], [FISH])

    def test_the_reward_vector_stays_in_info(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        self.step(client, WOOD)
        objectives = self.state(client)["info"]["objectives"]
        self.assertEqual(len(objectives), 2)
        self.assertTrue(all(value in (0.0, 1.0) for value in objectives), objectives)
        self.assertEqual(self.state(client)["reward"], sum(objectives))

    def test_a_seed_repeats_the_reward_sequence(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            out = []
            for action in (WOOD, FISH, WOOD, WOOD, FISH):
                receipt = self.step(client, action)["output"]
                out.append((receipt["reward"], receipt["state_hash"]))
            return out

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        self.assertEqual(self.reset(client)["output"]["seed"], 21)

    def test_the_episode_ends_at_200_steps(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        for number in range(1, 201):
            receipt = self.step(client, WOOD if number % 2 else FISH)
            self.assertEqual(receipt["status"], "completed", number)
            self.assertEqual(receipt["output"]["terminated"], number == 200, number)
            self.assertEqual(receipt["output"]["truncated"], number == 200, number)
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (200, True, True))
        self.assertEqual(self.step(client, WOOD)["error"]["mhs_code"], PRECONDITION)
        self.assertEqual(self.reset(client)["status"], "completed")               # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:fishwood-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, WOOD)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, WOOD), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

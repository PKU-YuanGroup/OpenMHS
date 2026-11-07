"""Acceptance run of the dart-env package: the gate, plus cases for what is specific to Copy-v0.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py); the upstream clone was
never imported, so nothing here compares the fake with the real environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
FAULT = "MHS.DEVICE.FAULTED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CopyCases(unittest.TestCase):
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

    def step(self, client, items, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"items": items}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_tuple_is_checked_by_the_environment(self) -> None:
        client = self.serve()
        refused = self.step(client, [5, 0, 0])                 # a movement outside Discrete(2)
        self.assertEqual(refused["status"], "failed")
        self.assertEqual(refused["error"]["mhs_code"], FAULT)  # the upstream asserts, it does not clamp
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_read_head_moves_and_off_tape_is_the_blank(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=3)["output"]["observation"]["index"]
        self.assertLess(first, 5)                              # a tape character, not the blank index
        for _ in range(2):                                     # head 0 -> -1 -> -2: both are off the tape
            receipt = self.step(client, [0, 0, 0])
            self.assertEqual(receipt["status"], "completed")
            self.assertEqual(receipt["output"]["observation"]["index"], 5)
        for _ in range(2):                                     # head -2 -> -1 -> 0: back on the first character
            receipt = self.step(client, [1, 0, 0])
            self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["observation"]["index"], first)

    def test_a_correct_copy_completes_the_target(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=5)["output"]["observation"]["index"]
        receipt = self.step(client, [0, 1, observation])       # write target[0], then step left
        self.assertEqual((receipt["status"], receipt["output"]["reward"]), ("completed", 1.0))
        writes = 1
        while not receipt["output"]["terminated"]:
            for _ in range(2):                                 # back to the read head of the next character
                receipt = self.step(client, [1, 0, 0])
                if receipt["output"]["terminated"]:
                    break
            if receipt["output"]["terminated"]:
                break
            observation = receipt["output"]["observation"]["index"]
            receipt = self.step(client, [0, 1, observation])
            self.assertEqual(receipt["status"], "completed")
            self.assertEqual(receipt["output"]["reward"], 1.0)
            writes += 1
        self.assertEqual(receipt["output"]["reward"], 1.0)
        self.assertEqual(receipt["output"]["terminated"], True)
        self.assertGreaterEqual(writes, 2)                     # starting_min_length is 2 (algorithmic_env.py:49)
        self.assertLessEqual(writes, 4)                        # randint(3) + 2 (algorithmic_env.py:227)

    def test_a_wrong_write_ends_the_episode(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=5)["output"]["observation"]["index"]
        wrong = (observation + 1) % 5                          # base is 5 (copy_.py:9)
        receipt = self.step(client, [0, 1, wrong])
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["reward"], -0.5)    # algorithmic_env.py:184
        self.assertEqual(receipt["output"]["terminated"], True)

    def test_the_time_limit_ends_the_episode_and_autoreset_continues(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        ticks = 0
        while True:
            receipt = self.step(client, [1, 0, 0])             # only move: the episode can end by time alone
            self.assertEqual(receipt["status"], "completed")
            ticks += 1
            if receipt["output"]["terminated"] or receipt["output"]["truncated"]:
                break
            self.assertLessEqual(ticks, 13)
        self.assertEqual(receipt["output"]["reward"], -1.0)    # algorithmic_env.py:191
        self.assertEqual(receipt["output"]["terminated"], True)
        self.assertGreaterEqual(ticks, 9)                      # time limit 2*len + 4 with len 2 .. 4
        next_receipt = self.step(client, [1, 0, 0])
        self.assertEqual(next_receipt["status"], "completed")  # autoreset starts episode 2
        self.assertEqual(next_receipt["output"]["tick"], 1)
        self.assertEqual(next_receipt["output"]["terminated"], False)
        self.assertEqual(self.state(client)["episode"], 2)

    def test_a_seed_repeats_the_tape(self) -> None:
        first_client = self.serve()
        first_reset = self.reset(first_client, seed=11)["output"]
        first_step = self.step(first_client, [1, 0, 0])["output"]
        second_client = self.serve()
        second_reset = self.reset(second_client, seed=11)["output"]
        second_step = self.step(second_client, [1, 0, 0])["output"]
        self.assertEqual(first_reset["observation"], second_reset["observation"])
        self.assertEqual(first_step["observation"], second_step["observation"])
        self.assertEqual(first_step["reward"], second_step["reward"])

    def test_the_seed_capability_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["status"], "completed")
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_ticks_applies_the_action_once_per_tick(self) -> None:
        client = self.serve()
        self.reset(client, seed=7)
        receipt = self.step(client, [1, 0, 0], ticks=2)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 2)
        self.assertEqual(receipt["output"]["reward"], 0.0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gym:Copy-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [1, 0, 0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [1, 0, 0]), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)        # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the Gym Trading Env package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): pandas, numpy and gymnasium are not installed where the gate runs, so
nothing here compares the fake with the upstream environment.  The expected numbers come from the fake's canned
series (100, 101, 102, ...) and from the trade arithmetic of ``utils/portfolio.py``, not from a real run.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
LAST_ROW = 119          # placeholder: the fake's series has 120 rows, so the last index is 119


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class TradingEnvCases(unittest.TestCase):
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
        refused = client.invoke("cap.world.step.v1", {"ticks": 0, "action": {"index": 0}}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)            # the bridge's step input bound
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_the_first_step_pays_the_price_return(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, 1)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # the fake buys or holds at 100 and values the position at 101: 1000 -> 1010, reward log(101/100)
        self.assertAlmostEqual(output["reward"], math.log(101 / 100), places=12)
        values = output["observation"]["values"]
        self.assertAlmostEqual(values[0], 0.01, places=12)
        self.assertEqual((values[1], values[2]), (1, 1.0))
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))

    def test_a_cash_step_pays_zero_then_a_long_step_pays_the_return(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        self.assertEqual(self.step(client, 0)["output"]["reward"], 0.0)          # cash at 100 -> cash at 101
        receipt = self.step(client, 1)
        # trade at 101 then value at 102: 1000 -> 1000 * 102 / 101
        self.assertAlmostEqual(receipt["output"]["reward"], math.log(102 / 101), places=12)
        self.assertAlmostEqual(receipt["output"]["observation"]["values"][0], 102 / 101 - 1, places=12)
        self.assertEqual(receipt["output"]["tick"], 2)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"] for action in (1, 0, 0, 1, 1)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_dataset_end_truncates_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, 0, ticks=1000)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual((output["terminated"], output["truncated"]), (False, True))
        # environments.py:248 truncates when the row index reaches len(df) - 1
        self.assertEqual(output["tick"], LAST_ROW)
        ended = self.step(client, 0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")       # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:TradingEnv", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

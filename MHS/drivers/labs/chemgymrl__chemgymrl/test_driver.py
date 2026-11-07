"""Acceptance run of the ChemGymRL GenWurtzExtract driver: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream package is
not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
OBSERVATION_VALUES = 3 * (100 + 7)          # three working vessels, 100 layers and a seven-product one-hot


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class GenWurtzExtractCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, 0)["status"], "completed")
        for index in (-1, 41):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_the_observation_has_the_upstream_shape(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=5)["output"]["observation"]["values"]
        self.assertEqual(len(observation), OBSERVATION_VALUES)
        for vessel in range(3):
            block = observation[vessel * 107:(vessel + 1) * 107]
            self.assertTrue(all(0.0 <= value <= 1.0 for value in block))
            one_hot = block[100:]
            self.assertEqual(sum(one_hot), 1.0)                                  # characterization_bench.py:177-186
            self.assertTrue(set(one_hot) <= {0.0, 1.0})

    def test_the_last_flattened_action_is_terminal(self) -> None:
        client = self.serve()
        receipt = self.step(client, 40)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, True, False))
        ended = self.step(client, 0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")       # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_episode_ends_at_the_fifty_step_default(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        output = None
        for expected_tick in range(1, 51):
            receipt = self.step(client, 0)
            self.assertEqual(receipt["status"], "completed", expected_tick)
            output = receipt["output"]
            self.assertEqual(output["tick"], expected_tick)
            if expected_tick < 50:
                self.assertFalse(output["terminated"], expected_tick)
        self.assertTrue(output["terminated"])                                   # general_bench.py:213
        self.assertFalse(output["truncated"])                                   # general_bench.py:222
        self.assertEqual(self.step(client, 0)["error"]["mhs_code"], PRECONDITION)

    def test_a_seed_repeats_the_observation(self) -> None:
        def trajectory():
            client = self.serve()
            first = self.reset(client, seed=9)["output"]["observation"]["values"]
            second = self.step(client, 5)["output"]["observation"]["values"]
            third = self.step(client, 39)["output"]["observation"]["values"]
            return first, second, third

        self.assertEqual(trajectory(), trajectory())

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        second = self.reset(client, seed=21)["output"]
        self.assertEqual(first["observation"], second["observation"])

    def test_reset_accepts_and_ignores_options(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3, options={"unused": True})["status"], "completed")
        self.assertEqual(self.reset(client, options={"another": 1})["status"], "completed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:GenWurtzExtract-v2", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 0), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

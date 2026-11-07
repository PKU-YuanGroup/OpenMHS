"""Acceptance run of the Mars Explorer package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream package
needs legacy gym, numpy, pygame and matplotlib, so nothing here imports or compares against it.
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


class MarsExplorerCases(unittest.TestCase):
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
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, 0)["status"], "completed")
        for index in (-1, 4):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)                 # the refused steps changed nothing

    def test_reset_returns_the_full_map_observation(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=7)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 7)                  # the bridge records the requested seed
        values = receipt["output"]["observation"]["values"]
        self.assertEqual(len(values), 21 * 21)                          # 21 x 21 x 1 flattened by the bridge
        self.assertTrue(all(0.0 <= value <= 1.0 for value in values))

    def test_a_move_changes_the_observation_and_advances_the_tick(self) -> None:
        client = self.serve()
        before = self.reset(client)["output"]["observation"]["values"]
        receipt = self.step(client, 0)                                  # [0, 0] -> [1, 0]
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertFalse(output["terminated"])
        self.assertIsInstance(output["reward"], (int, float))
        self.assertEqual(len(output["observation"]["values"]), 21 * 21)
        self.assertNotEqual(output["observation"]["values"], before)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_leaving_the_map_ends_the_episode_with_the_penalty(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, 1)                                  # from [0, 0] the -1 axis leaves the map
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["reward"], output["terminated"], output["tick"]), (-400.0, True, 1))
        # the driver configures autoreset: the next step starts a fresh episode instead of being refused
        next_episode = self.step(client, 0)
        self.assertEqual(next_episode["status"], "completed")
        self.assertEqual((next_episode["output"]["tick"], next_episode["output"]["terminated"]), (1, False))
        self.assertEqual(self.reset(client)["status"], "completed")     # an explicit reset starts another episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_seed_class_records_the_next_reset_seed(self) -> None:
        client = self.serve()
        seeded = client.invoke("cap.world.seed.v1", {"seed": 12}, **self.ids)
        self.assertEqual((seeded["output"]["seed"], seeded["output"]["accepted"]), (12, True))
        self.assertEqual(self.reset(client)["output"]["seed"], 12)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gym:explorer-v01", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, 0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 0), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                 # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

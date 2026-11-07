"""Acceptance run of the MetaIsaacGrasp package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Isaac Sim and Isaac Lab
are not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ACTION = {"values": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MetaIsaacGraspCases(unittest.TestCase):
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

    def step(self, client, ticks=1, action=None):
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": dict(action or ACTION)}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_reset_returns_a_seed_and_the_reduced_observation(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=3)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 3)
        values = receipt["output"]["observation"]["values"]
        self.assertEqual(len(values), 14)                      # camera pose + six arm joints + gripper
        self.assertEqual(self.state(client)["tick"], 0)

    def test_step_advances_the_tick_and_changes_the_hash(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        first = self.step(client)
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["output"]["tick"], 1)
        self.assertEqual(first["output"]["reward"], 0.0)
        self.assertEqual(first["output"]["terminated"], False)
        self.assertEqual(first["output"]["truncated"], False)
        second = self.step(client)
        self.assertNotEqual(first["output"]["state_hash"], second["output"]["state_hash"])
        self.assertEqual(self.state(client)["tick"], 2)

    def test_a_seeded_reset_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                              # a fresh world: the hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["status"], "completed")
            return [self.step(client, action={"values": [value] * 7})["output"]["state_hash"]
                    for value in (1.0, -1.0, 0.5, 0.5)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["status"], "completed")
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_episode_truncates_at_the_step_total(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, ticks=30)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual((receipt["output"]["tick"], receipt["output"]["truncated"]), (30, True))
        ended = self.step(client)
        self.assertEqual(ended["status"], "failed")
        self.assertEqual(ended["error"]["mhs_code"], PRECONDITION)
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")       # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_bridge_auto_resets_the_first_step(self) -> None:
        client = self.serve()
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 1)

    def test_the_action_and_observation_shapes_are_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        step = next(item for item in device["capabilities"] if item["capability_id"] == "cap.world.step.v1")
        self.assertEqual(step["input_schema"]["properties"]["action"]["properties"]["values"]["maxItems"], 7)
        self.assertEqual(self.reset(client, seed=2)["output"]["observation"]["values"][:7],
                         [0.7, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0])
        # no finite action bound is stated by the clone, so no envelope refusal is invented for the values
        self.assertEqual(self.step(client, action={"values": [0.0] * 7})["status"], "completed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["engine"], "isaaclab:AIR-v0-Data (Isaac Sim 4.5 / Isaac Lab 2.0)")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 60.0, places=6)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)
        self.assertTrue(any("NOT COVERED" in gap for gap in fidelity["gaps"]))

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

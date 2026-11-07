"""Acceptance run of the gym-compete package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the legacy gym 0.9.1 /
mujoco-py 0.5.7 stack is not installed where the gate runs, so nothing here compares the fake with upstream MuJoCo.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ZERO_ACTION = {"items": [[0.0] * 8, [0.0] * 8]}
ONE_ACTION = {"items": [[1.0] * 8, [1.0] * 8]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class GymCompeteCases(unittest.TestCase):
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

    def step(self, client, action=None, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action or ZERO_ACTION}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_contract_has_one_box_per_ant(self) -> None:
        client = self.serve()
        first = client.inspect(self.ids["device_id"])
        self.assertEqual(first["mode"], "simulated")
        step_cap = next(item for item in first["capabilities"] if item["capability_id"] == "cap.world.step.v1")
        action = step_cap["input_schema"]["properties"]["action"]
        self.assertEqual(action["type"], "object")
        items_schema = action["properties"]["items"]
        self.assertEqual((items_schema["type"], items_schema["minItems"], items_schema["maxItems"]),
                         ("array", 2, 2))
        # the observation is a Tuple of two per-ant Boxes (multi_agent_env.py:103-111), each 122 values
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed")
        items = receipt["output"]["observation"]["items"]
        self.assertEqual(len(items), 2)
        self.assertEqual([len(item["values"]) for item in items], [122, 122])
        self.assertEqual(receipt["output"]["tick"], 1)
        self.assertFalse(receipt["output"]["terminated"])

    def test_the_action_reaches_the_fake(self) -> None:
        zero = self.serve()
        self.reset(zero, seed=5)
        stopped = self.step(zero, ZERO_ACTION)["output"]["observation"]["items"][0]["values"]
        pushed = self.serve()
        self.reset(pushed, seed=5)
        moved = self.step(pushed, ONE_ACTION)["output"]["observation"]["items"][0]["values"]
        self.assertNotEqual(stopped[0], moved[0])          # the root x coordinate follows the mean control

    def test_ticks_advance_the_environment(self) -> None:
        client = self.serve()
        receipt = self.step(client, ticks=3)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 3)
        self.assertFalse(receipt["output"]["truncated"])
        self.assertEqual(self.state(client)["tick"], 3)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                         # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, ONE_ACTION)["output"]["state_hash"] for _ in range(4)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        seeded = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(seeded["status"], "completed")
        self.assertTrue(seeded["output"]["accepted"])
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertTrue(fidelity["engine"].startswith("gym-compete:run-to-goal-ants-v0"))
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)            # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

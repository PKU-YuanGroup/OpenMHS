"""Acceptance run of the HumanoidGen package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): SAPIEN, ManiSkill,
torch, the external assets and the clone are not installed or imported where the gate runs, so nothing here
compares the fake with the upstream environment.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
#: A valid 38-element action: the pd_joint_pos controller takes the arm and hand joint positions.
HOME = [0.0] * 38


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class BlocksStackCases(unittest.TestCase):
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

    def step(self, client, values, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_schema_requires_38_values(self) -> None:
        client = self.serve()
        refused = self.step(client, HOME[:-1])
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.step(client, HOME)["status"], "completed")

    def test_a_step_advances_the_world_and_echoes_the_action(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, HOME)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertEqual((output["reward"], output["terminated"], output["truncated"]), (0.0, False, False))
        self.assertEqual(output["observation"]["values"], HOME)
        self.assertTrue(all(math.isfinite(value) for value in output["observation"]["values"]))
        self.assertEqual(self.state(client)["info"]["elapsed_steps"], 1)

    def test_two_actions_produce_different_states(self) -> None:
        def after(action):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=5)["status"], "completed")
            return self.step(client, action)["output"]["state_hash"]

        self.assertNotEqual(after(HOME), after([0.25] + HOME[1:]))

    def test_a_seed_repeats_the_reset_observation(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]["observation"]
        self.assertEqual(self.reset(client, seed=11)["output"]["observation"], first)
        self.assertNotEqual(self.reset(client, seed=12)["output"]["observation"], first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_registered_episode_limit_truncates_at_200(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, HOME, ticks=200)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (200, False, True))
        ended = self.step(client, HOME)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:humanoidgen blocks_stack_easy fake", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (10.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 7)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, HOME)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, HOME), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                    # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the RoboCAS package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): SAPIEN, ManiSkill2,
the submodule assets and the clone are not installed or imported where the gate runs, so nothing here compares the
fake with the upstream environment.
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
#: A valid 11-element action: base (3), absolute EEF pose (6) and gripper (2), all inside the derived bounds.
HOME = [0.3, 0.0, 0.0, 0.3, 0.0, 0.6, 0.0, 0.0, 0.0, 0.02, 0.02]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RoboCASCases(unittest.TestCase):
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

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, HOME)["status"], "completed")
        for values in ([0.9, 0.0, 0.0] + HOME[3:], HOME[0:5] + [1.6] + HOME[6:],
                       HOME[0:9] + [0.05, 0.02], HOME[:10]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertIn(refused["error"]["mhs_code"], (ENVELOPE, INPUT_INVALID), values)
        self.assertEqual(self.state(client)["tick"], 1)                    # the refused steps changed nothing

    def test_a_step_advances_the_simulation_and_terminates(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, HOME)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertEqual((output["reward"], output["terminated"], output["truncated"]), (0.0, True, False))
        self.assertEqual(len(output["observation"]["values"]), 22)
        self.assertTrue(all(math.isfinite(value) for value in output["observation"]["values"]))
        self.assertEqual(self.state(client)["info"]["success"], True)

    def test_the_fake_echoes_the_commanded_state(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")
        values = self.step(client, HOME)["output"]["observation"]["values"]
        self.assertEqual(values[:11], HOME)
        # The fake derives the velocities from the previous fake state, which is a placeholder start, not zeros.
        self.assertEqual(len(values[11:]), 11)
        self.assertTrue(all(math.isfinite(value) for value in values[11:]))

    def test_two_actions_produce_different_states(self) -> None:
        def after(action):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=5)["status"], "completed")
            return self.step(client, action)["output"]["state_hash"]

        self.assertNotEqual(after(HOME), after([0.0, 0.0, 0.0] + HOME[3:]))

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, HOME)["output"]["state_hash"] for _ in range(3)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:RoboCAS-v0 fake", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (100.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, HOME)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, HOME), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                    # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

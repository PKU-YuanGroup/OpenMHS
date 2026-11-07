"""Acceptance run of the Flamingo package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Isaac Sim, Isaac Lab and
the upstream task are not installed where the gate runs, so nothing here compares the stand-in with the upstream
environment and no simulator or hardware run is claimed.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ACTION = [0.1, -0.2, 0.3, -0.4, 0.5, -0.6, 0.7, -0.8]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FlamingoCases(unittest.TestCase):
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

    def test_the_action_is_eight_unbounded_values(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, ACTION)
        self.assertEqual(receipt["status"], "completed", receipt)
        observation = receipt["output"]["observation"]["values"]
        self.assertEqual(len(observation), 28)
        self.assertEqual(observation[20:], ACTION)                 # the last-action term of stack_policy
        self.assertEqual((receipt["output"]["reward"], receipt["output"]["tick"]), (0.0, 1))
        # manager_based_constraint_rl_env.py:342-344: the action space is Box(-inf, inf), so large values are valid
        self.assertEqual(self.step(client, [1.0e6] * 8)["status"], "completed")
        refused = self.step(client, [0.0] * 7)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 2)            # the refused step changed nothing

    def test_ticks_advance_and_the_episode_truncates_at_1000(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, [0.0] * 8, ticks=1000)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        # 20.0 s / (4 * 0.005 s) = 1000 steps (manager_based_constraint_rl_env.py:97-105)
        self.assertEqual((output["tick"], output["truncated"], output["terminated"]), (1000, True, False))
        ended = self.step(client, [0.0] * 8)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["output"]["seed"], 5)
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_reset_options_are_accepted(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=2, options={"note": "the fake accepts and ignores reset options"})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["seed"], 2)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "isaaclab:Isaac-Velocity-Flat-Flamingo-v1-ppo-constraint")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 8)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * 8), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)             # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

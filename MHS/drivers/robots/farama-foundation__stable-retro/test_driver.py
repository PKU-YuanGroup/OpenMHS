"""Acceptance run of the Stable Retro package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the stable-retro
extension modules, emulator cores and game data are not imported here, so nothing compares the fake with upstream.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
FIRE = {"values": [0, 0, 1]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class StableRetroCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": values}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, FIRE)["status"], "completed")
        refused = self.step(client, {"values": [2, 0, 0]})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 1)          # the refused step changed nothing

    def test_reset_is_deterministic_and_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=5)["output"]
        self.assertEqual(self.reset(client, seed=5)["output"], first)
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual((accepted["status"], accepted["output"]["seed"]), ("completed", 21))
        self.assertEqual(accepted["output"]["accepted"], True)
        self.assertEqual(self.reset(client)["output"]["seed"], 21)
        self.assertEqual(self.reset(client)["output"]["observation"], first["observation"])

    def test_a_game_over_terminates_and_a_reset_starts_a_new_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, FIRE, ticks=40)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # the fake loses a life every 12 frames and terminates when the third life is gone (test data, not a
        # game rule); the bridge stops at the terminal state and sums the rewards, one per fire action
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 36))
        self.assertEqual(output["reward"], 36.0)
        ended = self.step(client, FIRE)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_observation_and_the_fidelity_contract_are_published(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        state = self.state(client)
        self.assertEqual(len(state["observation"]["values"]), 60)   # the fake's stand-in screen
        self.assertEqual((state["terminated"], state["truncated"], state["tick"]), (False, False, 0))
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("stable-retro:RetroEnv", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 60.0)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, FIRE)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, FIRE), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

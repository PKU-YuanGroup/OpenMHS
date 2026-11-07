"""Acceptance run of the RoboCasa GR-1 Tabletop package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream stack
(robosuite, MuJoCo, the tabletop assets) is not installed where the gate runs, so nothing here compares the fake with
the upstream environment.
"""

import copy
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"

# Default GR-1 action shapes (fake.py holds the same sizes); a different controller configuration can change them.
# The fake drops the upstream "action." key prefix so the bridge's derived limit path "action.<key>" resolves.
ZERO_ACTION = {
    "left_hand": [0.0] * 6,
    "right_hand": [0.0] * 6,
    "left_arm": [0.0] * 7,
    "right_arm": [0.0] * 7,
    "waist": [0.0] * 3,
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RoboCasaGR1TabletopCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action or copy.deepcopy(ZERO_ACTION)},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        refused_action = copy.deepcopy(ZERO_ACTION)
        refused_action["left_arm"][0] = 2.0                          # above the upstream Box max of 1
        refused = self.step(client, refused_action)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 1)                      # the refused step changed nothing

    def test_a_seed_repeats_the_initial_observation(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]
        again = self.reset(client, seed=11)["output"]
        other = self.reset(client, seed=12)["output"]
        self.assertEqual(first["observation"], again["observation"])
        self.assertNotEqual(first["observation"], other["observation"])

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_step_changes_the_state_and_the_tick(self) -> None:
        client = self.serve()
        initial = self.reset(client, seed=3)["output"]["observation"]
        receipt = self.step(client, ticks=2)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 2)
        self.assertNotEqual(output["observation"], initial)
        self.assertEqual((output["reward"], output["terminated"], output["truncated"]), (0.0, False, False))

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertIn("analytic", fidelity["engine"])
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                      # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

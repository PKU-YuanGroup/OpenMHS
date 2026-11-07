"""Acceptance run of the JSBGym package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): gymnasium, jsbsim and
numpy are not installed where the gate runs, so nothing here compares the stand-in with the upstream environment.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ZERO_ACTION = {"values": [0.0, 0.0, 0.0]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class JsbGymCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, [1.0, 0.0, -1.0])["status"], "completed")
        for values in ([1.0001, 0.0, 0.0], [0.0, -1.0001, 0.0], [0.0, 0.0, 1.0001]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        refused = client.invoke("cap.world.step.v1", {"ticks": 0, "action": ZERO_ACTION}, **self.ids)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", INPUT_INVALID))
        refused = client.invoke("cap.world.step.v1", {"ticks": 10001, "action": ZERO_ACTION}, **self.ids)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", INPUT_INVALID))
        self.assertEqual(self.state(client)["tick"], 1)              # the refused steps changed nothing

    def test_reset_returns_the_eleven_upstream_state_variables(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=3)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 3)
        values = receipt["output"]["observation"]["values"]
        self.assertEqual(len(values), 11)
        self.assertTrue(all(isinstance(value, (int, float)) and math.isfinite(value) for value in values), values)
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual((self.state(client)["terminated"], self.state(client)["truncated"]), (False, False))

    def test_a_step_advances_and_changes_the_observation(self) -> None:
        client = self.serve()
        before = self.reset(client)["output"]["observation"]["values"]
        receipt = self.step(client, [0.5, -0.5, 0.25])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertTrue(math.isfinite(output["reward"]))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertNotEqual(output["observation"]["values"], before)

    def test_the_seed_sets_the_next_reset_and_a_reset_repeats(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["status"], "completed")
        self.assertEqual((accepted["output"]["seed"], accepted["output"]["accepted"]), (21, True))
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        # the default HeadingControlTask start state is fixed, so the same seed and no step repeat it
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_an_episode_ends_after_the_step_budget(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, [0.0, 0.0, 0.0], ticks=1000)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # placeholder: the stand-in runs 60 s at 5 Hz, so its episode budget is 300 agent steps
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 300))
        ended = self.step(client, [0.0, 0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_an_altitude_excursion_terminates_early(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, [0.0, 1.0, 0.0], ticks=400)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # the upstream task terminates when the altitude error exceeds 1000 ft (tasks.py:429-431, :263)
        self.assertTrue(output["terminated"], output)
        self.assertFalse(output["truncated"], output)
        self.assertLess(output["tick"], 300)
        self.assertGreater(abs(output["observation"]["values"][9]), 1000.0, output)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertIn("jsbgym", fidelity["engine"])
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (200.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.1, 0.1, 0.1])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.1, 0.1, 0.1]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)              # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

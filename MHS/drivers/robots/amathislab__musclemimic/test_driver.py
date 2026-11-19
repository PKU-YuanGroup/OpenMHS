"""Acceptance run of the MuscleMimic MyoFullBody package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo, JAX, flax and the
external musclemimic_models package are not installed where the gate runs, and the model file is not in this clone,
so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ZERO_ACTION = {"values": [0.0]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MyoFullBodyCases(unittest.TestCase):
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

    def step(self, client, action=ZERO_ACTION, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_is_bounded_by_the_muscle_control_range(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        for value in (1.5, -1.5):
            refused = self.step(client, {"values": [value]})
            self.assertEqual(refused["status"], "rejected", value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_a_step_advances_the_world_and_returns_a_flat_observation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, {"values": [0.1, -0.2, 0.3]})
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertIsInstance(output["observation"]["values"], list)
        self.assertEqual(output["tick"], 1)
        self.assertFalse(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertTrue(output["state_hash"].startswith("sha256:"))
        self.assertEqual(self.state(client)["tick"], 1)
        self.assertEqual(self.state(client)["observation"], output["observation"])

    def test_ticks_accumulate_and_more_than_one_tick_changes_the_state(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, {"values": [0.5]}, ticks=3)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 3)
        self.assertEqual(self.state(client)["tick"], 3)

    def test_the_action_must_have_a_non_empty_numeric_values_row(self) -> None:
        client = self.serve()
        for action in ({}, {"values": "not-an-array"}):
            refused = self.step(client, action)
            self.assertEqual(refused["status"], "rejected", action)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, action)
        empty = self.step(client, {"values": []})                 # the schema has no minimum length
        self.assertEqual((empty["status"], empty["error"]["mhs_code"]), ("failed", INPUT_INVALID))
        self.assertEqual(self.step(client)["status"], "completed")

    def test_the_reset_is_full_and_the_seed_is_not_applied(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]
        self.assertEqual(first["seed"], 0)
        self.step(client, ticks=2)
        self.assertEqual(self.state(client)["tick"], 2)
        second = self.reset(client, seed=7)["output"]
        self.assertEqual(second["observation"], first["observation"])
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(self.state(client)["episode"], 2)

    def test_the_reset_refuses_a_non_default_scenario_and_non_empty_options(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, scenario="default")["status"], "completed")
        refused = self.reset(client, scenario="elsewhere")
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("failed", INPUT_INVALID))
        refused = self.reset(client, options={"upstream": "none"})
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("failed", INPUT_INVALID))
        self.assertEqual(self.reset(client, options={})["status"], "completed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("analytic:FakeMyoFullBody", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (10.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_missing_and_nonfinite_native_flags_are_refused(self) -> None:
        for field, value in ((1, []), (1, float("nan")), (2, None), (2, float("nan")), (3, [])):
            with self.subTest(field=field, value=value):
                driver = load_driver(HERE, backend="fake")
                self.addCleanup(driver.close)
                native_step = driver.native.step

                def malformed(action, native_step=native_step, field=field, value=value):
                    result = list(native_step(action))
                    result[field] = value
                    return tuple(result)

                driver.native.step = malformed
                with self.assertRaises(DriverFailed) as caught:
                    driver.call("cap.world.step.v1", {"ticks": 1, "action": ZERO_ACTION})
                self.assertEqual(caught.exception.code, "MHS.CAPABILITY.OUTPUT_INVALID")

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()

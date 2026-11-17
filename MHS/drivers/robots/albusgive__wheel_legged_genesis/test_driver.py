"""Acceptance run of the wheel-legged Genesis package: the gate, plus cases for this driver.

The cases run on the fake backend (fake.py).  Genesis, PyTorch and the upstream environment are not installed where
the gate runs, so nothing here compares the fake with the upstream simulator.
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
ZERO_ACTION = {"values": [0.0] * 8}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WheelLeggedCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake", site_limits=HERE / "site-limits.example.json")
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

    def test_the_action_envelope_is_enforced(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        for value in (100.5, -100.5):
            refused = self.step(client, {"values": [value] + [0.0] * 7})
            self.assertEqual(refused["status"], "rejected", value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["tick"], 1)                  # the refused steps changed nothing
        accepted = self.step(client, {"values": [100.0] + [0.0] * 7})
        self.assertEqual(accepted["status"], "completed")

    def test_unfilled_action_bounds_refuse_the_step(self) -> None:
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session_id = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.invoke("cap.world.step.v1", {"ticks": 1, "action": ZERO_ACTION},
                                device_id=device_id, session_id=session_id)
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")

    def test_a_step_advances_the_world_and_returns_the_286_value_row(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, {"values": [0.1] * 8})
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(len(output["observation"]["values"]), 286)      # 9 * 28 + 28 + 6
        self.assertEqual(output["tick"], 1)
        self.assertFalse(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertTrue(output["state_hash"].startswith("sha256:"))
        self.assertEqual(self.state(client)["tick"], 1)

    def test_a_seed_repeats_a_reset(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]
        self.assertEqual(first["seed"], 7)
        self.step(client)
        second = self.reset(client, seed=7)["output"]
        self.assertEqual(second["observation"], first["observation"])
        self.assertEqual(self.state(client)["seed"], 7)

    def test_the_default_reset_seed_is_reported(self) -> None:
        client = self.serve()
        output = self.reset(client)["output"]
        self.assertEqual(output["seed"], 0)
        self.assertEqual(self.state(client)["seed"], 0)
        self.assertEqual(len(output["observation"]["values"]), 286)

    def test_the_episode_truncates_after_the_configured_length(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, ticks=2001)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 2001)
        self.assertFalse(output["terminated"])
        self.assertTrue(output["truncated"])
        ended = self.step(client)
        self.assertEqual(ended["status"], "failed")
        self.assertEqual(ended["error"]["mhs_code"], PRECONDITION)
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_action_must_have_eight_values(self) -> None:
        client = self.serve()
        refused = self.step(client, {"values": [0.0] * 7})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.step(client)["status"], "completed")

    def test_missing_and_nonfinite_native_scalars_are_refused(self) -> None:
        for field, value in ((2, []), (2, float("nan")), (3, None), (3, [float("nan")])):
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

    def test_the_reset_options_are_accepted_and_the_scenario_is_limited(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=2, options={"upstream": "none"})["status"], "completed")
        self.assertEqual(self.reset(client, scenario="default")["status"], "completed")
        self.assertEqual(self.reset(client, scenario="elsewhere")["status"], "failed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("analytic:FakeWheelLeggedEnv", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (10.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced

    def test_the_step_reads_the_last_observation_and_info(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        self.step(client, {"values": [0.2] * 8})
        state = self.state(client)
        self.assertEqual(len(state["observation"]["values"]), 286)
        self.assertFalse(state["terminated"])
        self.assertIn("time_outs", state["info"])
        self.assertEqual(state["episode"], 1)


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the Lake Shore 336 package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
CONFIGURE = "cap.device.configure.v1"
SAFE_STATE = "x-cap.msuarezrodriguez.heaters_off.v1"
SITE_LIMITS = json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class LakeShore336Cases(unittest.TestCase):
    def serve(self, site_limits=None):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver.native

    def configure(self, client, **patch):
        return client.invoke(CONFIGURE, patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_reads_keep_the_upstream_parser_types(self) -> None:
        client, _fake = self.serve()
        state = self.state(client)
        self.assertEqual(state["identity"], "Lake Shore Model 336, fake, 0.0")   # placeholder
        self.assertEqual(state["temperature"], 300.0)                            # placeholder
        self.assertEqual(state["setpoint"], 300.0)                               # placeholder
        self.assertEqual(state["ramp_rate"], 1.0)                                # placeholder
        self.assertIs(state["ramp_enabled"], False)                              # placeholder
        self.assertEqual(state["heater_range"], "off")                           # placeholder
        self.assertEqual(state["output_mode"], "off")                            # placeholder
        self.assertEqual(state["output_input"], "none")                          # placeholder
        self.assertIs(state["output_powerup_enable"], False)                     # placeholder

    def test_the_setpoint_and_ramp_rate_wait_for_the_site(self) -> None:
        client, fake = self.serve()
        for patch in ({"setpoint": 250.0}, {"ramp_rate": 2.0}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(fake._setpoint, 300.0)                                  # placeholder, unchanged
        self.assertEqual(fake._ramp_rate, 1.0)                                   # placeholder, unchanged

    def test_the_example_overlay_bounds_the_setpoint(self) -> None:
        client, _fake = self.serve(site_limits=SITE_LIMITS)
        self.assertEqual(self.configure(client, setpoint=250.0)["status"], "completed")
        self.assertEqual(self.state(client)["setpoint"], 250.0)
        for value in (9.99, 300.01):
            refused = self.configure(client, setpoint=value)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["setpoint"], 250.0)

    def test_the_heater_range_and_output_mode_are_written_and_read_back(self) -> None:
        client, fake = self.serve()
        self.assertEqual(self.configure(client, heater_range="low")["status"], "completed")
        self.assertEqual(self.state(client)["heater_range"], "low")
        self.assertEqual(fake._ranges[1], 1)
        refused = self.configure(client, heater_range="max")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.configure(client, output_mode="open loop")["status"], "completed")
        self.assertEqual(self.state(client)["output_mode"], "open loop")
        self.assertEqual(self.configure(client, output_input="B")["status"], "completed")
        self.assertEqual(self.state(client)["output_input"], "B")
        self.assertEqual(self.configure(client, output_powerup_enable=True)["status"], "completed")
        self.assertIs(self.state(client)["output_powerup_enable"], True)
        self.assertEqual(fake._modes[1], 3)
        self.assertEqual(fake._inputs[1], 2)

    def test_the_ramp_and_manual_output_are_written(self) -> None:
        client, fake = self.serve(site_limits=SITE_LIMITS)
        self.assertEqual(self.configure(client, ramp_rate=2.5)["status"], "completed")
        self.assertEqual(self.state(client)["ramp_rate"], 2.5)
        self.assertEqual(self.configure(client, ramp_enabled=True)["status"], "completed")
        self.assertIs(self.state(client)["ramp_enabled"], True)
        self.assertEqual(self.configure(client, manual_output=25.5)["status"], "completed")
        self.assertEqual(fake._manual_output, 25.5)
        refused = self.configure(client, manual_output=100.1)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_estop_turns_both_heaters_off_and_latches(self) -> None:
        client, fake = self.serve(site_limits=SITE_LIMITS)
        self.assertEqual(self.configure(client, heater_range="high")["status"], "completed")
        self.assertEqual(self.configure(client, output_mode="closed loop")["status"], "completed")
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(fake._ranges, {1: 0, 2: 0})
        self.assertEqual(fake._modes, {1: 0, 2: 0})
        refused = self.configure(client, heater_range="low")
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_safe_state_action_reports_the_readback(self) -> None:
        client, fake = self.serve()
        self.assertEqual(self.configure(client, heater_range="high")["status"], "completed")
        receipt = client.invoke(SAFE_STATE, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["heater_range_1"], "off")
        self.assertEqual(receipt["output"]["heater_range_2"], "off")
        self.assertEqual(receipt["output"]["output_mode_1"], "off")
        self.assertEqual(receipt["output"]["output_mode_2"], "off")
        self.assertEqual(fake._ranges, {1: 0, 2: 0})

    def test_a_safe_state_readback_that_is_not_off_fails(self) -> None:
        # Model review: the controller ignoring RANGE n,0 must not be reported as an achieved safe state.
        client, fake = self.serve()
        self.assertEqual(self.configure(client, heater_range="high")["status"], "completed")
        fake.set_heater_range = lambda **_kwargs: None   # placeholder: the RANGE write has no effect
        receipt = client.invoke(SAFE_STATE, {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", receipt)
        self.assertEqual(fake._ranges[1], 3)

    def test_a_failed_native_set_is_a_failed_receipt(self) -> None:
        client, fake = self.serve(site_limits=SITE_LIMITS)

        def rejected(**_kwargs):
            raise RuntimeError("placeholder: VISA write failed")

        fake.set_setpoint = rejected
        receipt = self.configure(client, setpoint=250.0)
        self.assertEqual(receipt["status"], "failed", receipt)

    def test_closing_the_driver_closes_the_instrument(self) -> None:
        driver = load_driver(HERE, backend="fake")
        fake = driver.native
        driver.close()
        self.assertTrue(fake._closed)


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the Keithley 2450 driver: the gate, plus the cases specific to this package.

Add cases, never remove the check_driver call.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import DriverFailed, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
CONFIGURE = "cap.device.configure.v1"
SAFE_STATE = "x-cap.qcodespp.output_off.v1"
SITE_LIMITS = json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Keithley2450Cases(unittest.TestCase):
    def serve(self, site_limits=None):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver.native

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_reads_keep_the_upstream_parser_types(self) -> None:
        client, _fake = self.serve()
        state = self.state(client)
        self.assertAlmostEqual(state["voltage"], 1.0)             # placeholder
        self.assertAlmostEqual(state["current"], 0.001)           # placeholder
        self.assertAlmostEqual(state["resistance"], 1000.0)       # placeholder
        self.assertIs(state["output"], True)                      # placeholder
        self.assertEqual(state["source"], "CURR")                 # placeholder
        self.assertAlmostEqual(state["compliancev"], 10.0)        # placeholder
        self.assertAlmostEqual(state["compliancei"], 0.1)         # placeholder

    def test_operator_required_waits_for_the_site_envelope(self) -> None:
        client, _fake = self.serve()
        refused = client.invoke(CONFIGURE, {"compliancei": 0.05}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")
        self.assertAlmostEqual(self.state(client)["compliancei"], 0.1)   # placeholder, unchanged

    def test_the_site_envelope_narrows_the_compliance(self) -> None:
        client, _fake = self.serve(site_limits=SITE_LIMITS)
        applied = client.invoke(CONFIGURE, {"compliancei": 0.05}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        self.assertAlmostEqual(self.state(client)["compliancei"], 0.05)
        refused = client.invoke(CONFIGURE, {"compliancei": 1.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertAlmostEqual(self.state(client)["compliancei"], 0.05)

    def test_the_output_and_source_writes_reach_the_source(self) -> None:
        client, fake = self.serve(site_limits=SITE_LIMITS)
        applied = client.invoke(CONFIGURE, {"output": False}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        self.assertIs(self.state(client)["output"], False)
        applied = client.invoke(CONFIGURE, {"output": True}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        applied = client.invoke(CONFIGURE, {"source": "VOLT"}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        self.assertEqual(self.state(client)["source"], "VOLT")
        self.assertEqual(fake._sense, '"CURR"')                    # _set_mode_and_sense sets the opposite sense
        applied = client.invoke(CONFIGURE, {"voltage": 2.0}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        self.assertAlmostEqual(self.state(client)["voltage"], 2.0)

    def test_a_level_write_selects_its_source_function(self) -> None:
        client, _fake = self.serve(site_limits=SITE_LIMITS)
        self.assertEqual(self.state(client)["source"], "CURR")     # placeholder
        applied = client.invoke(CONFIGURE, {"voltage": 2.0}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        self.assertEqual(self.state(client)["source"], "VOLT")
        self.assertAlmostEqual(self.state(client)["voltage"], 2.0)
        applied = client.invoke(CONFIGURE, {"current": 0.02}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        self.assertEqual(self.state(client)["source"], "CURR")
        self.assertAlmostEqual(self.state(client)["current"], 0.02)

    def test_a_level_write_with_the_output_off_is_refused_without_a_mode_change(self) -> None:
        client, fake = self.serve(site_limits=SITE_LIMITS)
        applied = client.invoke(CONFIGURE, {"output": False}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        source_before = fake._source
        refused = client.invoke(CONFIGURE, {"voltage": 2.0}, **self.ids)
        self.assertEqual(refused["status"], "failed", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.DEVICE.PRECONDITION_UNMET")
        self.assertEqual(fake._source, source_before)
        state = self.state(client)
        self.assertNotIn("voltage", state)
        self.assertNotIn("current", state)
        self.assertNotIn("resistance", state)

    def test_the_safe_state_action_does_not_latch(self) -> None:
        client, fake = self.serve()
        stopped = client.invoke(SAFE_STATE, {}, **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertIs(stopped["output"]["output"], False)
        self.assertIs(fake._output, False)
        applied = client.invoke(CONFIGURE, {"output": True}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)

    def test_the_estop_sends_output_off_and_latches(self) -> None:
        client, fake = self.serve()
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(fake._written.count(":OUTP:STAT 0"), 2)   # the @estop and the safe-state action
        self.assertIs(fake._output, False)
        refused = client.invoke(CONFIGURE, {"output": True}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertIs(fake._output, False)

    def test_a_malformed_stop_readback_fails_the_estop(self) -> None:
        client, fake = self.serve()
        original = fake.ask

        def malformed(cmd):
            if cmd == ":OUTP:STAT?":
                return "not-a-number"                             # placeholder malformed reply
            return original(cmd)

        fake.ask = malformed
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertIs(stopped["output"]["safe_state_achieved"], False)
        self.assertIs(stopped["output"]["latched"], True)
        self.assertIs(fake._output, False)

    def test_a_failed_native_stop_write_fails_the_estop(self) -> None:
        client, fake = self.serve()
        original = fake.write

        def failing(cmd):
            if cmd == ":OUTP:STAT 0":
                raise RuntimeError("placeholder: VISA write failed")
            return original(cmd)

        fake.write = failing
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertIs(stopped["output"]["latched"], True)

    def test_closing_the_driver_closes_the_instrument(self) -> None:
        driver = load_driver(HERE, backend="fake")
        fake = driver.native
        driver.close()
        self.assertTrue(fake._closed)

    # Blocking regressions: these stay red until the stored-output envelope and reply format are repaired.
    # The stock gate assertion above is unchanged.
    def test_output_enable_cannot_bypass_unset_numeric_limits(self) -> None:
        client, fake = self.serve()
        client.invoke(CONFIGURE, {"output": False}, **self.ids)
        fake._voltage = 100.0  # placeholder stored level; no site overlay has authorized it
        receipt = client.invoke(CONFIGURE, {"output": True}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")
        self.assertFalse(fake._output)

    def test_source_change_cannot_select_an_unbounded_stored_level(self) -> None:
        client, fake = self.serve()
        fake._voltage = 100.0  # placeholder stored voltage in the inactive VOLT mode
        before = fake._source
        receipt = client.invoke(CONFIGURE, {"source": "VOLT"}, **self.ids)
        self.assertIn(receipt["status"], ("rejected", "failed"), receipt)
        self.assertEqual(fake._source, before)

    def test_scalar_sense_reply_is_not_reported_as_resistance(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        original = driver.native.ask
        driver.native.ask = lambda cmd: "0.25" if cmd == "READ?" else original(cmd)
        with self.assertRaises(DriverFailed):
            driver.resistance()


if __name__ == "__main__":
    unittest.main()

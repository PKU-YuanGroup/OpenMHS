"""Acceptance run of the TPR trigger driver: the gate, plus the cases specific to this package.

Add cases, never remove the check_driver call.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
TRIGGER = "x-cap.pcdshub.tpr_trigger.v1"
TICK_NS, TAP_NS = 70 / 13, 0.08          # pcdsdevices/tpr.py:15-16


def overlay():
    return json.loads((HERE / "site-limits.example.json").read_text())


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class TprTriggerCases(unittest.TestCase):
    def serve(self, *, limits=True):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=overlay() if limits else None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver.native

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_every_read_comes_from_the_fake_signals(self) -> None:
        client, _fake = self.serve()
        state = self.state(client)
        self.assertEqual(sorted(state), sorted(
            ["channel_enabled", "trigger_enabled", "eventrate", "delay_ns", "width_ns", "label"]))
        self.assertFalse(state["channel_enabled"])
        self.assertFalse(state["trigger_enabled"])
        self.assertEqual(state["eventrate"], 0.0)          # placeholder
        # derived as upstream: ticks * TPR_TICK_NS + taps * TPR_TAP_NS and ticks * TPR_TICK_NS (placeholder members)
        self.assertAlmostEqual(state["delay_ns"], 2 * TICK_NS + 3 * TAP_NS)
        self.assertAlmostEqual(state["width_ns"], 1 * TICK_NS)
        self.assertEqual(state["label"], "TPR channel")    # placeholder

    def test_the_extension_enables_and_disables_both_outputs(self) -> None:
        client, fake = self.serve()
        receipt = client.invoke(TRIGGER, {"enabled": True, "scope": "both"}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"channel_enabled": True, "trigger_enabled": True})
        state = self.state(client)
        self.assertTrue(state["channel_enabled"])
        self.assertTrue(state["trigger_enabled"])
        self.assertEqual(fake.enable_ch_cmd.value, 1)
        self.assertEqual(fake.enable_trg_cmd.value, 1)

        receipt = client.invoke(TRIGGER, {"enabled": False, "scope": "channel"}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        state = self.state(client)
        self.assertFalse(state["channel_enabled"])
        self.assertTrue(state["trigger_enabled"])

    def test_the_delay_write_sets_the_delay_setpoint(self) -> None:
        # ns_delay.put writes only delay_setpoint (_put_last); the read stays derived from ticks and taps, which only
        # the real IOC updates (the fake has no IOC, so the derived read does not follow the write here).
        client, fake = self.serve()
        receipt = client.write("main", {"delay_ns": 100.0}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(fake.delay_setpoint.value, 100.0)
        self.assertAlmostEqual(self.state(client)["delay_ns"], 2 * TICK_NS + 3 * TAP_NS)

    def test_the_width_write_sets_the_width_setpoint(self) -> None:
        client, fake = self.serve()
        receipt = client.write("main", {"width_ns": 50.0}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(fake.width_setpoint.value, 50.0)
        self.assertAlmostEqual(self.state(client)["width_ns"], 1 * TICK_NS)

    def test_a_failed_setpoint_status_is_a_failed_write(self) -> None:
        # utils.set_many would drop this failure inside ns_delay.put; the driver sets the member and keeps it.
        client, fake = self.serve()

        class _Failed:
            def wait(self, timeout=None):
                raise RuntimeError("placeholder: the set did not complete")

        fake.delay_setpoint.set = lambda value, timeout=None, settle_time=None: _Failed()
        receipt = client.write("main", {"delay_ns": 100.0}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)

    def test_the_derived_reads_follow_the_upstream_formulas(self) -> None:
        client, fake = self.serve()
        fake.delay_ticks.value, fake.delay_taps.value, fake.width_ticks.value = 13, 5, 26   # placeholders
        state = self.state(client)
        self.assertAlmostEqual(state["delay_ns"], 13 * TICK_NS + 5 * TAP_NS)
        self.assertAlmostEqual(state["width_ns"], 26 * TICK_NS)

    def test_without_the_operator_overlay_every_numeric_write_is_refused(self) -> None:
        client, _fake = self.serve(limits=False)
        for field in ("delay_ns", "width_ns"):
            receipt = client.write("main", {field: 1.0}, **self.ids)
            self.assertEqual(receipt["status"], "rejected", receipt)
            self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")

    def test_the_out_of_envelope_write_is_refused_without_native_effect(self) -> None:
        client, fake = self.serve()
        receipt = client.write("main", {"delay_ns": 200000.0}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(fake.delay_setpoint.value, 11.0)    # placeholder, unchanged

    def test_the_estop_reaches_the_native_disable_and_latches(self) -> None:
        client, fake = self.serve()
        self.assertEqual(client.invoke(TRIGGER, {"enabled": True, "scope": "both"}, **self.ids)["status"],
                         "completed")
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(fake.enable_ch_cmd.value, 0)
        self.assertEqual(fake.enable_trg_cmd.value, 0)
        refused = client.invoke(TRIGGER, {"enabled": True, "scope": "both"}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")

    def test_the_estop_is_unreached_while_an_enable_command_does_not_read_back_0(self) -> None:
        client, fake = self.serve()
        self.assertEqual(client.invoke(TRIGGER, {"enabled": True, "scope": "both"}, **self.ids)["status"],
                         "completed")
        fake.disable_trg = lambda: None          # the trigger enable put does not take effect
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        refused = client.invoke(TRIGGER, {"enabled": True, "scope": "both"}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")

    def test_the_fake_disable_runs_both_upstream_calls(self) -> None:
        _client, fake = self.serve()
        fake.enable()
        self.assertEqual((fake.enable_ch_cmd.value, fake.enable_trg_cmd.value), (1, 1))
        fake.disable()
        self.assertEqual((fake.enable_ch_cmd.value, fake.enable_trg_cmd.value), (0, 0))


if __name__ == "__main__":
    unittest.main()

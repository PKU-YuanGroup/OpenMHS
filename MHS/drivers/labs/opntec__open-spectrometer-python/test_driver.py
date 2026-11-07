"""Acceptance run of the TCD1304 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INTENSITY = "cap.measure.intensity.v1"
CONFIGURE = "cap.device.configure.v1"
REENABLE = "x-cap.opntec.power_on.v1"
DEFAULT_INTEGRATION_MS = 0.01   # the fake's start value (test data, not a device fact)
PEAK = 90.0                     # the fake's largest sample (test data, not a device fact)
OVERLAY_INTEGRATION_MS = 0.5    # a value inside site-limits.example.json


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class TCD1304Cases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def site(self):
        return str(HERE / "site-limits.example.json")

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def configure(self, client, **patch):
        return client.invoke(CONFIGURE, patch, **self.ids)

    def test_the_scalar_state_and_the_peak_capture(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertAlmostEqual(state["integration_time"], DEFAULT_INTEGRATION_MS)
        self.assertAlmostEqual(state["master_clock_frequency"], 2e6)
        measured = client.invoke(INTENSITY, {}, **self.ids)
        self.assertEqual(measured["status"], "completed")
        self.assertAlmostEqual(measured["output"]["intensity"], PEAK)
        self.assertAlmostEqual(measured["output"]["integration_ms"], DEFAULT_INTEGRATION_MS)
        self.assertIn("sampled_at", measured["output"])

    def test_the_integration_time_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, integration_time=OVERLAY_INTEGRATION_MS)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        refused_read = client.invoke(INTENSITY, {"integration_ms": OVERLAY_INTEGRATION_MS}, **self.ids)
        self.assertEqual(refused_read["error"]["mhs_code"], LIMITS_UNSET)
        self.assertAlmostEqual(self.state(client)["integration_time"], DEFAULT_INTEGRATION_MS)
        client = self.serve(self.site())
        applied = self.configure(client, integration_time=OVERLAY_INTEGRATION_MS)
        self.assertEqual(applied["status"], "completed")
        self.assertAlmostEqual(applied["output"]["applied"]["integration_time"], OVERLAY_INTEGRATION_MS)
        self.assertAlmostEqual(self.state(client)["integration_time"], OVERLAY_INTEGRATION_MS)
        measured = client.invoke(INTENSITY, {"integration_ms": 0.2}, **self.ids)
        self.assertEqual(measured["status"], "completed")
        self.assertAlmostEqual(measured["output"]["integration_ms"], 0.2)
        self.assertAlmostEqual(self.state(client)["integration_time"], 0.2)
        for value in (0.0005, 1.5):
            out_of_range = self.configure(client, integration_time=value)
            self.assertEqual(out_of_range["error"]["mhs_code"], ENVELOPE, value)
        self.assertAlmostEqual(self.state(client)["integration_time"], 0.2)

    def test_the_estop_powers_off_and_latches_the_setter(self) -> None:
        client = self.serve(self.site())
        estop = client.estop("test", **self.ids)
        self.assertEqual(estop["status"], "completed")
        self.assertEqual(estop["output"]["estop"], "engaged")
        measured = client.invoke(INTENSITY, {}, **self.ids)
        self.assertEqual(measured["status"], "completed")
        self.assertEqual(measured["output"]["intensity"], 0.0)   # powered off: the fake returns zeros
        refused = self.configure(client, integration_time=OVERLAY_INTEGRATION_MS)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def serve_driver(self):
        """A server over a driver this test keeps, so the fake's supply state and poweron calls are visible."""
        driver = load_driver(HERE, "fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        calls = []
        original = driver.native.poweron
        driver.native.poweron = lambda: (calls.append("poweron"), original())[1]   # counts the native calls
        return driver, client, calls

    def test_the_reenable_is_refused_while_latched_with_nothing_sent(self) -> None:
        driver, client, calls = self.serve_driver()
        client.estop("test", **self.ids)
        refused = client.invoke(REENABLE, {}, **self.ids)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ESTOP))
        self.assertEqual(calls, [])
        self.assertFalse(driver.native._powered)

    def test_the_reset_rearms_nothing_and_names_the_reenable(self) -> None:
        driver, client, calls = self.serve_driver()
        client.estop("test", **self.ids)
        receipt = client.reset(**self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)   # simulated: an agent may reset
        self.assertEqual(receipt["output"]["reenable"], REENABLE)
        self.assertIs(receipt["output"]["resumed"], False)
        self.assertEqual(calls, [])                                 # SAFE-042: the reset re-armed nothing
        self.assertFalse(driver.native._powered)
        self.assertEqual(client.invoke(INTENSITY, {}, **self.ids)["output"]["intensity"], 0.0)  # still off

    def test_the_reenable_powers_on_and_then_a_capture_reads_the_signal(self) -> None:
        driver, client, calls = self.serve_driver()
        client.estop("test", **self.ids)
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        enabled = client.invoke(REENABLE, {}, **self.ids)
        self.assertEqual(enabled["status"], "completed", enabled)
        self.assertEqual(enabled["output"], {"powered": True})
        self.assertEqual(calls, ["poweron"])
        self.assertTrue(driver.native._powered)
        self.assertAlmostEqual(client.invoke(INTENSITY, {}, **self.ids)["output"]["intensity"], PEAK)

    def test_the_reenable_is_declared_and_never_a_safe_state_action(self) -> None:
        client = self.serve()
        manifest = next(item for item in client.devices() if item["device_id"] == self.ids["device_id"])
        self.assertEqual(manifest["safety"]["estop"]["reenable"], REENABLE)
        self.assertNotIn(REENABLE, manifest["safety"]["safe_state"]["achieved_by"])


if __name__ == "__main__":
    unittest.main()

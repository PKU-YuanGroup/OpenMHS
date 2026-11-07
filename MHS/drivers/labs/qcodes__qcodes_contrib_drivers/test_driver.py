"""Acceptance run of the Thorlabs PM100D driver: the gate, plus the cases specific to this exemplar.

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
SITE_LIMITS = json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ThorlabsPM100DCases(unittest.TestCase):
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
        self.assertEqual(state["power"], 1.25e-3)        # placeholder
        self.assertIs(state["auto_range"], True)         # placeholder; the on/off mapping returns a bool
        self.assertEqual(state["averaging"], "1")        # placeholder raw AVER? reply (no parser upstream)
        self.assertEqual(state["current_range"], 1.0e-5)  # placeholder
        for unserved in ("wavelength", "beam_diameter", "current", "frequency"):
            self.assertNotIn(unserved, state)

    def test_the_power_range_waits_for_the_site_envelope(self) -> None:
        client, _fake = self.serve()
        refused = client.invoke(CONFIGURE, {"power_range": 5.0e-3}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")
        self.assertEqual(self.state(client)["power_range"], 2.0e-3)     # placeholder, unchanged

    def test_the_power_range_inside_and_outside_the_site_envelope(self) -> None:
        client, _fake = self.serve(site_limits=SITE_LIMITS)
        applied = client.invoke(CONFIGURE, {"power_range": 5.0e-3}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        self.assertEqual(self.state(client)["power_range"], 5.0e-3)
        refused = client.invoke(CONFIGURE, {"power_range": 0.5}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(self.state(client)["power_range"], 5.0e-3)

    def test_auto_range_is_written_through_the_parameter_set(self) -> None:
        client, fake = self.serve()
        applied = client.invoke(CONFIGURE, {"auto_range": False}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        self.assertIs(self.state(client)["auto_range"], False)
        self.assertIs(fake.auto_range.get(), False)

    def test_the_estop_sends_abor_and_latches(self) -> None:
        client, fake = self.serve()
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(fake._written, ["ABOR"])
        refused = client.invoke(CONFIGURE, {"auto_range": False}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertIs(fake.auto_range.get(), True)       # placeholder, unchanged

    def test_a_failed_native_set_is_a_failed_receipt(self) -> None:
        client, fake = self.serve()

        def rejected(value):
            raise RuntimeError("placeholder: VISA write failed")

        fake.auto_range.set = rejected
        receipt = client.invoke(CONFIGURE, {"auto_range": False}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)

    def test_closing_the_driver_closes_the_instrument(self) -> None:
        driver = load_driver(HERE, backend="fake")
        fake = driver.native
        driver.close()
        self.assertTrue(fake._closed)


if __name__ == "__main__":
    unittest.main()

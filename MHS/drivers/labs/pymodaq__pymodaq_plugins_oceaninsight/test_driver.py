"""Acceptance run of the Ocean Insight package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The numbers in the fake (16 pixels, 400 to 1000 nm, 100 ms) are
placeholder test data of the stand-in, not device facts.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INTENSITY = "cap.measure.intensity.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class OceanInsightCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def measure(self, client, **payload):
        return client.invoke(INTENSITY, payload, **self.ids)

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_scalar_reads(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        state = self.state(client)
        self.assertEqual(state["wavelength_min_nm"], 400.0)          # placeholder axis of the fake
        self.assertEqual(state["wavelength_max_nm"], 1000.0)         # placeholder axis of the fake
        self.assertEqual(state["pixel_count"], 16)                   # placeholder pixel count of the fake
        self.assertEqual(state["integration_time_ms"], 100.0)        # placeholder controller value of the fake

    def test_the_intensity_of_the_nearest_pixel(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = self.measure(client, wavelength_nm=520)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["intensity"], 250.0)       # placeholder intensity of pixel 520 nm

    def test_the_brightest_pixel_without_a_wavelength(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = self.measure(client)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["intensity"], 250.0)       # placeholder peak of the fake spectrum

    def test_the_wavelength_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.measure(client, wavelength_nm=520)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_example_overlay_narrows_the_wavelength(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for value in (399, 801):
            refused = self.measure(client, wavelength_nm=value)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["pixel_count"], 16)

    def test_the_integration_time_is_written_through_the_plugin_hook(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.state(client)["integration_time_ms"], 100.0)   # placeholder start value
        written = self.configure(client, integration_time_ms=250)
        self.assertEqual(written["status"], "completed", written)
        self.assertEqual(self.state(client)["integration_time_ms"], 250.0)

    def test_the_integration_time_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, integration_time_ms=250)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["integration_time_ms"], 100.0)   # the fake's placeholder, untouched

    def test_the_example_overlay_narrows_the_integration_time(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for value in (0, 1001):
            refused = self.configure(client, integration_time_ms=value)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["integration_time_ms"], 100.0)

    def test_the_estop_stops_the_averaging_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.measure(client, wavelength_nm=520)["status"], "completed")
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        safety = client.safety_status(device_id=self.ids["device_id"])
        self.assertTrue(safety["estop_engaged"])
        self.assertTrue(safety["estop"]["confirmed"])       # the native stop reached the fake plugin
        # cap.measure.intensity.v1 is a class whose verb is read, so the runtime still serves state reads
        # while the latch is engaged; it is not an actuating command and the latch does not gate it.
        self.assertEqual(self.state(client)["pixel_count"], 16)


if __name__ == "__main__":
    unittest.main()

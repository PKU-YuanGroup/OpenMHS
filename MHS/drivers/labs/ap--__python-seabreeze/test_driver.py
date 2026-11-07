"""Acceptance run of the python-seabreeze spectrometer package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INTENSITY = "cap.measure.intensity.v1"
PIXELS = 16                 # the fake's detector (test data, not a device fact)
PEAK_INTENSITY = 250.0      # the fake's brightest pixel (test data, not a device fact)
PIXEL_INTENSITY = 20.0      # the fake's second pixel (test data, not a device fact)
MAX_INTENSITY = 65535.0     # the fake's full scale (test data, not a device fact)
SERIAL_NUMBER = "FAKE0001"  # the fake's serial number (test data, not a device fact)
MODEL_NAME = "USB2000PLUS"  # the fake's model name (test data, not a device fact)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SeaBreezeSpectrometerCases(unittest.TestCase):
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

    def test_the_state_and_the_peak_intensity_measurement(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["pixel_count"], PIXELS)
        self.assertAlmostEqual(state["max_intensity"], MAX_INTENSITY)
        self.assertEqual(state["serial_number"], SERIAL_NUMBER)
        self.assertEqual(state["model_name"], MODEL_NAME)
        measured = client.invoke(INTENSITY, {}, **self.ids)
        self.assertEqual(measured["status"], "completed")
        self.assertAlmostEqual(measured["output"]["intensity"], PEAK_INTENSITY)
        self.assertIn("sampled_at", measured["output"])

    def test_the_wavelength_and_the_integration_time_wait_for_the_site(self) -> None:
        client = self.serve()
        for payload in ({"wavelength_nm": 520}, {"integration_ms": 10}):
            refused = client.invoke(INTENSITY, payload, **self.ids)
            self.assertEqual(refused["status"], "rejected", payload)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, payload)
        client = self.serve(self.site())
        measured = client.invoke(INTENSITY, {"wavelength_nm": 440}, **self.ids)
        self.assertEqual(measured["status"], "completed")
        self.assertAlmostEqual(measured["output"]["intensity"], PIXEL_INTENSITY)
        applied = client.invoke(INTENSITY, {"wavelength_nm": 520, "integration_ms": 10}, **self.ids)
        self.assertEqual(applied["status"], "completed")
        self.assertAlmostEqual(applied["output"]["intensity"], PEAK_INTENSITY)
        self.assertAlmostEqual(applied["output"]["integration_ms"], 10.0)
        for payload in ({"wavelength_nm": 150}, {"wavelength_nm": 1200},
                        {"integration_ms": 0.5}, {"integration_ms": 70000}):
            out_of_range = client.invoke(INTENSITY, payload, **self.ids)
            self.assertEqual(out_of_range["error"]["mhs_code"], ENVELOPE, payload)

    def test_the_integration_time_can_be_set(self) -> None:
        client = self.serve()
        refused = client.invoke("x-cap.ap.set_integration_time.v1", {"integration_ms": 10}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        client = self.serve(self.site())
        applied = client.invoke("x-cap.ap.set_integration_time.v1", {"integration_ms": 10}, **self.ids)
        self.assertEqual(applied["status"], "completed")
        self.assertAlmostEqual(applied["output"]["integration_ms"], 10.0)
        for value in (0.5, 70000):
            out_of_range = client.invoke("x-cap.ap.set_integration_time.v1", {"integration_ms": value}, **self.ids)
            self.assertEqual(out_of_range["error"]["mhs_code"], ENVELOPE, value)

    def test_the_estop_latches_the_device(self) -> None:
        client = self.serve(self.site())
        client.estop("test", **self.ids)
        refused = client.invoke("x-cap.ap.set_integration_time.v1", {"integration_ms": 10}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()

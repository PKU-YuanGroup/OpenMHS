"""Acceptance run of the TCD1304 linear CCD package: the gate, plus cases for this driver.

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

PIXELS = 16                    # the fake's detector (test data, not a device fact)
DARK_PIXELS = 3                # the fake's dark-pixel count (test data, not a device fact)
PEAK_INTENSITY = 1600.0        # the fake's brightest pixel (test data, not a device fact)
PIXEL_ONE_INTENSITY = 250.0    # the fake's pixel 1, nearest 440 nm (test data, not a device fact)
PIXEL_THREE_INTENSITY = 400.0  # the fake's pixel 3, nearest 520 nm (test data, not a device fact)
IDENTIFIER = "FAKE-TCD1304"    # the fake's identifier (test data, not a device fact)
SENSOR = "TCD1304"             # the fake's sensor name (test data, not a device fact)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class LinearCcdCases(unittest.TestCase):
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

    def test_the_reported_state(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["identifier"], IDENTIFIER)
        self.assertEqual(state["pixel_count"], PIXELS)
        self.assertEqual(state["dark_pixel_count"], DARK_PIXELS)
        self.assertEqual(state["sensor"], SENSOR)
        self.assertIn("PIXELS %d" % PIXELS, state["configuration"])
        self.assertIn("DARK %d" % DARK_PIXELS, state["configuration"])

    def test_the_measurement_waits_for_the_site(self) -> None:
        client = self.serve()
        for payload in ({"integration_ms": 10.0}, {"wavelength_nm": 440.0},
                        {"integration_ms": 10.0, "wavelength_nm": 440.0}):
            refused = client.invoke(INTENSITY, payload, **self.ids)
            self.assertEqual(refused["status"], "rejected", payload)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, payload)

    def test_the_peak_measurement_with_the_site(self) -> None:
        client = self.serve(self.site())
        measured = client.invoke(INTENSITY, {"integration_ms": 10.0}, **self.ids)
        self.assertEqual(measured["status"], "completed", measured)
        self.assertAlmostEqual(measured["output"]["intensity"], PEAK_INTENSITY)
        self.assertAlmostEqual(measured["output"]["integration_ms"], 10.0)
        self.assertIs(measured["output"]["saturated"], False)
        self.assertIn("sampled_at", measured["output"])

    def test_the_wavelength_measurement_with_the_site(self) -> None:
        client = self.serve(self.site())
        measured = client.invoke(INTENSITY, {"integration_ms": 10.0, "wavelength_nm": 440.0}, **self.ids)
        self.assertEqual(measured["status"], "completed", measured)
        self.assertAlmostEqual(measured["output"]["intensity"], PIXEL_ONE_INTENSITY)
        other = client.invoke(INTENSITY, {"integration_ms": 20.0, "wavelength_nm": 520.0}, **self.ids)
        self.assertEqual(other["status"], "completed", other)
        self.assertAlmostEqual(other["output"]["intensity"], PIXEL_THREE_INTENSITY)
        self.assertAlmostEqual(other["output"]["integration_ms"], 20.0)

    def test_the_out_of_envelope_inputs_are_refused(self) -> None:
        client = self.serve(self.site())
        for payload in ({"integration_ms": 0.5}, {"integration_ms": 70000.0},
                        {"wavelength_nm": 150.0}, {"wavelength_nm": 1200.0},
                        {"integration_ms": 10.0, "wavelength_nm": 1200.0}):
            refused = client.invoke(INTENSITY, payload, **self.ids)
            self.assertEqual(refused["status"], "rejected", payload)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, payload)

    def test_the_current_buffer_can_be_read_without_an_integration_time(self) -> None:
        client = self.serve(self.site())
        measured = client.invoke(INTENSITY, {}, **self.ids)
        self.assertEqual(measured["status"], "completed", measured)
        self.assertAlmostEqual(measured["output"]["intensity"], PEAK_INTENSITY)
        self.assertNotIn("integration_ms", measured["output"])

    def test_the_holdoff_setting(self) -> None:
        client = self.serve()
        refused = client.invoke("x-cap.drmcnelson.set_holdoff.v1", {"holdoff_us": 1000}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        client = self.serve(self.site())
        applied = client.invoke("x-cap.drmcnelson.set_holdoff.v1", {"holdoff_us": 1000}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        self.assertEqual(applied["output"]["holdoff_us"], 1000)
        for value in (-1, 1000001):
            out_of_range = client.invoke("x-cap.drmcnelson.set_holdoff.v1", {"holdoff_us": value}, **self.ids)
            self.assertEqual(out_of_range["status"], "rejected", value)
            self.assertEqual(out_of_range["error"]["mhs_code"], ENVELOPE, value)

    def test_the_estop_latches_the_device(self) -> None:
        client = self.serve(self.site())
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"]["estop"], "engaged")
        self.assertIs(stopped["output"]["latched"], True)
        status = client.safety_status(self.ids["device_id"])
        self.assertIs(status["estop_engaged"], True)
        refused = client.invoke("x-cap.drmcnelson.set_holdoff.v1", {"holdoff_us": 1000}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()

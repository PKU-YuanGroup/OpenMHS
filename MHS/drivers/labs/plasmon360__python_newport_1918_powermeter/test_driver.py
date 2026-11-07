"""Acceptance run of the Newport 1918-C package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
INTENSITY = "cap.measure.intensity.v1"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
SERIAL_NUMBER = "FAKE1918"      # the fake's serial number (test data, not a device fact)
MODEL_NUMBER = "1918-C"         # the fake's model number (test data, not a device fact)
WAVELENGTH_NM = 700             # the fake's starting wavelength (test data, not a device fact)
POWER = 1.234e-06               # the fake's power reading (test data, not a device fact)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Newport1918cCases(unittest.TestCase):
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

    def configure(self, client, value):
        return client.invoke("cap.device.configure.v1", {"wavelength_nm": value}, **self.ids)

    def test_the_state_and_the_reading_at_the_current_wavelength(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["serial_number"], SERIAL_NUMBER)
        self.assertEqual(state["model_number"], MODEL_NUMBER)
        self.assertEqual(state["wavelength_nm"], WAVELENGTH_NM)
        measured = client.invoke(INTENSITY, {}, **self.ids)
        self.assertEqual(measured["status"], "completed")
        self.assertAlmostEqual(measured["output"]["intensity"], POWER)
        self.assertIn("sampled_at", measured["output"])

    def test_the_wavelength_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = client.invoke(INTENSITY, {"wavelength_nm": 520}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["wavelength_nm"], WAVELENGTH_NM)

    def test_the_example_overlay_supplies_the_wavelength_range(self) -> None:
        client = self.serve(self.site())
        measured = client.invoke(INTENSITY, {"wavelength_nm": 520}, **self.ids)
        self.assertEqual(measured["status"], "completed")
        self.assertAlmostEqual(measured["output"]["intensity"], POWER)
        self.assertEqual(self.state(client)["wavelength_nm"], 520)
        for value in (300, 1200):
            refused = client.invoke(INTENSITY, {"wavelength_nm": value}, **self.ids)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["wavelength_nm"], 520)

    def test_the_configured_wavelength_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, 520)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["wavelength_nm"], WAVELENGTH_NM)

    def test_the_configured_wavelength_is_written_under_the_overlay(self) -> None:
        client = self.serve(self.site())
        applied = self.configure(client, 520)
        self.assertEqual(applied["status"], "completed")
        self.assertAlmostEqual(applied["output"]["applied"]["wavelength_nm"], 520)
        self.assertEqual(self.state(client)["wavelength_nm"], 520)
        for value in (300, 1200):
            refused = self.configure(client, value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed")
        latched = self.configure(client, 520)
        self.assertEqual(latched["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()

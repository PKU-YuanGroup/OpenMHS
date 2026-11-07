"""Acceptance run of the speck-lab-goniometer spectrometer package: the gate plus package-specific cases.

Add cases, never remove the ``check_driver`` call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SpeckLabSpectrometerCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def spectrum(self, client, wavelength_min, wavelength_max):
        return client.invoke("cap.measure.spectrum.v1", {
            "wavelength_min": wavelength_min,
            "wavelength_max": wavelength_max,
        }, **self.ids)

    def test_numeric_settings_wait_for_the_site(self) -> None:
        client = self.serve()
        self.assertEqual(self.state(client)["manual_exposure"], 10.0)          # fake test data
        refused = self.configure(client, manual_exposure=20.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        refused = self.spectrum(client, 400, 800)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["manual_exposure"], 10.0)

    def test_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, manual_exposure=12.5)["status"], "completed")
        self.assertEqual(self.configure(client, hardware_average=4)["status"], "completed")
        self.assertEqual(self.configure(client, output_hw_trigger_delay=-2.5)["status"], "completed")
        self.assertEqual(self.configure(client, input_hw_trigger_enabled=True)["status"], "completed")
        self.assertEqual(self.configure(client, use_amplitude_correction=True)["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["manual_exposure"], 12.5)
        self.assertEqual(state["hardware_average"], 4)
        self.assertEqual(state["output_hw_trigger_delay"], -2.5)
        self.assertTrue(state["input_hw_trigger_enabled"])
        self.assertFalse(state["input_hw_trigger_average_no_wait"])
        self.assertFalse(state["input_hw_trigger_falling_edge"])
        self.assertTrue(state["use_amplitude_correction"])

        refused = self.configure(client, manual_exposure=0.05)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["manual_exposure"], 12.5)

    def test_spectrum_is_filtered_to_the_requested_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        result = self.spectrum(client, 400, 800)
        self.assertEqual(result["status"], "completed", result)
        output = result["output"]
        self.assertTrue(output["wavelengths"])
        self.assertEqual(len(output["wavelengths"]), len(output["intensities"]))
        self.assertTrue(all(400 <= value <= 800 for value in output["wavelengths"]))
        self.assertIn("sampled_at", output)

    def test_estop_latches_the_device(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        refused = self.configure(client, manual_exposure=12.5)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        refused = self.spectrum(client, 400, 800)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()

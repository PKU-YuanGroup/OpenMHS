"""Acceptance run of the CSS45 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
SPECTRUM = "cap.measure.spectrum.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CSS45Cases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def measure(self, client, wavelength_min, wavelength_max):
        return client.invoke(SPECTRUM, {"wavelength_min": wavelength_min, "wavelength_max": wavelength_max},
                             **self.ids)

    def test_the_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["serial_number"], "000000000000000")
        self.assertEqual(state["firmware_version"], "1.58")
        self.assertEqual(state["status"], 0)
        self.assertEqual(state["temperature"], 24.5)
        self.assertEqual(state["cct"], 5000.0)
        self.assertEqual(state["photopic"], 50.0)
        self.assertEqual(state["par"], 0.5)
        self.assertEqual(state["radiometric_unit"], "W_PER_M2")
        self.assertEqual(state["last_integration_time"], 0.16)
        self.assertEqual((state["wavelength_start"], state["wavelength_end"]), (360.0, 830.0))

    def test_the_whole_spectrum(self) -> None:
        client = self.serve()
        receipt = self.measure(client, 360.0, 830.0)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(len(output["wavelengths"]), 288)
        self.assertEqual(len(output["intensities"]), 288)
        self.assertEqual((output["wavelengths"][0], output["wavelengths"][-1]), (360.0, 830.0))
        self.assertTrue(all(isinstance(value, float) for value in output["intensities"]))
        self.assertIn("sampled_at", output)

    def test_a_subrange_and_a_reversed_range(self) -> None:
        client = self.serve()
        for low, high in ((500.0, 600.0), (800.0, 500.0)):
            receipt = self.measure(client, low, high)
            self.assertEqual(receipt["status"], "completed", receipt)
            values = receipt["output"]["wavelengths"]
            lower, upper = sorted((low, high))
            self.assertTrue(values)
            self.assertTrue(all(lower <= value <= upper for value in values), (low, high, values[:3]))
            self.assertEqual(len(values), len(receipt["output"]["intensities"]))

    def test_a_range_between_pixels_returns_the_nearest_pixel(self) -> None:
        client = self.serve()
        receipt = self.measure(client, 361.0, 361.1)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(len(receipt["output"]["wavelengths"]), 1)

    def test_out_of_range_is_refused_by_the_runtime(self) -> None:
        client = self.serve()
        for low, high in ((359.0, 600.0), (500.0, 831.0)):
            refused = self.measure(client, low, high)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (low, high))

    def test_the_software_e_stop_latches(self) -> None:
        client = self.serve()
        client.estop("test", **self.ids)
        refused = self.measure(client, 400.0, 500.0)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()

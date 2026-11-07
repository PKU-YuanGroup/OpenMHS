"""Acceptance run of the NanoDrop 1000 package: the gate, plus cases specific to this driver.

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


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class NanoDropCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def spectrum(self, client, low=220, high=750):
        return client.invoke(
            "cap.measure.spectrum.v1",
            {"wavelength_min": low, "wavelength_max": high, "integration_ms": 20},
            **self.ids,
        )

    def test_the_wavelength_range_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.spectrum(client)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_blank_then_spectrum_with_the_example_overlay(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        blanked = client.invoke("x-cap.jordvl.take_blank.v1", {"integration_ms": 20}, **self.ids)
        self.assertEqual(blanked["status"], "completed")
        self.assertEqual(blanked["output"], {"blanked": True})
        measured = self.spectrum(client)
        self.assertEqual(measured["status"], "completed", measured)
        output = measured["output"]
        self.assertGreater(len(output["wavelengths"]), 0)
        self.assertEqual(len(output["wavelengths"]), len(output["intensities"]))
        self.assertTrue(all(220 <= value <= 750 for value in output["wavelengths"]))
        self.assertTrue(all(value == value for value in output["intensities"]))  # no NaN placeholder

    def test_the_integration_time_bound(self) -> None:
        client = self.serve()
        written = client.write("main", {"integration_time": 20}, **self.ids)
        self.assertEqual(written["status"], "completed")
        for value in (2, 65536):
            refused = client.write("main", {"integration_time": value}, **self.ids)
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)

    def test_the_integration_time_reaches_the_native_as_whole_milliseconds(self) -> None:
        # The upstream setter splits the value with & and >> (Code/nanodrop.py:79-81), which a float cannot pass:
        # the driver converts a whole-number value to int and refuses a fractional one before any native call.
        client = self.serve()
        written = client.write("main", {"integration_time": 25.0}, **self.ids)
        self.assertEqual(written["status"], "completed", written)
        refused = client.write("main", {"integration_time": 25.5}, **self.ids)
        self.assertEqual(refused["status"], "failed", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")
        blank = client.invoke("x-cap.jordvl.take_blank.v1", {"integration_ms": 20.5}, **self.ids)
        self.assertEqual(blank["status"], "failed", blank)
        self.assertEqual(blank["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")

    def test_the_fake_setter_refuses_a_float_like_the_upstream(self) -> None:
        from mhs.adapter import load_driver

        fake = load_driver(HERE, backend="fake").native
        with self.assertRaises(TypeError):
            fake.set_integration_time(20.0)
        fake.set_integration_time(20)

    def test_the_raw_frame_has_the_detector_length(self) -> None:
        client = self.serve()
        frame = client.invoke("x-cap.jordvl.raw_spectrum.v1", {}, **self.ids)
        self.assertEqual(frame["status"], "completed")
        self.assertEqual(len(frame["output"]["intensities"]), 2048)

    def test_a_reversed_range_is_refused_by_the_driver(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        refused = self.spectrum(client, 750, 220)
        self.assertEqual(refused["status"], "failed")
        self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")

    def test_the_estop_latches_and_refuses_the_next_call(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        refused = self.spectrum(client)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the Thorlabs beam profiler package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for
from mhs.driver import DriverFailed

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class BeamProfilerCases(unittest.TestCase):
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

    def test_the_reads_are_the_configured_state_and_the_sensor_geometry(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["sensor_pixels_x"], state["sensor_pixels_y"]), (64, 48))
        self.assertAlmostEqual(state["pixel_pitch_horizontal"], 5.5)
        self.assertAlmostEqual(state["pixel_pitch_vertical"], 5.5)
        self.assertEqual((state["roi_left"], state["roi_top"]), (0, 0))
        self.assertEqual((state["roi_width"], state["roi_height"]), (64, 48))
        self.assertAlmostEqual(state["exposure_time"], 40.0)
        self.assertAlmostEqual(state["wavelength"], 633.0)
        self.assertEqual((state["precision_mode"], state["binning"]), (1, 1))
        self.assertAlmostEqual(state["sensor_temperature"], 31.0)

    def test_exposure_and_wavelength_wait_for_the_site(self) -> None:
        client = self.serve()
        for patch in ({"exposure_time": 10.0}, {"wavelength": 600.0}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, patch)
        state = self.state(client)
        self.assertAlmostEqual(state["exposure_time"], 40.0)
        self.assertAlmostEqual(state["wavelength"], 633.0)

    def test_the_example_overlay_supplies_exposure_and_wavelength(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, exposure_time=10.0)["status"], "completed")
        self.assertEqual(self.configure(client, wavelength=600.0)["status"], "completed")
        state = self.state(client)
        self.assertAlmostEqual(state["exposure_time"], 10.0)
        self.assertAlmostEqual(state["wavelength"], 600.0)
        for patch in ({"exposure_time": 0.0001}, {"wavelength": 5000.0}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)
        state = self.state(client)
        self.assertAlmostEqual(state["exposure_time"], 10.0)
        self.assertAlmostEqual(state["wavelength"], 600.0)

    def test_precision_and_binning_use_the_sourced_allowed_sets(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, precision_mode=0)["status"], "completed")
        self.assertEqual(self.configure(client, binning=4)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["precision_mode"], state["binning"]), (0, 4))
        for patch in ({"precision_mode": 2}, {"binning": 3}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)
        state = self.state(client)
        self.assertEqual((state["precision_mode"], state["binning"]), (0, 4))

    def test_capture_without_an_artifact_store_refuses_before_measurement(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.sensing.image.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.NOT_READY", receipt)
        self.assertNotIn("image_ref", (receipt.get("output") or {}))

    def test_capture_without_a_store_does_not_apply_requested_exposure(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke("cap.sensing.image.v1",
                                {"width": 32, "height": 32, "exposure_ms": 5.0}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertAlmostEqual(self.state(client)["exposure_time"], 40.0)

    def test_safety_reset_cannot_reopen_a_closed_native_session(self) -> None:
        client = self.serve()
        client.estop("permanent session close", **self.ids)
        receipt = client.reset(**self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.RESET_REFUSED", receipt)

    def test_the_terminal_estop_is_declared_with_its_reason(self) -> None:
        client = self.serve()
        manifest = next(item for item in client.devices() if item["device_id"] == self.ids["device_id"])
        terminal = manifest["safety"]["estop"]["terminal"]
        self.assertIn("TLBC2.py:229-239", terminal)
        self.assertNotIn("reenable", manifest["safety"]["estop"])

    def test_reset_after_the_terminal_estop_keeps_the_latch_without_a_bridge_call(self) -> None:
        client = self.serve()
        terminal = next(item for item in client.devices()
                        if item["device_id"] == self.ids["device_id"])["safety"]["estop"]["terminal"]
        self.assertEqual(client.estop("terminal close", **self.ids)["status"], "completed")
        for _attempt in range(2):
            receipt = client.reset(**self.ids)
            self.assertEqual(receipt["status"], "rejected", receipt)
            details = receipt["error"]["details"]
            self.assertEqual(details["reason"], "terminal_estop", receipt)
            self.assertEqual(details["terminal"], terminal)
            self.assertIs(details["latched"], True)
        status = client.safety_status(device_id=self.ids["device_id"])
        self.assertIs(status["estop"]["engaged"], True)
        self.assertIs(status["estop"]["terminated"], True)
        refused = client.invoke("x-cap.thorlabs.measure_beam.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_no_reset_reopens_a_closed_session(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.estop("terminal close")
        self.assertTrue(driver.native.closed)
        self.assertEqual(driver.reset(), {})  # no reset hook: nothing native runs and nothing reopens
        self.assertTrue(driver.native.closed)
        with self.assertRaises(DriverFailed):
            driver.native.get_exposure_time([None])  # the closing state is irreversible

    def test_measure_beam_returns_the_analysis_values(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.thorlabs.measure_beam.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        expected = {
            "beam_width_4sigma_x", "beam_width_4sigma_y", "beam_width_4sigma_x_rotated",
            "beam_width_4sigma_y_rotated", "azimuth_angle", "ellipticity", "centroid_x", "centroid_y",
            "peak_intensity", "peak_position_x", "peak_position_y", "saturation", "saturated_pixel_ratio",
            "total_power_dbm", "sensor_temperature",
        }
        self.assertEqual(set(output), expected)
        self.assertGreater(output["beam_width_4sigma_x"], 0)
        self.assertIsInstance(output["peak_intensity"], int)
        self.assertAlmostEqual(output["sensor_temperature"], 31.0)
        self.assertAlmostEqual(output["centroid_x"], 3.5)

    def test_every_native_operation_refuses_after_terminal_close(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        native = driver.native
        cases = {
            "get_exposure_time": ([None],), "get_wavelength": ([None],),
            "get_precision_mode": ([None],), "get_binning": ([None],),
            "get_sensor_information": tuple([None] for _ in range(4)),
            "get_roi": tuple([None] for _ in range(4)),
            "get_beam_width_4_sigma": tuple([None] for _ in range(6)),
            "get_centroid": tuple([None] for _ in range(2)),
            "get_peak": tuple([None] for _ in range(3)),
            "get_saturation": tuple([None] for _ in range(2)),
            "get_power": ([None],), "get_temperature": ([None],),
            "set_exposure_time": (1.0,), "set_wavelength": (633.0,),
            "set_precision_mode": (1,), "set_binning": (1,), "set_roi": (0, 0, 32, 32),
            "request_new_measurement": (),
            "get_image": (bytearray(2448 * 2048 * 2), [None], [None], [None]),
        }
        native.close()
        for name, args in cases.items():
            with self.subTest(method=name), self.assertRaises(DriverFailed):
                getattr(native, name)(*args)

    def test_the_estop_closes_the_session_and_latches(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.estop("test")
        self.assertTrue(driver.native.closed)
        client = self.serve()
        client.estop("test", **self.ids)
        refused = client.invoke("cap.sensing.image.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the PICam package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import os
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PicamCases(unittest.TestCase):
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

    def test_the_reads_are_the_camera_parameters_and_the_first_roi(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["sensor_temperature_status"], "Unlocked")
        self.assertEqual(state["readout_stride"], 16)
        self.assertAlmostEqual(state["exposure_time"], 10.0)
        self.assertAlmostEqual(state["adc_speed"], 2.0)
        self.assertEqual((state["roi_x"], state["roi_width"], state["roi_x_binning"]), (0, 8, 1))
        self.assertEqual((state["roi_y"], state["roi_height"], state["roi_y_binning"]), (0, 8, 1))

    def test_the_exposure_and_roi_wait_for_the_site(self) -> None:
        client = self.serve()
        for patch in ({"exposure_time": 5.0}, {"roi_x": 3}, {"roi_width": 4}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, patch)
        self.assertAlmostEqual(self.state(client)["exposure_time"], 10.0)

    def test_the_example_overlay_supplies_the_ranges_and_the_writes_reach_the_fake(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, exposure_time=5.0)["status"], "completed")
        self.assertEqual(self.configure(client, roi_x=3, roi_width=4)["status"], "completed")
        state = self.state(client)
        self.assertAlmostEqual(state["exposure_time"], 5.0)
        self.assertEqual((state["roi_x"], state["roi_width"]), (3, 4))
        for patch in ({"exposure_time": 0.0001}, {"roi_x": -1}, {"roi_x_binning": 9}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)
        self.assertAlmostEqual(self.state(client)["exposure_time"], 5.0)

    def test_a_capture_returns_a_pgm_file_and_its_size(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.sensing.image.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["width"], output["height"]), (8, 8))
        path = output["image_ref"]
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        self.assertTrue(os.path.isfile(path))
        with open(path, "rb") as stream:
            self.assertEqual(stream.read(13), b"P5\n8 8\n65535\n")

    def test_a_capture_under_the_example_overlay_applies_the_inputs(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke("cap.sensing.image.v1",
                                {"width": 16, "height": 16, "exposure_ms": 2.5}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual((receipt["output"]["width"], receipt["output"]["height"]), (8, 8))
        self.assertAlmostEqual(receipt["output"]["exposure_ms"], 2.5)
        self.addCleanup(lambda: os.path.exists(receipt["output"]["image_ref"])
                        and os.unlink(receipt["output"]["image_ref"]))
        state = self.state(client)
        self.assertEqual((state["roi_width"], state["roi_height"]), (16, 16))
        self.assertAlmostEqual(state["exposure_time"], 2.5)

    def test_the_estop_closes_the_camera_and_latches(self) -> None:
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

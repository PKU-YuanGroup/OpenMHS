"""Acceptance run of the OpenFlexure Microscope package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): its ``_commands`` list is
what reached the "microscope".  Nothing here ran on a real microscope.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = str(HERE / "site-limits.example.json")
CAPABILITY = "x-cap.rwb27.autofocus_scan.v1"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"

#: placeholder test input (microsteps); inside site-limits.example.json
SCAN = [-160.0, -80.0, 0.0, 80.0, 160.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MicroscopeCases(unittest.TestCase):
    def serve(self, site_limits=None):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        self.microscope = driver.native                     # the fake Microscope
        self.client = client_for(server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        del self.microscope._commands[:]
        return self.client

    def scan(self, z_positions):
        return self.client.invoke(CAPABILITY, {"z_positions": z_positions}, **self.ids)

    def state(self):
        return self.client.read("main", **self.ids)["state"]

    def set_zoom(self, zoom):
        return self.client.write("main", {"zoom": zoom}, **self.ids)

    def calls(self, name):
        return [command for command in self.microscope._commands if command == name]

    # -- the reads ------------------------------------------------------------------------------------------
    def test_the_reads_report_the_camera_state(self) -> None:
        self.serve()
        state = self.state()
        self.assertEqual(state["zoom"], 1.0)
        self.assertEqual(state["resolution"], [640, 480])
        self.assertEqual(state["shutter_speed"], 10000)
        self.assertEqual(state["awb_mode"], "auto")
        self.microscope._set_shutter_speed(2500)
        self.microscope._set_awb_mode("off")
        state = self.state()
        self.assertEqual((state["shutter_speed"], state["awb_mode"]), (2500, "off"))

    # -- the write ------------------------------------------------------------------------------------------
    def test_the_zoom_write_reaches_the_camera_and_is_observable(self) -> None:
        self.serve()
        receipt = self.set_zoom(2.0)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(self.calls("zoom"), ["zoom"])
        self.assertAlmostEqual(self.microscope.zoom, 2.0, places=9)
        self.assertAlmostEqual(self.state()["zoom"], 2.0, places=9)
        self.assertEqual(self.set_zoom(4.0)["status"], "completed")
        self.assertAlmostEqual(self.state()["zoom"], 4.0, places=9)

    def test_the_zoom_floor_is_the_documented_one(self) -> None:
        self.serve()
        refused = self.set_zoom(0.5)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE))
        self.assertEqual(refused["error"]["details"]["bound"], 1.0)
        self.assertEqual(self.calls("zoom"), [])              # the camera saw nothing
        self.assertEqual(self.set_zoom(1.0)["status"], "completed")

    # -- the autofocus scan ---------------------------------------------------------------------------------
    def test_the_scan_waits_for_the_site(self) -> None:
        self.serve()                                         # no overlay: the bounds are operator_required
        refused = self.scan(SCAN)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", LIMITS_UNSET))
        self.assertEqual(self.calls("autofocus"), [])

    def test_the_scan_reaches_the_upstream_autofocus(self) -> None:
        self.serve(OVERLAY)
        receipt = self.scan(SCAN)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["positions"], SCAN)
        self.assertEqual(len(output["sharpnesses"]), len(SCAN))
        self.assertEqual(output["best_position"], 0.0)       # the sharpness curve peaks at the current position
        self.assertEqual(self.calls("autofocus"), ["autofocus"])
        self.assertEqual(self.microscope.stage.position, [0.0, 0.0, 0.0])   # the scan ends at the best position

    def test_the_scan_envelope_comes_from_the_site(self) -> None:
        self.serve(OVERLAY)
        refused = self.scan([0.0, 2000.0])                   # the example overlay allows +-1280 microsteps
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE))
        self.assertEqual(refused["error"]["details"]["bound"], 1280)
        self.assertEqual(self.calls("autofocus"), [])

    def test_an_empty_scan_is_refused(self) -> None:
        self.serve(OVERLAY)
        refused = self.scan([])
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("failed", INPUT_INVALID))
        self.assertEqual(self.calls("autofocus"), [])

    # -- stop and e-stop ------------------------------------------------------------------------------------
    def test_the_estop_closes_the_camera_and_the_stage_and_latches(self) -> None:
        self.serve(OVERLAY)
        self.client.estop("test", **self.ids)
        self.assertEqual(self.calls("close"), ["close"])
        self.assertTrue(self.microscope._closed)
        self.assertTrue(self.microscope.camera.closed)
        for refused in (self.scan(SCAN), self.set_zoom(2.0)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual((len(self.calls("autofocus")), len(self.calls("zoom")), len(self.calls("close"))), (0, 0, 1))


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the ScanImage TCP/IP client package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): its ``calls`` list is
what reached the "client".  Nothing here ran on a ScanImage server.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = str(HERE / "site-limits.example.json")
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
SCAN_ZOOM = "hSI.hRoiManager.scanZoomFactor"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ScanimageCases(unittest.TestCase):
    def serve(self, site_limits=None):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        self.client_object = driver.native                  # the fake ScanimageTcpipClient
        self.client = client_for(server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        del self.client_object.calls[:]
        return self.client

    def state(self):
        return self.client.read("main", **self.ids)["state"]

    def set_zoom(self, value):
        return self.client.write("main", {"scan_zoom_factor": value}, **self.ids)

    def calls(self, name):
        return [call for call in self.client_object.calls if call[0] == name]

    # -- the read --------------------------------------------------------------------------------------------
    def test_the_read_reports_the_server_property(self) -> None:
        self.serve()
        self.assertEqual(self.state()["scan_zoom_factor"], 1.0)       # placeholder start value
        self.assertEqual(self.calls("si_get"), [("si_get", SCAN_ZOOM)])

    # -- the write -------------------------------------------------------------------------------------------
    def test_the_write_waits_for_the_site(self) -> None:
        self.serve()                                                    # no overlay: operator_required
        refused = self.set_zoom(2.0)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", LIMITS_UNSET))
        self.assertEqual(self.calls("si_set"), [])
        self.assertEqual(self.state()["scan_zoom_factor"], 1.0)

    def test_the_zoom_write_reaches_the_client_and_is_observable(self) -> None:
        self.serve(OVERLAY)
        receipt = self.set_zoom(4.0)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(self.calls("si_set"), [("si_set", SCAN_ZOOM, 4.0)])
        self.assertEqual(self.client_object.values[SCAN_ZOOM], 4.0)
        self.assertEqual(self.state()["scan_zoom_factor"], 4.0)

    def test_the_zoom_envelope_comes_from_the_site(self) -> None:
        self.serve(OVERLAY)
        refused = self.set_zoom(0.5)                                    # the example overlay starts at 1
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE))
        self.assertEqual(self.calls("si_set"), [])

    # -- no action ----------------------------------------------------------------------------------------------
    def test_no_action_can_start_an_acquisition(self) -> None:
        # hSI.startFocus starts a laser scan that close(), the e-stop, cannot stop: a model review removed it.
        self.serve()
        capabilities = [cap["capability_id"] for cap in self.client.devices()[0]["capabilities"]]
        self.assertNotIn("x-cap.histedlab.start_focus.v1", capabilities)
        self.assertFalse([cap for cap in capabilities if cap.startswith("x-cap.")], capabilities)

    # -- safety ----------------------------------------------------------------------------------------------
    def test_the_estop_closes_the_socket_and_latches(self) -> None:
        self.serve(OVERLAY)
        self.client.estop("test", **self.ids)
        self.assertEqual(self.calls("close"), [("close",)])
        self.assertTrue(self.client_object.closed)
        self.assertEqual(self.set_zoom(2.0)["error"]["mhs_code"], ESTOP)
        self.assertEqual((len(self.calls("si_set")), len(self.calls("close"))), (0, 1))


if __name__ == "__main__":
    unittest.main()

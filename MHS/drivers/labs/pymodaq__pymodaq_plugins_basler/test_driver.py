"""Acceptance run of the Basler camera package: the gate, plus cases for this driver.

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


class BaslerCases(unittest.TestCase):
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

    def test_the_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["model_name"], "acA1920-40gm")           # placeholder test data
        self.assertEqual(state["detector_size"], [1280, 960])          # placeholder test data
        self.assertEqual((state["roi_x0"], state["roi_x1"]), (0, 1280))  # placeholder test data
        self.assertEqual((state["roi_y0"], state["roi_y1"]), (0, 960))   # placeholder test data
        self.assertEqual((state["binning_x"], state["binning_y"]), (1, 1))  # placeholder test data
        self.assertEqual(state["exposure_ms"], 10.0)                   # placeholder test data (10000 us)
        self.assertEqual(state["gain"], 1.0)                           # placeholder test data
        self.assertEqual(state["frame_rate"], 15.0)                    # placeholder test data
        self.assertEqual(state["pixel_format"], "Mono12")              # placeholder test data
        self.assertFalse(state["grabbing"])

    def test_the_roi_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, roi_x0=5)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["roi_x0"], 0)               # placeholder test data, untouched

    def test_the_example_overlay_supplies_the_roi_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        applied = self.configure(client, roi_x0=5, roi_x1=15, roi_y0=2, roi_y1=12, binning_x=2, binning_y=2)
        self.assertEqual(applied["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["roi_x0"], state["roi_x1"]), (5, 15))
        self.assertEqual((state["roi_y0"], state["roi_y1"]), (2, 12))
        self.assertEqual((state["binning_x"], state["binning_y"]), (2, 2))
        refused = self.configure(client, roi_x0=11)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["roi_x0"], 5)

    def test_the_clear_roi_action_restores_the_detector(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, roi_x0=5, roi_x1=15, roi_y0=2, roi_y1=12)["status"], "completed")
        cleared = client.invoke("x-cap.pymodaq.clear_roi.v1", {}, **self.ids)
        self.assertEqual(cleared["status"], "completed")
        self.assertEqual(cleared["output"], {"roi": [0, 1280, 0, 960, 1, 1]})  # placeholder detector size
        state = self.state(client)
        self.assertEqual((state["roi_x0"], state["roi_x1"]), (0, 1280))
        self.assertEqual((state["roi_y0"], state["roi_y1"]), (0, 960))

    def test_the_grabbing_actions_and_the_estop(self) -> None:
        client = self.serve()
        started = client.invoke("x-cap.pymodaq.start_grabbing.v1", {}, **self.ids)
        self.assertEqual(started["status"], "completed")
        self.assertEqual(started["output"], {"grabbing": True})
        self.assertTrue(self.state(client)["grabbing"])
        stopped = client.invoke("x-cap.pymodaq.stop_grabbing.v1", {}, **self.ids)
        self.assertEqual(stopped["output"], {"grabbing": False})
        self.assertFalse(self.state(client)["grabbing"])

        client.invoke("x-cap.pymodaq.start_grabbing.v1", {}, **self.ids)
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["grabbing"])
        refused = client.invoke("x-cap.pymodaq.start_grabbing.v1", {}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()

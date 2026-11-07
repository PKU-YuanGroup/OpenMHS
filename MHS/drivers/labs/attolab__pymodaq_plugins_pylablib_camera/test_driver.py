"""Acceptance run of the pylablib camera package: the gate, plus cases for what is specific to this driver.

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


class PylablibCameraCases(unittest.TestCase):
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

    def test_the_reads_describe_the_fake_camera(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["camera_list"], ["fake-thorlabs-serial"])
        self.assertEqual(state["camera_info"], "fake-thorlabs-camera")
        self.assertEqual(state["detector_size"], [1280, 1024])
        self.assertEqual((state["roi_x0"], state["roi_x1"], state["roi_y0"], state["roi_y1"]), (0, 640, 0, 480))
        self.assertEqual((state["binning_x"], state["binning_y"]), (1, 1))
        self.assertAlmostEqual(state["exposure"], 0.01)

    def test_the_writes_wait_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, exposure=0.05)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertAlmostEqual(self.state(client)["exposure"], 0.01)      # the fake's placeholder, untouched

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, exposure=0.05)["status"], "completed")
        self.assertAlmostEqual(self.state(client)["exposure"], 0.05)
        self.assertEqual(self.configure(client, roi_x1=320, roi_y1=240)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["roi_x1"], state["roi_y1"]), (320, 240))
        self.assertEqual(self.configure(client, binning_x=2, binning_y=2)["status"], "completed")
        self.assertEqual((self.state(client)["binning_x"], self.state(client)["binning_y"]), (2, 2))
        refused = self.configure(client, exposure=10.01)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_estop_stops_the_camera_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        client.estop("test", **self.ids)
        refused = self.configure(client, exposure=0.05)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()

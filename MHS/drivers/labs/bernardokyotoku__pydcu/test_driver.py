"""Acceptance run of the uEye camera package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.
"""

import os
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


class UEyeCameraCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def test_the_aoi_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, width=640)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        state = self.state(client)
        self.assertEqual((state["width"], state["height"]), (1024, 768))
        self.assertEqual((state["image_x"], state["image_y"]), (0, 0))

    def test_the_example_overlay_supplies_the_aoi_bounds(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch, field, value in (
            ({"width": 640}, "width", 640),
            ({"height": 480}, "height", 480),
            ({"image_x": 10}, "image_x", 10),
            ({"image_y": 20}, "image_y", 20),
        ):
            receipt = self.configure(client, **patch)
            self.assertEqual(receipt["status"], "completed", receipt)
            self.assertEqual(self.state(client)[field], value)
        refused = self.configure(client, width=1281)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["width"], 640)

    def test_the_capture_reports_the_aoi_and_a_bmp(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, width=640, height=480)["status"], "completed")
        receipt = client.invoke("cap.sensing.image.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["width"], output["height"]), (640, 480))
        self.assertEqual(output["media_type"], "image/bmp")
        path = output["image_ref"]
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        self.assertTrue(os.path.isfile(path))
        with open(path, "rb") as stream:
            self.assertEqual(stream.read(2), b"BM")

    def test_the_estop_closes_the_camera_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.sensing.image.v1", {}, **self.ids)["status"], "completed")
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        refused = client.invoke("cap.sensing.image.v1", {}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()

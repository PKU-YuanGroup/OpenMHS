"""Acceptance run of the DTMicroscope package: the gate, plus cases for what is specific to this driver.

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


class DtmicroscopeCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def overlay(self):
        return str(HERE / "site-limits.example.json")

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["detectors"], ["flu_camera", "ceta_camera", "scan", "super_x"])
        self.assertEqual(state["microscope_status"], "Idle")                    # the fake's canned reply
        self.assertEqual(state["stage"], [0.0, 0.0, 0.0, 0.0, 0.0])           # the fake's start position
        self.assertEqual(state["vacuum"], 1.0)                                  # the fake's canned reply

    def test_the_writes_wait_for_the_site(self) -> None:
        client = self.serve()
        for patch in ({"stage": [0.0, 0.0, 0.0, 0.0, 0.0]}, {"beam_position": [1.0, 1.0]}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, refused)
        self.assertEqual(self.state(client)["stage"], [0.0, 0.0, 0.0, 0.0, 0.0])

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(self.overlay())
        moved = self.configure(client, stage=[0.0005, -0.0005, 0.0, 2.0, -2.0])
        self.assertEqual(moved["status"], "completed", moved)
        self.assertEqual(self.state(client)["stage"], [0.0005, -0.0005, 0.0, 2.0, -2.0])
        shifted = self.configure(client, beam_position=[10.0, -10.0])
        self.assertEqual(shifted["status"], "completed", shifted)
        self.assertEqual(self.state(client)["beam_position"], [10.0, -10.0])
        for patch in ({"stage": [0.01, 0.0, 0.0, 0.0, 0.0]}, {"beam_position": [101.0, 0.0]}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, refused)
        self.assertEqual(self.state(client)["stage"], [0.0005, -0.0005, 0.0, 2.0, -2.0])

    def test_the_image_is_a_pgm_artifact(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.imaging.capture.v1", {"camera": "flu_camera"}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["width"], output["height"], output["channel"]), (4, 4, "flu_camera"))
        path = output["image_ref"]
        self.addCleanup(os.unlink, path)
        with open(path, "rb") as stream:
            self.assertTrue(stream.read(2) == b"P5")
        self.assertEqual(self.state(client)["detectors"][0], "flu_camera")

    def test_the_spectrum_echoes_the_detector(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.pycroscopy.acquire_spectrum.v1", {"device": "super_x"}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["device"], "super_x")
        self.assertEqual(len(output["intensities"]), 8)
        self.assertIn("sampled_at", output)

    def test_the_estop_closes_the_client_and_latches(self) -> None:
        client = self.serve()
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        refused = client.invoke("cap.imaging.capture.v1", {"camera": "flu_camera"}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the Basler camera package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.artifacts import LocalArtifactStore
from mhs.client import InProcessTransport, MHSClient
from mhs.pixels import PNG_SIGNATURE
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class BaslerCases(unittest.TestCase):
    def serve(self, site_limits=None, artifact_store=None):
        server = load(HERE, backend="fake", site_limits=site_limits, artifact_store=artifact_store)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server))
        self.addCleanup(client.close)
        hello = client.hello()
        device_id = hello["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_reads_are_the_camera_metadata_and_last_mean(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["camera_model"], "Emulation")
        self.assertEqual(state["serial_number"], "00000000")
        self.assertEqual(state["user_defined_name"], "fake-camera")
        self.assertEqual(state["image_shape"], [8, 8])
        self.assertEqual((state["pixel_level_min"], state["pixel_level_max"]), (0, 255))
        self.assertEqual(state["active_format"], "Mono8")
        self.assertEqual(state["payload_size"], 64)
        self.assertEqual(state["grab_timeout"], 5000)
        self.assertEqual(state["exposure_time"], 1000.0)
        self.assertEqual(state["mean"], 0.0)

    def test_exposure_write_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = client.invoke("cap.device.configure.v1", {"exposure_time": 5.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, refused)
        self.assertEqual(self.state(client)["exposure_time"], 1000.0)

    def test_example_overlay_supplies_the_exposure_range(self) -> None:
        client = self.serve(site_limits=str(HERE / "site-limits.example.json"))
        receipt = client.invoke("cap.device.configure.v1", {"exposure_time": 5.0}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(self.state(client)["exposure_time"], 5.0)

    def test_capture_returns_a_png_artifact(self) -> None:
        client = self.serve(artifact_store=LocalArtifactStore())
        receipt = client.invoke("cap.sensing.image.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["width"], output["height"]), (8, 8))
        self.assertEqual(output["media_type"], "image/png")
        self.assertTrue(output["image_ref"].startswith("mhs+artifact://"), output)
        artifact = client.read_artifact(output["image_ref"], session_id=client.session_id)
        self.assertTrue(artifact["data"].startswith(PNG_SIGNATURE), artifact["descriptor"])
        self.assertGreater(self.state(client)["mean"], 0.0)

    def test_capture_without_an_artifact_store_refuses_before_staging(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.sensing.image.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.NOT_READY", receipt)
        self.assertEqual(self.state(client)["mean"], 0.0)

    def test_estop_reaches_the_pylon_stop_and_latches(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.estop("test")
        self.assertEqual(driver.native.camera_object.stop_calls, 1)
        client = self.serve()
        client.estop("test", **self.ids)
        refused = client.invoke("cap.sensing.image.v1", {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)


if __name__ == "__main__":
    unittest.main()

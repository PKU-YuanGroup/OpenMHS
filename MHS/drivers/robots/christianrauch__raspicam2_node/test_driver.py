"""Acceptance and repository-specific cases for the raspicam2_node package."""

import unittest
from pathlib import Path

from mhs.adapter import load
from mhs.artifacts import LocalArtifactStore
from mhs.client import InProcessTransport, MHSClient
from mhs.driver import close_server
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent
IMAGE_CAP = "cap.sensing.image.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ImageCapture(unittest.TestCase):
    """Exercise the adapter and stock server with the package's ROS-free fake peer."""

    def open(self, **options):
        store = LocalArtifactStore()
        self.addCleanup(store.close)
        server = load(HERE, backend="fake", artifact_store=store, options=options)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server))
        client.hello()
        self.addCleanup(client.close)
        device = next(iter(server.devices))
        client.open_session([device], capabilities=[IMAGE_CAP])
        return store, server, client, device

    def test_capture_returns_a_session_bound_png_artifact(self) -> None:
        store, _server, client, device = self.open()
        receipt = client.invoke(IMAGE_CAP, {}, device_id=device)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(set(output), {"image_ref", "width", "height", "media_type"}, output)
        self.assertEqual((output["width"], output["height"]), (2, 2), output)
        self.assertEqual(output["media_type"], "image/png", output)
        self.assertTrue(output["image_ref"].startswith("mhs+artifact://"), output)
        data = client.read_artifact(output["image_ref"], session_id=client.session_id)
        self.assertEqual(data["descriptor"]["media_type"], "image/png", data)
        self.assertTrue(data["data"], data)
        self.assertEqual(len(store._grants), 1)

    def test_geometry_reads_come_from_camera_info(self) -> None:
        _store, _server, client, device = self.open()
        state = client.read("camera", device_id=device)["state"]
        self.assertEqual(state, {"frame_id": "camera", "width": 2, "height": 2}, state)

    def test_malformed_image_reply_has_no_artifact(self) -> None:
        store, _server, client, device = self.open(malformed_image=True)
        receipt = client.invoke(IMAGE_CAP, {}, device_id=device)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertNotIn("artifacts", receipt)
        self.assertIsNone(receipt["output"])
        self.assertEqual(store._grants, {})


if __name__ == "__main__":
    unittest.main()

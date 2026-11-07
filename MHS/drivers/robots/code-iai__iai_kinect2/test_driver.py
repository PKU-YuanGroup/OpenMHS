"""Acceptance and repository-specific cases for the iai_kinect2 package."""

import unittest
from pathlib import Path

from mhs.adapter import load
from mhs.artifacts import LocalArtifactStore
from mhs.client import InProcessTransport, MHSClient
from mhs.driver import close_server
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent
IMAGE_CAP = "cap.sensing.image.v1"
IMAGE_TOPICS = {
    "color": "/kinect2/sd/image_color_rect",
    "depth": "/kinect2/sd/image_depth_rect",
    "ir": "/kinect2/sd/image_ir",
}


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
        fake = server.devices[device].bridge.native
        return store, server, client, device, fake

    def capture(self, client, device, camera):
        return client.invoke(IMAGE_CAP, {"camera": camera}, device_id=device)

    def test_color_capture_returns_a_session_bound_png_artifact(self) -> None:
        store, _server, client, device, _fake = self.open()
        receipt = self.capture(client, device, "color")
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(set(output), {"image_ref", "width", "height", "media_type"}, output)
        self.assertEqual((output["width"], output["height"]), (4, 2), output)
        self.assertEqual(output["media_type"], "image/png", output)
        self.assertTrue(output["image_ref"].startswith("mhs+artifact://"), output)
        data = client.read_artifact(output["image_ref"], session_id=client.session_id)
        self.assertEqual(data["descriptor"]["media_type"], "image/png", data)
        self.assertTrue(data["data"], data)
        self.assertEqual(len(store._grants), 1)

    def test_geometry_reads_come_from_the_sd_camera_info(self) -> None:
        _store, _server, client, device, _fake = self.open()
        state = client.read("camera", device_id=device)["state"]
        self.assertEqual(state, {"frame_id": "kinect2_ir_optical_frame", "width": 4, "height": 2}, state)

    def test_each_camera_subscribes_to_its_declared_topic(self) -> None:
        _store, _server, client, device, fake = self.open()
        for camera, topic in IMAGE_TOPICS.items():
            before = len(fake.subscribed_topics)
            receipt = self.capture(client, device, camera)
            self.assertEqual(receipt["status"], "completed", receipt)
            self.assertIn(topic, fake.subscribed_topics[before:], fake.subscribed_topics)

    def test_depth_and_ir_preserve_16_bit_samples_as_png(self) -> None:
        _store, _server, client, device, _fake = self.open()
        for camera in ("depth", "ir"):
            receipt = self.capture(client, device, camera)
            self.assertEqual(receipt["status"], "completed", receipt)
            self.assertEqual(receipt["output"]["media_type"], "image/png", receipt)
            self.assertEqual((receipt["output"]["width"], receipt["output"]["height"]), (4, 2), receipt)

    def test_malformed_step_fails_without_an_artifact(self) -> None:
        store, _server, client, device, _fake = self.open(malformed_step=True)
        receipt = self.capture(client, device, "color")
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertNotIn("artifacts", receipt)
        self.assertIsNone(receipt["output"])
        self.assertEqual(store._grants, {})

    def test_missing_ros1_header_sequence_fails_without_an_artifact(self) -> None:
        store, _server, client, device, _fake = self.open(missing_header_seq=True)
        receipt = self.capture(client, device, "depth")
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertNotIn("artifacts", receipt)
        self.assertIsNone(receipt["output"])
        self.assertEqual(store._grants, {})

    def test_unknown_camera_is_rejected_before_an_image_subscription(self) -> None:
        _store, _server, client, device, fake = self.open()
        before = list(fake.subscribed_topics)
        receipt = client.invoke(IMAGE_CAP, {"camera": "elsewhere"}, device_id=device)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual([topic for topic in fake.subscribed_topics[len(before):]
                          if topic in IMAGE_TOPICS.values()], [])

    def test_extra_capture_controls_are_rejected_before_the_wire(self) -> None:
        _store, _server, client, device, fake = self.open()
        before = list(fake.subscribed_topics)
        receipt = client.invoke(IMAGE_CAP, {"camera": "color", "width": 640}, device_id=device)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual([topic for topic in fake.subscribed_topics[len(before):]
                          if topic in IMAGE_TOPICS.values()], [])


if __name__ == "__main__":
    unittest.main()

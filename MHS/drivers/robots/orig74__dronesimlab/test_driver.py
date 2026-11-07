"""Acceptance run of the DroneSimLab UE4 camera package: the gate plus image cases."""

import time
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.artifacts import LocalArtifactStore
from mhs.client import InProcessTransport, MHSClient
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

    def capture(self, camera: str, **options):
        store, server, client, device = self.open(**options)
        receipt = client.invoke(IMAGE_CAP, {"camera": camera}, device_id=device)
        return store, server, client, receipt

    def test_color_capture_returns_a_session_bound_png_artifact(self) -> None:
        store, _server, client, receipt = self.capture("color")
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
        source = data["descriptor"]["x-vendor"]["openmhs.ros_image"]
        self.assertEqual(source["camera"], "color")
        self.assertEqual(source["topic"], "/rgb_camera_0")
        self.assertEqual(source["type"], "sensor_msgs/Image")
        self.assertEqual(source["ros_version"], 1)
        # The bridge sets no header on the color stream (ue4_bridge.py:53-55); only the
        # colorized depth _rgb8 image carries frame_id camera_rgb (ue4_bridge.py:64).
        self.assertEqual(source["header"]["frame_id"], "")
        self.assertIsInstance(source["header"]["seq"], int)

    def test_depth_capture_returns_the_metric_stream_artifact(self) -> None:
        _store, _server, client, receipt = self.capture("depth")
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["width"], output["height"]), (2, 2), output)
        self.assertEqual(output["media_type"], "image/png", output)
        data = client.read_artifact(output["image_ref"], session_id=client.session_id)
        source = data["descriptor"]["x-vendor"]["openmhs.ros_image"]
        self.assertEqual(source["camera"], "depth")
        self.assertEqual(source["topic"], "/rgb_camera_0depth_range_mm")
        self.assertEqual(source["type"], "sensor_msgs/Image")
        self.assertEqual(source["ros_version"], 1)
        self.assertEqual(source["header"]["frame_id"], "camera_depth")

    def test_the_main_resource_is_empty_and_needs_no_topic_wait(self) -> None:
        _store, _server, client, device = self.open()
        state = client.read("camera", device_id=device)
        self.assertEqual(state["state"], {}, state)

    def test_a_malformed_image_reply_has_no_artifact(self) -> None:
        store, _server, _client, receipt = self.capture("color", malformed_image=True)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertNotIn("artifacts", receipt)
        self.assertIsNone(receipt["output"])
        self.assertEqual(store._grants, {})

    def test_an_unsupported_encoding_is_refused(self) -> None:
        store, _server, _client, receipt = self.capture("color", unsupported_encoding=True)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertNotIn("artifacts", receipt)
        self.assertEqual(store._grants, {})

    def test_a_ros1_image_without_header_seq_is_refused(self) -> None:
        store, _server, _client, receipt = self.capture("depth", include_header_seq=False)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertNotIn("artifacts", receipt)
        self.assertEqual(store._grants, {})

    def test_a_missing_depth_sample_times_out_without_an_artifact(self) -> None:
        store, _server, client, device = self.open(publish_depth=False)
        receipt = client.invoke(IMAGE_CAP, {"camera": "depth"}, deadline_ms=100, device_id=device)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIn(receipt["error"]["mhs_code"], {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})
        self.assertIsNone(receipt.get("output"))
        self.assertEqual(store._grants, {})
        # The stock server records the terminal receipt on its worker after the
        # client returns; let that finish before close_server tears the log down.
        time.sleep(0.2)

    def test_an_undeclared_camera_is_refused_by_the_closed_input_schema(self) -> None:
        _store, _server, client, device = self.open()
        receipt = client.invoke(IMAGE_CAP, {"camera": "down"}, device_id=device)
        self.assertNotEqual(receipt["status"], "completed", receipt)
        self.assertIsNone(receipt.get("output"))


if __name__ == "__main__":
    unittest.main()

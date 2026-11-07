"""Acceptance run of the Easys camera package: the gate plus image cases.

Add cases, never remove the check_driver call.
"""

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


class CameraCases(unittest.TestCase):
    """Exercise the adapter and stock server with the package's ROS-free peer."""

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

    def test_raw_camera_capture_returns_a_session_bound_png_artifact(self) -> None:
        store, _server, client, receipt = self.capture("camera")
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
        self.assertEqual(source["camera"], "camera")
        self.assertEqual(source["topic"], "/camera")
        self.assertEqual(source["type"], "sensor_msgs/msg/Image")
        self.assertEqual(source["ros_version"], 2)
        self.assertEqual(source["header"]["frame_id"], "fake_camera_frame")  # placeholder

    def test_detected_image_capture_returns_the_detector_output(self) -> None:
        _store, _server, client, receipt = self.capture("detected")
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["width"], output["height"]), (2, 2), output)
        data = client.read_artifact(output["image_ref"], session_id=client.session_id)
        source = data["descriptor"]["x-vendor"]["openmhs.ros_image"]
        self.assertEqual(source["camera"], "detected")
        self.assertEqual(source["topic"], "/image_processed")
        self.assertEqual(source["type"], "sensor_msgs/msg/Image")
        self.assertEqual(source["ros_version"], 2)
        # The detector assigns no header (balloon_detect.py:85-89): the fake answers with a zero
        # stamp and an empty frame id (placeholders for what cv_bridge leaves; not checked live).
        self.assertEqual(source["header"], {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": ""})
        self.assertNotIn("seq", source["header"])

    def test_the_main_resource_is_empty_and_needs_no_topic_wait(self) -> None:
        _store, _server, client, device = self.open()
        state = client.read("camera", device_id=device)
        self.assertEqual(state["state"], {}, state)

    def test_a_malformed_image_reply_has_no_artifact(self) -> None:
        store, _server, _client, receipt = self.capture("camera", malformed_image=True)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertNotIn("artifacts", receipt)
        self.assertIsNone(receipt["output"])
        self.assertEqual(store._grants, {})

    def test_an_unsupported_encoding_is_refused(self) -> None:
        store, _server, _client, receipt = self.capture("camera", unsupported_encoding=True)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertNotIn("artifacts", receipt)
        self.assertEqual(store._grants, {})

    def test_a_missing_detected_sample_times_out_without_an_artifact(self) -> None:
        store, _server, client, device = self.open(publish_detected=False)
        receipt = client.invoke(IMAGE_CAP, {"camera": "detected"}, deadline_ms=100, device_id=device)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIn(receipt["error"]["mhs_code"], {"MHS.OUTCOME.TIMEOUT", "MHS.DEVICE.NOT_READY"})
        self.assertIsNone(receipt.get("output"))
        self.assertEqual(store._grants, {})
        # The stock server records the terminal receipt on its worker after the
        # client returns; let that finish before close_server tears the log down.
        time.sleep(0.2)

    def test_an_undeclared_camera_is_refused_by_the_closed_input_schema(self) -> None:
        _store, _server, client, device = self.open()
        receipt = client.invoke(IMAGE_CAP, {"camera": "thrusters"}, device_id=device)
        self.assertNotEqual(receipt["status"], "completed", receipt)
        self.assertIsNone(receipt.get("output"))


if __name__ == "__main__":
    unittest.main()

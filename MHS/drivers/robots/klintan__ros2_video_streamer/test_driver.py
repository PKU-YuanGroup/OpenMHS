"""Acceptance run of the ros2_video_streamer camera driver: the gate plus repository cases.

Add cases, never remove the check_driver call.  Every packet below is
controlled test data; no ROS node, video, camera or upstream module is run.
"""

import struct
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.artifacts import LocalArtifactStore
from mhs.client import InProcessTransport, MHSClient
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent
IMAGE = "cap.sensing.image.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ImageCases(unittest.TestCase):
    def serve(self):
        store = LocalArtifactStore()
        self.addCleanup(store.close)
        server = load(HERE, backend="fake", artifact_store=store)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server))
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return server, client, device_id, session, store

    def test_image_capture_returns_complete_png_and_the_source_header(self) -> None:
        _, client, device_id, session, _ = self.serve()
        receipt = client.invoke(IMAGE, {"camera": "color"}, device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(set(receipt["output"]), {"image_ref", "width", "height", "media_type"})
        self.assertEqual(receipt["output"]["width"], 4)     # placeholder from the fake
        self.assertEqual(receipt["output"]["height"], 2)    # placeholder from the fake
        self.assertEqual(receipt["output"]["media_type"], "image/png")
        descriptor = receipt["artifacts"][0]
        metadata = descriptor["x-vendor"]["openmhs.ros_image"]
        self.assertEqual(metadata["camera"], "color")
        self.assertEqual(metadata["topic"], "/image/image_raw")
        self.assertEqual(metadata["type"], "sensor_msgs/msg/Image")
        self.assertEqual(metadata["ros_version"], 2)
        self.assertEqual(metadata["header"], {
            "stamp": {"sec": 17, "nanosec": 123456789},      # placeholder from the fake
            "frame_id": "fake_camera",                       # placeholder from the fake
        })
        blob = client.read_artifact(descriptor["uri"], session_id=session)["data"]
        self.assertTrue(blob.startswith(b"\x89PNG\r\n\x1a\n"))
        width, height = struct.unpack(">II", blob[16:24])
        self.assertEqual((width, height), (4, 2))           # placeholder from the fake

    def test_the_camera_selector_is_closed(self) -> None:
        _, client, device_id, session, _ = self.serve()
        for payload in ({}, {"camera": "depth"}):
            with self.subTest(payload=payload):
                receipt = client.invoke(IMAGE, payload, device_id=device_id, session_id=session)
                self.assertEqual(receipt["status"], "rejected", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")

    def test_the_declared_subscription_and_unsubscription_are_sent(self) -> None:
        server, client, device_id, session, _ = self.serve()
        receipt = client.invoke(IMAGE, {"camera": "color"}, device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        native = server.devices[device_id].bridge.native
        subscriptions = [message for message in native.sent if message.get("op") == "subscribe"]
        self.assertTrue(subscriptions, native.sent)
        self.assertEqual(subscriptions[0]["topic"], "/image/image_raw")
        self.assertEqual(subscriptions[0]["type"], "sensor_msgs/msg/Image")
        self.assertEqual(subscriptions[0]["queue_length"], 1)
        self.assertTrue(any(message.get("op") == "unsubscribe"
                            and message.get("topic") == "/image/image_raw"
                            for message in native.sent), native.sent)

    def test_malformed_stride_is_refused_without_an_artifact(self) -> None:
        server, client, device_id, session, store = self.serve()
        server.devices[device_id].bridge.native.malformed_step = True
        receipt = client.invoke(IMAGE, {"camera": "color"}, device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID")
        self.assertNotIn("artifacts", receipt)
        self.assertEqual(store._grants, {})

    def test_unsupported_encoding_is_refused_without_an_artifact(self) -> None:
        server, client, device_id, session, store = self.serve()
        server.devices[device_id].bridge.native.unsupported_encoding = True
        receipt = client.invoke(IMAGE, {"camera": "color"}, device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID")
        self.assertNotIn("artifacts", receipt)
        self.assertEqual(store._grants, {})

    def test_a_packet_without_a_header_is_refused_without_an_artifact(self) -> None:
        server, client, device_id, session, store = self.serve()
        server.devices[device_id].bridge.native.missing_header = True
        receipt = client.invoke(IMAGE, {"camera": "color"}, device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID")
        self.assertNotIn("artifacts", receipt)
        self.assertEqual(store._grants, {})

    def test_a_silent_image_topic_fails_not_ready_without_an_artifact(self) -> None:
        # Model review of 2026-11-04: in image-folder mode the node publishes every image inside its
        # constructor before it spins, and a video without --loop exits at its end; a later capture gets no frame.
        server, client, device_id, session, store = self.serve()
        server.devices[device_id].bridge.native.silent = True
        receipt = client.invoke(IMAGE, {"camera": "color"}, device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.NOT_READY")
        self.assertNotIn("artifacts", receipt)
        self.assertEqual(store._grants, {})

    def test_the_estop_latch_refuses_further_image_capture(self) -> None:
        _, client, device_id, session, _ = self.serve()
        estop = client.estop("test", device_id=device_id, session_id=session)
        self.assertEqual(estop["status"], "completed", estop)
        self.assertIn(estop["output"]["estop"], {"engaged", "software_only"})
        refused = client.invoke(IMAGE, {"camera": "color"}, device_id=device_id, session_id=session)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_native_peer_is_a_ros_free_transport(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(type(driver.native).__name__, "FakeRos2VideoStreamer")
        self.assertEqual(driver.native.sent, [])


if __name__ == "__main__":
    unittest.main()

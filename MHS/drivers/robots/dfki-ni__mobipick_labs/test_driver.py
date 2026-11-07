"""Acceptance run of the Mobipick experiment-camera package: the gate plus repository cases.

The image is the primary output of this device, so the cases exercise the stock
artifact path and the fixed ROS 1 subscription rather than metadata alone.  Add
cases, never remove the ``check_driver`` call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.artifacts import LocalArtifactStore
from mhs.client import InProcessTransport, MHSClient
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent
CAP = "cap.sensing.image.v1"
TOPIC = "/experiment_camera/image_raw"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ExperimentCameraCases(unittest.TestCase):
    def serve(self):
        store = LocalArtifactStore()
        self.addCleanup(store.close)
        server = load(HERE, backend="fake", artifact_store=store)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server))
        client.hello()
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        self.driver = next(iter(server.devices.values())).bridge
        return client

    def test_a_capture_returns_the_complete_fake_frame(self) -> None:
        client = self.serve()
        receipt = client.invoke(CAP, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["width"], 4)          # placeholder fake width
        self.assertEqual(output["height"], 3)         # placeholder fake height
        self.assertEqual(output["media_type"], "image/png")
        self.assertTrue(output["image_ref"].startswith("mhs+artifact://"), output)

    def test_the_capture_subscribes_to_the_pinned_image_topic_and_type(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke(CAP, {}, **self.ids)["status"], "completed")
        subscriptions = [message for message in self.driver.native.sent
                         if message.get("op") == "subscribe"]
        self.assertTrue(subscriptions, self.driver.native.sent)
        self.assertEqual(subscriptions[0]["topic"], TOPIC)
        self.assertEqual(subscriptions[0]["type"], "sensor_msgs/Image")
        self.assertTrue(any(message.get("op") == "unsubscribe" and message.get("topic") == TOPIC
                            for message in self.driver.native.sent), self.driver.native.sent)

    def test_an_unsupported_native_encoding_is_a_failed_capture(self) -> None:
        client = self.serve()
        self.driver.native.encoding = "bayer"         # placeholder unsupported encoding
        receipt = client.invoke(CAP, {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID", receipt)

    def test_the_artifact_contains_the_fake_frame_pixels(self) -> None:
        client = self.serve()
        receipt = client.invoke(CAP, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        descriptor = receipt["artifacts"][0]
        self.assertEqual(descriptor["media_type"], "image/png")
        blob = client.read_artifact(descriptor["uri"], session_id=receipt["session_id"])["data"]
        self.assertTrue(blob.startswith(b"\x89PNG\r\n\x1a\n"), blob[:8])
        self.assertEqual(int.from_bytes(blob[16:20], "big"), 4)   # placeholder fake width
        self.assertEqual(int.from_bytes(blob[20:24], "big"), 3)   # placeholder fake height


if __name__ == "__main__":
    unittest.main()

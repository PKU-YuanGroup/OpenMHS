"""Acceptance run of the ros_astra_camera package: the gate, plus image cases.

The check_driver call is kept.  These cases exercise the stock RosDriver bridge
and the package-local ROS-free protocol fake; no ROS graph, camera or hardware
is contacted.
"""

import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.artifacts import LocalArtifactStore
from mhs.client import InProcessTransport, MHSClient
from mhs.driver import build_server, close_server
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent
IMAGE_CAPABILITY = "cap.sensing.image.v1"
IMAGE_TOPIC = "/image"
IMAGE_TYPE = "sensor_msgs/msg/Image"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
NOT_READY_CODES = {"MHS.DEVICE.NOT_READY", "MHS.OUTCOME.TIMEOUT"}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AstroCameraImageCases(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, "fake")
        store = LocalArtifactStore()
        server = build_server(driver, artifact_store=store)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server))
        self.addCleanup(client.close)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    def test_capture_returns_actual_dimensions_and_a_png_artifact(self) -> None:
        _driver, client = self.serve()
        receipt = client.invoke(IMAGE_CAPABILITY, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(set(output), {"image_ref", "width", "height", "media_type"}, output)
        self.assertEqual((output["width"], output["height"]), (4, 2), output)
        self.assertEqual(output["media_type"], "image/png", output)
        self.assertTrue(output["image_ref"].startswith("mhs+artifact://"), output)
        artifact = client.read_artifact(output["image_ref"], session_id=self.ids["session_id"])
        self.assertEqual(artifact["descriptor"]["media_type"], "image/png", artifact)
        data = artifact["data"]
        self.assertTrue(data.startswith(PNG_SIGNATURE), data[:8])
        self.assertEqual(int.from_bytes(data[16:20], "big"), 4)
        self.assertEqual(int.from_bytes(data[20:24], "big"), 2)

    def test_capture_subscribes_to_the_declared_color_endpoint(self) -> None:
        driver, client = self.serve()
        receipt = client.invoke(IMAGE_CAPABILITY, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        subscriptions = [message for message in driver.native.sent
                         if message.get("op") == "subscribe"
                         and message.get("topic") == IMAGE_TOPIC]
        self.assertEqual(len(subscriptions), 1, driver.native.sent)
        self.assertEqual(subscriptions[0]["type"], IMAGE_TYPE)
        self.assertEqual(subscriptions[0]["queue_length"], 1)
        self.assertFalse([message for message in driver.native.sent
                          if message.get("op") in
                          ("advertise", "publish", "call_service", "send_action_goal")])

    def test_wrong_row_step_is_refused_without_an_artifact(self) -> None:
        driver, client = self.serve()
        driver.native.wrong_step = True
        receipt = client.invoke(IMAGE_CAPABILITY, {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID")
        self.assertIsNone(receipt.get("output"))

    def test_wrong_data_length_is_refused_without_an_artifact(self) -> None:
        driver, client = self.serve()
        driver.native.wrong_data_length = True
        receipt = client.invoke(IMAGE_CAPABILITY, {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID")
        self.assertIsNone(receipt.get("output"))

    def test_unsupported_pixel_encoding_is_refused(self) -> None:
        driver, client = self.serve()
        driver.native.unsupported_encoding = True
        receipt = client.invoke(IMAGE_CAPABILITY, {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID")
        self.assertIsNone(receipt.get("output"))

    def test_a_silent_image_topic_does_not_complete(self) -> None:
        driver, client = self.serve()
        driver.native.publish_image = False
        receipt = client.invoke(IMAGE_CAPABILITY, {}, deadline_ms=200, **self.ids)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIn(receipt["error"]["mhs_code"], NOT_READY_CODES)
        self.assertIsNone(receipt.get("output"))

    def test_camera_exposes_no_command_or_stop_binding(self) -> None:
        driver, _client = self.serve()
        model = driver._model
        self.assertEqual([binding.capability_id for binding in model.bindings],
                         [IMAGE_CAPABILITY])
        self.assertIsNone(model.estop)
        self.assertEqual(list(model.achieved_by), [])


if __name__ == "__main__":
    unittest.main()

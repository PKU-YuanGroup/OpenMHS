"""Acceptance run of the ZED ROS 2 package: the gate, plus image-specific cases.

The gate check is kept unchanged.  The cases below exercise the real bridge and
the package-local recording transport; no ROS graph, camera or hardware is
contacted.
"""

import time
import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.artifacts import LocalArtifactStore
from mhs.client import InProcessTransport, MHSClient
from mhs.driver import build_server, close_server
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent
IMAGE_CAPABILITY = "cap.sensing.image.v1"
IMAGE_TOPIC = "/zed/zed_node/rgb/color/rect/image"
IMAGE_TYPE = "sensor_msgs/msg/Image"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ZedImageCases(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, "fake")
        store = LocalArtifactStore()
        server = build_server(driver, artifact_store=store)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server))
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return driver, client

    def test_image_capture_reports_actual_dimensions_and_png(self) -> None:
        _, client = self.serve()
        receipt = client.invoke(IMAGE_CAPABILITY, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["width"], 4)
        self.assertEqual(output["height"], 2)
        self.assertEqual(output["media_type"], "image/png")
        self.assertTrue(output["image_ref"].startswith("mhs+artifact://"))
        artifact = client.read_artifact(output["image_ref"], session_id=self.ids["session_id"])
        data = artifact["data"]
        self.assertTrue(data.startswith(PNG_SIGNATURE))
        self.assertEqual(int.from_bytes(data[16:20], "big"), 4)
        self.assertEqual(int.from_bytes(data[20:24], "big"), 2)
        self.assertEqual(artifact["descriptor"]["media_type"], "image/png")

    def test_capture_subscribes_only_to_the_declared_image_endpoint(self) -> None:
        driver, client = self.serve()
        receipt = client.invoke(IMAGE_CAPABILITY, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        subscriptions = [message for message in driver.native.sent if message.get("op") == "subscribe"]
        self.assertEqual(len(subscriptions), 1, driver.native.sent)
        self.assertEqual(subscriptions[0]["topic"], IMAGE_TOPIC)
        self.assertEqual(subscriptions[0]["type"], IMAGE_TYPE)
        self.assertFalse([message for message in driver.native.sent
                          if message.get("op") in ("advertise", "publish", "call_service", "send_action_goal")])

    def test_missing_image_data_fails_before_any_artifact(self) -> None:
        driver, client = self.serve()
        driver.native.omit_data = True
        receipt = client.invoke(IMAGE_CAPABILITY, {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID")
        self.assertIsNone(receipt.get("output"))

    def test_wrong_row_step_is_refused(self) -> None:
        driver, client = self.serve()
        driver.native.wrong_step = True
        receipt = client.invoke(IMAGE_CAPABILITY, {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID")

    def test_a_silent_image_topic_does_not_complete(self) -> None:
        driver, client = self.serve()
        driver.native.publish_image = False
        receipt = client.invoke(IMAGE_CAPABILITY, {}, deadline_ms=50, **self.ids)
        self.assertIn(receipt["status"], {"failed", "unknown"}, receipt)
        self.assertIn(receipt["error"]["mhs_code"],
                      {"MHS.DEVICE.NOT_READY", "MHS.OUTCOME.TIMEOUT"})
        self.assertIsNone(receipt.get("output"))
        # Let the command worker record its final timed-out receipt before
        # close_server tears down the evidence log.
        time.sleep(2.5)

    def test_camera_exposes_no_command_or_stop_binding(self) -> None:
        driver, _ = self.serve()
        model = driver._model
        self.assertEqual([binding.capability_id for binding in model.bindings], [IMAGE_CAPABILITY])
        self.assertIsNone(model.estop)
        self.assertEqual(list(model.achieved_by), [])


if __name__ == "__main__":
    unittest.main()

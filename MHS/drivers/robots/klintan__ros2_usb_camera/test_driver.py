"""Acceptance run of the ros2_usb_camera metadata package: the gate plus repository cases.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
CAP = "x-cap.klintan.camera_info.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CameraInfoCases(unittest.TestCase):
    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_the_metadata_capability_returns_the_selected_frame_id(self) -> None:
        driver = self.driver()
        driver.native.frame_id = "test_frame"  # placeholder
        self.assertEqual(driver.call(CAP, {}), {"frame_id": "test_frame"})

    def test_the_resource_read_returns_the_selected_frame_id(self) -> None:
        driver = self.driver()
        driver.native.frame_id = "resource_frame"  # placeholder
        self.assertEqual(driver.read("camera", ["frame_id"]), {"frame_id": "resource_frame"})

    def test_the_client_invocation_returns_the_metadata_output(self) -> None:
        client = self.serve()
        receipt = client.invoke(CAP, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"frame_id": "fake_camera_frame"})  # placeholder

    def test_the_subscription_names_the_camera_info_topic_and_type(self) -> None:
        driver = self.driver()
        driver.call(CAP, {})
        subscriptions = [message for message in driver.native.sent
                         if message.get("op") == "subscribe"]
        self.assertTrue(subscriptions, driver.native.sent)
        self.assertEqual(subscriptions[0]["topic"], "/camera_info")
        self.assertEqual(subscriptions[0]["type"], "sensor_msgs/msg/CameraInfo")
        self.assertEqual(subscriptions[0]["queue_length"], 1)
        self.assertTrue(any(message.get("op") == "unsubscribe"
                            and message.get("topic") == "/camera_info"
                            for message in driver.native.sent), driver.native.sent)

    def test_a_message_without_a_header_is_a_state_error(self) -> None:
        driver = self.driver()
        driver.native.include_header = False
        with self.assertRaises(MHSError) as caught:
            driver.call(CAP, {})
        self.assertEqual(caught.exception.code, "MHS.RESOURCE.STATE_INVALID")

    def test_a_message_without_a_frame_id_is_a_state_error(self) -> None:
        driver = self.driver()
        driver.native.include_frame_id = False
        with self.assertRaises(MHSError) as caught:
            driver.read("camera", ["frame_id"])
        self.assertEqual(caught.exception.code, "MHS.RESOURCE.STATE_INVALID")


if __name__ == "__main__":
    unittest.main()

"""Acceptance run of the realsense-ros package: the gate plus repository cases.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
CAMERA_INFO = "x-cap.realsenseai.camera_info.v1"
DEVICE_INFO = "x-cap.realsenseai.device_info.v1"
FRAME_METADATA = "x-cap.realsenseai.frame_metadata.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RealsenseCases(unittest.TestCase):
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

    def test_the_camera_info_capability_returns_the_selected_geometry(self) -> None:
        driver = self.driver()
        driver.native.frame_id = "test_color_frame"  # placeholder
        driver.native.width = 848  # placeholder
        driver.native.height = 480  # placeholder
        self.assertEqual(
            driver.call(CAMERA_INFO, {}),
            {
                "width": 848,
                "height": 480,
                "frame_id": "test_color_frame",
                "distortion_model": "plumb_bob",  # placeholder
                "binning_x": 0,
                "binning_y": 0,
            },
        )

    def test_the_resource_read_returns_identity_and_geometry(self) -> None:
        driver = self.driver()
        driver.native.device_info["serial_number"] = "test_serial"  # placeholder
        state = driver.read("camera", ["frame_id", "width", "height", "serial_number"])
        self.assertEqual(state["serial_number"], "test_serial")
        self.assertEqual(state["width"], 640)  # placeholder
        self.assertEqual(state["height"], 480)  # placeholder
        self.assertEqual(state["frame_id"], "fake_color_optical_frame")  # placeholder

    def test_the_client_invocation_returns_the_device_info_output(self) -> None:
        client = self.serve()
        receipt = client.invoke(DEVICE_INFO, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(set(output), {
            "device_name", "serial_number", "firmware_version", "usb_type_descriptor",
            "firmware_update_id", "sensors", "physical_port",
        })
        self.assertEqual(output["sensors"], "Stereo Module,RGB Camera")  # placeholder

    def test_the_subscriptions_name_the_declared_topics_and_types(self) -> None:
        driver = self.driver()
        driver.call(CAMERA_INFO, {})
        driver.call(FRAME_METADATA, {})
        subscriptions = [message for message in driver.native.sent
                         if message.get("op") == "subscribe"]
        self.assertEqual(
            [(message["topic"], message["type"]) for message in subscriptions],
            [
                ("/camera/camera/color/camera_info", "sensor_msgs/msg/CameraInfo"),
                ("/camera/camera/color/metadata", "realsense2_camera_msgs/msg/Metadata"),
            ],
        )
        self.assertTrue(all(message["queue_length"] == 1 for message in subscriptions))
        self.assertTrue(any(message.get("op") == "unsubscribe"
                            and message.get("topic") == "/camera/camera/color/camera_info"
                            for message in driver.native.sent), driver.native.sent)

    def test_the_device_info_service_is_called_with_its_declared_type(self) -> None:
        driver = self.driver()
        driver.call(DEVICE_INFO, {})
        calls = [message for message in driver.native.sent
                 if message.get("op") == "call_service"]
        self.assertEqual(len(calls), 1, driver.native.sent)
        self.assertEqual(calls[0]["service"], "/camera/camera/device_info")
        self.assertEqual(calls[0]["type"], "realsense2_camera_msgs/srv/DeviceInfo")
        self.assertEqual(calls[0]["args"], {})

    def test_the_frame_metadata_capability_returns_json_text(self) -> None:
        driver = self.driver()
        driver.native.metadata_json = '{"FrameNumber":"7"}'  # placeholder
        self.assertEqual(driver.call(FRAME_METADATA, {}), {"json_data": '{"FrameNumber":"7"}'})

    def test_a_camera_info_without_width_is_a_state_error(self) -> None:
        driver = self.driver()
        driver.native.include_width = False
        with self.assertRaises(MHSError) as caught:
            driver.read("camera", ["width"])
        self.assertEqual(caught.exception.code, "MHS.RESOURCE.STATE_INVALID")

    def test_a_camera_info_without_frame_id_is_a_state_error(self) -> None:
        driver = self.driver()
        driver.native.include_frame_id = False
        with self.assertRaises(MHSError) as caught:
            driver.read("camera", ["frame_id"])
        self.assertEqual(caught.exception.code, "MHS.RESOURCE.STATE_INVALID")

    def test_a_metadata_message_without_json_data_is_a_state_error(self) -> None:
        driver = self.driver()
        driver.native.include_metadata_json = False
        with self.assertRaises(MHSError) as caught:
            driver.call(FRAME_METADATA, {})
        self.assertEqual(caught.exception.code, "MHS.RESOURCE.STATE_INVALID")

    def test_a_failed_device_info_response_does_not_report_success(self) -> None:
        driver = self.driver()
        driver.native.device_info_ok = False
        with self.assertRaises(DriverFailed):
            driver.call(DEVICE_INFO, {})

    def test_a_device_info_response_missing_a_field_is_an_output_error(self) -> None:
        driver = self.driver()
        driver.native.include_serial = False
        with self.assertRaises(DriverFailed) as caught:
            driver.call(DEVICE_INFO, {})
        self.assertEqual(caught.exception.code, "MHS.CAPABILITY.OUTPUT_INVALID")

    def test_a_device_info_read_missing_a_field_is_a_state_error(self) -> None:
        driver = self.driver()
        driver.native.include_serial = False
        with self.assertRaises(MHSError) as caught:
            driver.read("camera", ["serial_number"])
        self.assertEqual(caught.exception.code, "MHS.RESOURCE.STATE_INVALID")

    def test_a_silent_camera_info_topic_times_out_as_not_ready(self) -> None:
        driver = self.driver()
        driver.native.publish_camera_info = False
        with self.assertRaises(MHSError) as caught:
            driver.read("camera", ["frame_id"])
        self.assertEqual(caught.exception.code, "MHS.DEVICE.NOT_READY")


if __name__ == "__main__":
    unittest.main()

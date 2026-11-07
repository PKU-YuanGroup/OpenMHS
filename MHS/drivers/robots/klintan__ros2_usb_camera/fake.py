"""ROS-free complete camera packets; every sample is explicit test data.

This controlled peer supplies independent Image/CameraInfo subscriptions. It
does not execute OpenCV, the upstream node, ROS, a camera or a physics clock.
No sample is measured calibration, native fidelity or source-age evidence.
"""

import copy

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeRos2UsbCamera(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond, max_message_bytes=16 * 1024 * 1024)
        self.frame_id = "fake_camera_frame"  # placeholder
        self.include_header = True           # placeholder negative-path switch
        self.include_frame_id = True         # placeholder negative-path switch
        self.subscription_count = 0          # placeholder counter
        self.silent_topics = set()            # placeholder negative-path control
        self.camera_info_override = None      # placeholder malformed-packet control
        self.image = {                        # placeholder complete 3x2 BGR8 sample
            "header": {"stamp": {"sec": 17, "nanosec": 123456789}, "frame_id": self.frame_id},
            "height": 2, "width": 3, "encoding": "bgr8", "is_bigendian": 0, "step": 9,
            "data": [1, 9, 27, 80, 130, 201, 255, 0, 42, 13, 31, 61, 77, 99, 121, 9, 190, 245],
        }

    def camera_info(self):
        # Placeholder calibration and ROI, deliberately nonconstant and complete.
        msg = {
            "header": {"stamp": {"sec": 17, "nanosec": 123456789}, "frame_id": self.frame_id},
            "height": 2, "width": 3, "distortion_model": "plumb_bob",
            "d": [0.11, -0.03, 0.004, 0.002, 0.001],
            "k": [500.0, 0.0, 1.5, 0.0, 510.0, 1.0, 0.0, 0.0, 1.0],
            "r": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
            "p": [490.0, 0.0, 1.5, 0.0, 0.0, 505.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            "binning_x": 0, "binning_y": 0,
            "roi": {"x_offset": 0, "y_offset": 0, "height": 0, "width": 0, "do_rectify": False},
        }
        if not self.include_header:
            msg.pop("header")
        elif not self.include_frame_id:
            msg["header"].pop("frame_id")
        return msg

    def _respond(self, message):
        if message.get("op") != "subscribe" or message.get("topic") not in ("/image", "/camera_info"):
            return None
        self.subscription_count += 1
        if message["topic"] in self.silent_topics:
            return None
        msg = (self.image if message["topic"] == "/image" else
               self.camera_info_override if self.camera_info_override is not None else self.camera_info())
        return {
            "op": "publish",
            "topic": message["topic"],
            "id": message.get("id"),
            "msg": copy.deepcopy(msg),
        }

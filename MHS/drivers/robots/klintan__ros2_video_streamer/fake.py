"""ROS-free controlled peer for the pinned camera_simulator Image wire contract.

The fake answers the fixed rosbridge subscription the driver declares:
``/image/image_raw`` as a ROS 2 ``sensor_msgs/msg/Image`` carrying a complete
BGR8 packet and an exact ROS 2 header. It runs no ROS node, OpenCV, video
decoder or capture timer and contacts no camera. Every sample below is
explicit test data, not captured ROS traffic or a device measurement.
"""

import base64

from mhs.bridge.ros_transport import RecordingRosTransport

IMAGE_TOPIC = "/image/image_raw"        # declared test endpoint
IMAGE_TYPE = "sensor_msgs/msg/Image"    # declared ROS 2 type


class FakeRos2VideoStreamer(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond, max_message_bytes=16 * 1024 * 1024)  # placeholder budget
        self.width = 4                   # placeholder
        self.height = 2                  # placeholder
        self.frame_id = "fake_camera"    # placeholder
        self.stamp_sec = 17              # placeholder
        self.stamp_nanosec = 123456789   # placeholder
        self.malformed_step = False      # placeholder negative-path switch
        self.unsupported_encoding = False  # placeholder negative-path switch
        self.missing_header = False      # placeholder negative-path switch
        # Placeholder negative-path switch: the node publishes nothing (image-folder mode after its
        # constructor, or a video without --loop after its end).
        self.silent = False
        self._pixels = bytes(range(24))  # placeholder BGR8 4x2 payload

    def _image_message(self):
        encoding = "yuv422" if self.unsupported_encoding else "bgr8"  # placeholder negative-path encoding
        step = self.width * 3            # placeholder three bytes per BGR8 pixel
        if self.malformed_step:
            step += 1                    # placeholder malformed stride
        message = {
            "header": {
                "stamp": {"sec": self.stamp_sec, "nanosec": self.stamp_nanosec},  # placeholder
                "frame_id": self.frame_id,  # placeholder
            },
            "height": self.height,       # placeholder
            "width": self.width,         # placeholder
            "encoding": encoding,        # placeholder
            "is_bigendian": 0,           # placeholder ROS 2 Image field
            "step": step,                # placeholder
            "data": base64.b64encode(self._pixels).decode("ascii"),  # placeholder
        }
        if self.missing_header:
            message.pop("header")
        return message

    def _respond(self, message):
        if message.get("op") != "subscribe" or message.get("topic") != IMAGE_TOPIC:
            return None
        if message.get("type") != IMAGE_TYPE:
            return None
        if self.silent:
            return None
        return {
            "op": "publish",
            "topic": IMAGE_TOPIC,
            "id": message.get("id"),
            "msg": self._image_message(),
        }

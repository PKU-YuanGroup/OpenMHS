"""ROS-free protocol fake for the pinned realsense_ros2_camera endpoints.

The fake answers the two fixed rosbridge subscriptions the driver declares:
``/camera/color/image_raw`` with a ``sensor_msgs/msg/Image`` message and
``/camera/color/camera_info`` with a CameraInfo-shaped message carrying the
geometry fields the driver reads.  It contacts no ROS graph and no camera.

The responses are synthesized from placeholder data, not replayed from
captured ROS traffic.  Every value below is test data, not a device fact.  The
4x2 RGB frame is deliberately smaller than the node's configured 640x480
default; the real deployment size is whatever the ``color_width`` and
``color_height`` ROS parameters select.
"""

import base64

from mhs.bridge.ros_transport import RecordingRosTransport

IMAGE_TOPIC = "/camera/color/image_raw"
INFO_TOPIC = "/camera/color/camera_info"
IMAGE_TYPE = "sensor_msgs/msg/Image"
INFO_TYPE = "sensor_msgs/msg/CameraInfo"


class FakeRos2IntelRealsense(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.width = 4                                      # placeholder
        self.height = 2                                     # placeholder
        self.frame_id = "camera_color_optical_frame"        # placeholder
        self.encoding = "rgb8"                              # placeholder
        self.is_bigendian = 0                               # placeholder
        self.pixels = bytes([                               # placeholder
            8, 16, 24,    32, 40, 48,    56, 64, 72,    80, 88, 96,
            104, 112, 120,    128, 136, 144,    152, 160, 168,    176, 184, 192,
        ])
        self.publish_image = True                           # placeholder negative-path switch
        self.publish_info = True                            # placeholder negative-path switch
        self.wrong_step = False                             # placeholder negative-path switch
        self.unsupported_encoding = False                   # placeholder negative-path switch

    def _image_message(self):
        message = {
            "header": {
                "frame_id": self.frame_id,                  # placeholder
                "stamp": {"sec": 0, "nanosec": 0},            # placeholder
            },
            "width": self.width,                            # placeholder
            "height": self.height,                          # placeholder
            "encoding": self.encoding,                      # placeholder
            "is_bigendian": self.is_bigendian,              # placeholder
            "step": self.width * 3,                         # placeholder
            "data": base64.b64encode(self.pixels).decode("ascii"),  # placeholder
        }
        if self.wrong_step:
            message["step"] = self.width * 3 + 1            # placeholder
        if self.unsupported_encoding:
            message["encoding"] = "8UC1"                    # placeholder
        return message

    def _info_message(self):
        return {
            "header": {
                "frame_id": self.frame_id,                  # placeholder
                "stamp": {"sec": 0, "nanosec": 0},            # placeholder
            },
            "height": self.height,                          # placeholder
            "width": self.width,                            # placeholder
            "distortion_model": "plumb_bob",                # placeholder
            "d": [],                                        # placeholder
            "k": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],  # placeholder
            "r": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],  # placeholder
            "p": [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0,
                  0.0, 0.0, 1.0, 0.0],                       # placeholder
        }

    def _respond(self, message):
        if message.get("op") != "subscribe":
            return None
        topic = message.get("topic")
        if topic == IMAGE_TOPIC and message.get("type") == IMAGE_TYPE:
            if not self.publish_image:
                return None
            return {
                "op": "publish",
                "topic": IMAGE_TOPIC,
                "id": message.get("id"),
                "msg": self._image_message(),
            }
        if topic == INFO_TOPIC and message.get("type") == INFO_TYPE:
            if not self.publish_info:
                return None
            return {
                "op": "publish",
                "topic": INFO_TOPIC,
                "id": message.get("id"),
                "msg": self._info_message(),
            }
        return None

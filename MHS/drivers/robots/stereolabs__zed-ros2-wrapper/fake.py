"""ROS-free recording fake for the ZED ROS 2 RGB image endpoint.

The fake models the pinned rosbridge contract of one subscription to
``/zed/zed_node/rgb/color/rect/image``: the request carries the declared
``sensor_msgs/msg/Image`` type, and the response event is an
``sensor_msgs/msg/Image``-shaped message whose pixels become a local PNG
artifact.  It answers no service, action or command endpoint.

The frame is deliberately tiny test data, not a camera fact.  The real
publisher sends the configured grab resolution and BGR8 or BGRA8 depending on
``video.enable_24bit_output``; the fake proves the wire and conversion
contract only and claims no camera, ROS graph or hardware execution.
"""

import base64

from mhs.bridge.ros_transport import RecordingRosTransport

IMAGE_TOPIC = "/zed/zed_node/rgb/color/rect/image"
IMAGE_TYPE = "sensor_msgs/msg/Image"


class FakeZedRos2Wrapper(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # A 4x2 BGRA test frame.  Every dimension and pixel below is
        # placeholder test data, not a device fact or a claimed resolution.
        self.width = 4  # placeholder
        self.height = 2  # placeholder
        self.frame_id = "fake_zed_left_camera_optical_frame"  # placeholder
        self.encoding = "bgra8"  # placeholder
        self.is_bigendian = 0  # placeholder
        self.pixels = bytes([  # placeholder
            0, 0, 255, 255,   0, 255, 0, 255,
            255, 0, 0, 255,   255, 255, 255, 255,
            16, 32, 48, 64,   80, 96, 112, 128,
            144, 160, 176, 192,   208, 224, 240, 255,
        ])
        self.publish_image = True   # placeholder negative-path switch
        self.omit_data = False      # placeholder negative-path switch
        self.wrong_step = False     # placeholder negative-path switch

    def _image_message(self):
        message = {
            "header": {"frame_id": self.frame_id},
            "width": self.width,
            "height": self.height,
            "encoding": self.encoding,
            "is_bigendian": self.is_bigendian,
            "step": self.width * 4,
            "data": base64.b64encode(self.pixels).decode("ascii"),
        }
        if self.omit_data:
            message.pop("data", None)
        if self.wrong_step:
            message["step"] = self.width * 3
        return message

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe" and message.get("topic") == IMAGE_TOPIC:
            if not self.publish_image:
                return None
            return {
                "op": "publish",
                "topic": IMAGE_TOPIC,
                "id": message.get("id"),
                "msg": self._image_message(),
            }
        return None

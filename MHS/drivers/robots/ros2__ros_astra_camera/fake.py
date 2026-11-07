"""ROS-free protocol fake for the pinned ros_astra_camera color endpoint.

The fake models the declared rosbridge wire contract: one subscriber receives a
``sensor_msgs/msg/Image``-shaped message on the relative color publisher's
resolved endpoint ``/image``.  The message is built from placeholder values,
not replayed from captured ROS traffic, so it is a synthesized controlled-peer
fake (F0), not a recording of a camera.

The real node publishes the configured device resolution and the frame listener
supplies the ROS RGB8 encoding and step; this fake's 4x2 frame is deliberately
smaller.  No pixel below is measured calibration, native fidelity or source-age
evidence.
"""

import base64

from mhs.bridge.ros_transport import RecordingRosTransport

IMAGE_TOPIC = "/image"
IMAGE_TYPE = "sensor_msgs/msg/Image"


class FakeRosAstraCamera(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.frame_id = "astra_fake_color_optical_frame"  # placeholder
        self.width = 4                                    # placeholder
        self.height = 2                                   # placeholder
        self.encoding = "rgb8"                            # placeholder
        self.is_bigendian = 0                             # placeholder
        self.stamp_sec = 17                               # placeholder
        self.stamp_nanosec = 123456789                    # placeholder
        self.pixels = bytes([                             # placeholder complete 4x2 RGB8 sample
            0, 8, 16,    32, 40, 48,    64, 72, 80,    96, 104, 112,
            15, 23, 31,  47, 55, 63,   79, 87, 95,   111, 119, 127,
        ])
        self.publish_image = True                         # placeholder negative-path switch
        self.wrong_step = False                           # placeholder negative-path switch
        self.wrong_data_length = False                    # placeholder negative-path switch
        self.unsupported_encoding = False                 # placeholder negative-path switch
        self.missing_encoding = False                     # placeholder negative-path switch

    def _image_message(self):
        message = {
            "header": {
                "stamp": {"sec": self.stamp_sec, "nanosec": self.stamp_nanosec},  # placeholder
                "frame_id": self.frame_id,                                        # placeholder
            },
            "height": self.height,                            # placeholder
            "width": self.width,                              # placeholder
            "encoding": self.encoding,                        # placeholder
            "is_bigendian": self.is_bigendian,                # placeholder
            "step": self.width * 3,                           # placeholder
            "data": base64.b64encode(self.pixels).decode("ascii"),  # placeholder
        }
        if self.wrong_step:
            message["step"] = self.width * 3 + 1              # placeholder
        if self.wrong_data_length:
            message["data"] = base64.b64encode(self.pixels + b"\x01").decode("ascii")  # placeholder
        if self.unsupported_encoding:
            message["encoding"] = "yuv422"                    # placeholder
        if self.missing_encoding:
            message.pop("encoding", None)
        return message

    def _respond(self, message):
        if message.get("op") != "subscribe":
            return None
        if message.get("topic") != IMAGE_TOPIC or message.get("type") != IMAGE_TYPE:
            return None
        if not self.publish_image:
            return None
        return {
            "op": "publish",
            "topic": IMAGE_TOPIC,
            "id": message.get("id"),
            "msg": self._image_message(),
        }

"""ROS-free protocol fake for the DroneSimLab UE4 camera bridge.

The fake answers the two fixed rosbridge image subscriptions that the driver
declares: ``/rgb_camera_0`` with a bgr8 ``sensor_msgs/Image`` and
``/rgb_camera_0depth_range_mm`` with a mono16 ``sensor_msgs/Image``.  It
contacts no ROS graph, ZMQ proxy or Unreal Engine renderer.  Every frame below
is synthesized placeholder data; this is not a replay of captured ROS traffic.

The 2x2 frame is deliberately smaller than a deployment's UE4 render target so
the receipts stay small.  The real render-target size is deployment-configured.
"""

import base64
import struct

from mhs.bridge.ros_transport import RecordingRosTransport

COLOR_TOPIC = "/rgb_camera_0"
DEPTH_TOPIC = "/rgb_camera_0depth_range_mm"


def _b64(payload: bytes) -> str:
    return base64.b64encode(payload).decode("ascii")


class FakeDronesimlab(RecordingRosTransport):
    def __init__(self, *, malformed_image: bool = False, unsupported_encoding: bool = False,
                 include_header_seq: bool = True, publish_color: bool = True,
                 publish_depth: bool = True, **_options):
        super().__init__(handler=self._respond)
        self.width = 2   # placeholder
        self.height = 2  # placeholder
        # The bridge publishes the color stream without setting its header
        # (ue4_bridge.py:53-55), so its frame_id stays empty; "camera_rgb" is
        # only the colorized depth _rgb8 image's frame (ue4_bridge.py:64).
        self.color_frame_id = ""
        self.depth_frame_id = "camera_depth"    # ue4_bridge.py:75
        # 2x2 bgr8 placeholder pixels.
        self.color_data = _b64(bytes([0, 0, 0, 255, 0, 0, 0, 255, 0, 0, 0, 255]))  # placeholder
        # 2x2 mono16 placeholder depth samples, little endian: 100, 200, 300, 400.
        self.depth_data = _b64(struct.pack("<4H", 100, 200, 300, 400))  # placeholder
        self.publish_color = bool(publish_color)                 # placeholder negative-path switch
        self.publish_depth = bool(publish_depth)                 # placeholder negative-path switch
        self.malformed_image = bool(malformed_image)             # placeholder negative-path switch
        self.unsupported_encoding = bool(unsupported_encoding)   # placeholder negative-path switch
        self.include_header_seq = bool(include_header_seq)       # placeholder negative-path switch
        self._seq = 0                                            # placeholder counter

    def _header(self, frame_id):
        header = {
            "frame_id": frame_id,
            "stamp": {"secs": 0, "nsecs": 0},  # placeholder
        }
        if self.include_header_seq:
            header["seq"] = self._seq  # placeholder
        return header

    def _respond(self, message):
        if message.get("op") != "subscribe":
            return None
        topic = message.get("topic")
        if topic == COLOR_TOPIC and self.publish_color:
            self._seq += 1
            return {
                "op": "publish",
                "topic": topic,
                "id": message.get("id"),
                "msg": {
                    "header": self._header(self.color_frame_id),
                    "height": self.height,
                    "width": self.width,
                    "encoding": "bgr8x" if self.unsupported_encoding else "bgr8",  # placeholder encoding
                    "is_bigendian": 0,  # placeholder
                    # Deliberately inconsistent step for the malformed-image case.
                    "step": self.width * (2 if self.malformed_image else 3),
                    "data": self.color_data,
                },
            }
        if topic == DEPTH_TOPIC and self.publish_depth:
            self._seq += 1
            return {
                "op": "publish",
                "topic": topic,
                "id": message.get("id"),
                "msg": {
                    "header": self._header(self.depth_frame_id),
                    "height": self.height,
                    "width": self.width,
                    "encoding": "mono32" if self.unsupported_encoding else "mono16",  # placeholder encoding
                    "is_bigendian": 0,  # placeholder
                    # Deliberately inconsistent step for the malformed-image case.
                    "step": self.width * (1 if self.malformed_image else 2),
                    "data": self.depth_data,
                },
            }
        return None

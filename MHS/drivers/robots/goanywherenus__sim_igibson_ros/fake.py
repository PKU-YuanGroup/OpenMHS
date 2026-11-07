"""ROS-free contract fake (analytic stand-in) for the iGibson RGB camera.

The fake answers one fixed ``sensor_msgs/Image`` subscription on the absolute
``/gibson_ros/camera/rgb/image`` topic.  It contacts no ROS graph, iGibson,
renderer or upstream node.  Every pixel, dimension, frame id, sequence and
stamp below is synthesized placeholder test data; this is not a replay of
captured ROS traffic.

The 2x2 frame is deliberately smaller than the configured 256x256 camera so
the receipt and artifact stay small.  The real dimensions and the
``camera_depth_optical_frame`` frame id are source facts in the driver.
"""

import base64

from mhs.bridge.ros_transport import RecordingRosTransport

TOPIC = "/gibson_ros/camera/rgb/image"
TYPE = "sensor_msgs/Image"


def _b64(payload: bytes) -> str:
    return base64.b64encode(payload).decode("ascii")


class FakeSimIgibsonRos(RecordingRosTransport):
    def __init__(self, *, publish: bool = True, malformed_step: bool = False,
                 unsupported_encoding: bool = False, missing_header_seq: bool = False,
                 **_options):
        super().__init__(handler=self._respond)
        self.width = 2                        # placeholder
        self.height = 2                       # placeholder
        self.sequence = 7                     # placeholder
        self.stamp_secs = 12                  # placeholder
        self.stamp_nsecs = 340000000          # placeholder
        self.frame_id = "fake_camera_frame"   # placeholder
        # 2x2 rgb8 placeholder pixels.
        self.pixels = bytes([
            10, 20, 30, 40, 50, 60,             # placeholder row 0
            70, 80, 90, 100, 110, 120,          # placeholder row 1
        ])
        self.publish = bool(publish)                          # placeholder negative-path switch
        self.malformed_step = bool(malformed_step)            # placeholder negative-path switch
        self.unsupported_encoding = bool(unsupported_encoding)  # placeholder negative-path switch
        self.missing_header_seq = bool(missing_header_seq)    # placeholder negative-path switch
        self.subscription_count = 0                           # placeholder counter

    def _header(self):
        header = {
            "seq": self.sequence,                                  # placeholder
            "stamp": {"secs": self.stamp_secs, "nsecs": self.stamp_nsecs},  # placeholder
            "frame_id": self.frame_id,                             # placeholder
        }
        if self.missing_header_seq:
            header.pop("seq")
        return header

    def _message(self):
        step = self.width * 3                                      # placeholder
        if self.malformed_step:
            step += 1                                              # placeholder
        return {
            "header": self._header(),
            "height": self.height,                                 # placeholder
            "width": self.width,                                   # placeholder
            "encoding": "yuv422" if self.unsupported_encoding else "rgb8",  # placeholder
            "is_bigendian": 0,                                     # placeholder
            "step": step,                                          # placeholder
            "data": _b64(self.pixels),                             # placeholder
        }

    def _respond(self, message):
        if message.get("op") != "subscribe":
            return None
        if message.get("topic") != TOPIC or message.get("type") != TYPE:
            return None
        self.subscription_count += 1                               # placeholder counter
        if not self.publish:
            return None
        return {
            "op": "publish",
            "topic": TOPIC,
            "id": message.get("id"),
            "msg": self._message(),
        }

"""ROS-free protocol fake for the pinned kinect2_bridge SD wire contract.

The fake answers the four fixed rosbridge subscriptions the driver
declares: ``/kinect2/sd/image_color_rect`` with a BGR8
``sensor_msgs/Image`` message, ``/kinect2/sd/image_depth_rect`` and
``/kinect2/sd/image_ir`` with 16UC1 ``sensor_msgs/Image`` messages, and
``/kinect2/sd/camera_info`` with a CameraInfo-shaped message carrying the
geometry fields the driver reads.  It contacts no ROS graph and no camera.

The responses are synthesized from placeholder data, not replayed from
captured ROS traffic.  Every value below is test data, not a device fact.
The 4x2 placeholder frames are deliberately smaller than the pinned SD
streams (512x424); the real capture size is fixed by the upstream node's
``sizeIr`` construction and is not changed by this fake.
"""

import base64

from mhs.bridge.ros_transport import RecordingRosTransport

IMAGE_TYPE = "sensor_msgs/Image"          # placeholder type token
INFO_TYPE = "sensor_msgs/CameraInfo"      # placeholder type token
COLOR_TOPIC = "/kinect2/sd/image_color_rect"   # placeholder test endpoint
DEPTH_TOPIC = "/kinect2/sd/image_depth_rect"   # placeholder test endpoint
IR_TOPIC = "/kinect2/sd/image_ir"              # placeholder test endpoint
INFO_TOPIC = "/kinect2/sd/camera_info"         # placeholder test endpoint


class FakeIaiKinect2(RecordingRosTransport):
    def __init__(self, *, malformed_step=False, unsupported_encoding=False,
                 missing_header_seq=False, **_options):
        super().__init__(handler=self._respond, max_message_bytes=4 * 1024 * 1024)  # placeholder budget
        self.width = 4                        # placeholder
        self.height = 2                       # placeholder
        self.frame_id = "kinect2_ir_optical_frame"  # placeholder
        self.sequence = 7                     # placeholder
        self.stamp_secs = 1                   # placeholder
        self.stamp_nsecs = 23456789           # placeholder
        self.subscribed_topics = []           # placeholder observation log
        self.silent_topics = set()            # placeholder negative-path control
        self.malformed_step = bool(malformed_step)              # placeholder negative-path switch
        self.unsupported_encoding = bool(unsupported_encoding)  # placeholder negative-path switch
        self.missing_header_seq = bool(missing_header_seq)      # placeholder negative-path switch
        self._pixels = {
            COLOR_TOPIC: bytes([                # placeholder BGR8 4x2 payload
                10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120,
                130, 140, 150, 160, 170, 180, 190, 200, 210, 220, 230, 240,
            ]),
            DEPTH_TOPIC: bytes([                # placeholder 16UC1 4x2 payload
                0, 0, 1, 0, 0, 1, 255, 255,
                2, 0, 3, 0, 4, 0, 5, 0,
            ]),
            IR_TOPIC: bytes([                   # placeholder 16UC1 4x2 payload
                16, 0, 32, 0, 48, 0, 64, 0,
                80, 0, 96, 0, 112, 0, 128, 0,
            ]),
        }
        self._encodings = {
            COLOR_TOPIC: ("bgr8", 3),           # placeholder
            DEPTH_TOPIC: ("16UC1", 2),          # placeholder
            IR_TOPIC: ("16UC1", 2),             # placeholder
        }

    def _header(self):
        header = {
            "seq": self.sequence,              # placeholder
            "stamp": {"secs": self.stamp_secs, "nsecs": self.stamp_nsecs},  # placeholder
            "frame_id": self.frame_id,         # placeholder
        }
        if self.missing_header_seq:
            header.pop("seq")
        return header

    def _image_message(self, topic):
        encoding, bytes_per_pixel = self._encodings[topic]
        if self.unsupported_encoding:
            encoding = "yuv422"                # placeholder unsupported encoding
        step = self.width * bytes_per_pixel    # placeholder
        if self.malformed_step:
            step += 1                          # placeholder malformed step
        return {
            "header": self._header(),
            "height": self.height,             # placeholder
            "width": self.width,               # placeholder
            "encoding": encoding,              # placeholder
            "is_bigendian": 0,                 # placeholder
            "step": step,                      # placeholder
            "data": base64.b64encode(self._pixels[topic]).decode("ascii"),  # placeholder
        }

    def _info_message(self):
        return {
            "header": self._header(),
            "height": self.height,             # placeholder
            "width": self.width,               # placeholder
            "distortion_model": "plumb_bob",   # placeholder
            # ROS 1 sensor_msgs/CameraInfo spells D, K, R and P in capitals, as
            # createCameraInfo writes them (kinect2_bridge.cpp:752-772).
            "D": [0.0, 0.0, 0.0, 0.0, 0.0],    # placeholder
            "K": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],  # placeholder
            "R": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],  # placeholder
            "P": [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0],  # placeholder
        }

    def _respond(self, message):
        if message.get("op") != "subscribe":
            return None
        topic = message.get("topic")
        expected_type = INFO_TYPE if topic == INFO_TOPIC else IMAGE_TYPE
        if message.get("type") != expected_type:
            return None
        if topic in self.silent_topics:
            return None
        if topic == INFO_TOPIC:
            self.subscribed_topics.append(topic)  # placeholder observation
            return {
                "op": "publish",
                "topic": topic,
                "id": message.get("id"),
                "msg": self._info_message(),
            }
        if topic in self._pixels:
            self.subscribed_topics.append(topic)  # placeholder observation
            return {
                "op": "publish",
                "topic": topic,
                "id": message.get("id"),
                "msg": self._image_message(topic),
            }
        return None

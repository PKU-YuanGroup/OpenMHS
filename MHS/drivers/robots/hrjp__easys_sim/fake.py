"""ROS-free contract fake for the Easys camera and balloon_detect image topics.

The fake answers the two fixed rosbridge Image subscriptions the driver
declares: the raw Gazebo camera on ``/camera`` and the detector output on
``/image_processed``.  It contacts no ROS graph, Gazebo renderer, camera or
``balloon_detect`` process.  Every pixel, frame id and stamp below is
synthesized placeholder data; this is not a replay of captured ROS traffic
and it does not show that a balloon was detected.

The detector publishes its output without assigning a header
(``balloon_detect.py:85-89``), so the fake answers ``/image_processed`` with a
zero stamp and an empty frame id instead of an invented frame; what cv_bridge
leaves in that header on a live graph was not checked.

The 2x2 frame is deliberately smaller than the pinned 320x240 sensor so the
receipts and artifacts stay small; the real dimensions are a source fact in
the driver.
"""

import base64
import copy

from mhs.bridge.ros_transport import RecordingRosTransport

RAW_TOPIC = "/camera"
DETECTED_TOPIC = "/image_processed"


def _b64(payload: bytes) -> str:
    return base64.b64encode(payload).decode("ascii")


class FakeEasysSim(RecordingRosTransport):
    def __init__(self, *, publish_camera: bool = True, publish_detected: bool = True,
                 malformed_image: bool = False, unsupported_encoding: bool = False,
                 include_header: bool = True, **_options):
        super().__init__(handler=self._respond)
        self.width = 2                     # placeholder
        self.height = 2                    # placeholder
        self.camera_frame_id = "fake_camera_frame"      # placeholder
        # placeholder: the detector assigns no header (balloon_detect.py:85-89), so its
        # output carries an empty frame id and a zero stamp here.
        self.detected_frame_id = ""
        # 2x2 rgb8 placeholder pixels for the raw stream.
        self.camera_data = _b64(bytes([
            10, 20, 30, 40, 50, 60,      # placeholder row 0
            70, 80, 90, 100, 110, 120,   # placeholder row 1
        ]))
        # 2x2 rgb8 placeholder pixels for the detector output (green boxes).
        self.detected_data = _b64(bytes([
            0, 255, 0, 0, 255, 0,        # placeholder row 0
            0, 255, 0, 0, 255, 0,        # placeholder row 1
        ]))
        self.publish_camera = bool(publish_camera)          # placeholder negative-path switch
        self.publish_detected = bool(publish_detected)      # placeholder negative-path switch
        self.malformed_image = bool(malformed_image)        # placeholder negative-path switch
        self.unsupported_encoding = bool(unsupported_encoding)  # placeholder negative-path switch
        self.include_header = bool(include_header)          # placeholder negative-path switch
        self.subscription_count = 0                        # placeholder counter
        self._seq = 0                                      # placeholder counter

    def _header(self, frame_id: str, *, stamped: bool = True):
        if not self.include_header:
            return {}
        if not stamped:
            # placeholder: the unassigned header of the detector output (zero stamp).
            return {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": frame_id}
        self._seq += 1  # placeholder
        return {
            "stamp": {"sec": self._seq, "nanosec": 0},  # placeholder
            "frame_id": frame_id,
        }

    def _message(self, topic: str, frame_id: str, data: str):
        message = {
            "header": self._header(frame_id, stamped=topic == RAW_TOPIC),
            "height": self.height,
            "width": self.width,
            "encoding": "bgr8x" if self.unsupported_encoding else "rgb8",  # placeholder encoding
            "is_bigendian": 0,  # placeholder
            "step": self.width * (2 if self.malformed_image else 3),  # placeholder
            "data": _b64(b"\x00" * (self.width * 2)) if self.malformed_image else data,
        }
        return {
            "op": "publish",
            "topic": topic,
            "id": None,
            "msg": message,
        }

    def _respond(self, message):
        if message.get("op") != "subscribe":
            return None
        topic = message.get("topic")
        if topic not in (RAW_TOPIC, DETECTED_TOPIC):
            return None
        self.subscription_count += 1  # placeholder counter
        if topic == RAW_TOPIC and not self.publish_camera:
            return None
        if topic == DETECTED_TOPIC and not self.publish_detected:
            return None
        reply = (self._message(RAW_TOPIC, self.camera_frame_id, self.camera_data)
                 if topic == RAW_TOPIC else
                 self._message(DETECTED_TOPIC, self.detected_frame_id, self.detected_data))
        reply["id"] = message.get("id")
        reply["msg"] = copy.deepcopy(reply["msg"])
        return reply

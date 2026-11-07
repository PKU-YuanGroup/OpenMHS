"""ROS-free contract fake for the LunarSim topic graph.

The fake answers the five subscriptions and records the one publication that
the pinned README declares.  It runs no LunarSim binary, ROS graph, physics
engine or camera.  Every value below is placeholder test data, not a device
fact and not a capture of simulator traffic.
"""

import base64
import copy

from mhs.bridge.ros_transport import RecordingRosTransport

POSE_TOPIC = "/lunarsim/gt/pose"
IMU_TOPIC = "/lunarsim/imu"
LEFT_TOPIC = "/lunarsim/camera_left/raw"
RIGHT_TOPIC = "/lunarsim/camera_right/raw"
DEPTH_TOPIC = "/lunarsim/camera_depth/depth"
CMD_VEL_TOPIC = "/cmd_vel"


def _stamp():
    return {"sec": 17, "nanosec": 123456789}  # placeholder


def _header(frame_id):
    return {"stamp": _stamp(), "frame_id": frame_id}  # placeholder frame ids


def _image(frame_id, encoding, width, height, step, pixels):
    return {
        "header": _header(frame_id),
        "height": height,                          # placeholder
        "width": width,                            # placeholder
        "encoding": encoding,                      # placeholder
        "is_bigendian": 0,                         # placeholder
        "step": step,                              # placeholder
        "data": base64.b64encode(pixels).decode("ascii"),  # placeholder
    }


class FakeLunarsim(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.last_twist = None          # placeholder observation of the last publication
        self.published = []             # placeholder publication log
        self.silent_topics = set()      # placeholder negative-path control
        self.pose = {                   # placeholder ground-truth sample
            "header": _header("map"),
            "pose": {
                "position": {"x": 1.0, "y": 2.0, "z": 0.5},                    # placeholder
                "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},       # placeholder
            },
        }
        self.imu = {                    # placeholder inertial sample
            "header": _header("imu_link"),
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},           # placeholder
            "angular_velocity": {"x": 0.0, "y": 0.0, "z": 0.1},                # placeholder
            "linear_acceleration": {"x": 0.0, "y": 0.0, "z": 9.81},            # placeholder
        }
        self.images = {                 # placeholder camera packets
            LEFT_TOPIC: _image(
                "camera_left_optical_frame", "bgr8", 4, 2, 12,                 # placeholder
                bytes([10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120,     # placeholder
                       130, 140, 150, 160, 170, 180, 190, 200, 210, 220, 230, 240]),  # placeholder
            ),
            RIGHT_TOPIC: _image(
                "camera_right_optical_frame", "bgr8", 4, 2, 12,                # placeholder
                bytes([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12,                  # placeholder
                       13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24]),       # placeholder
            ),
            DEPTH_TOPIC: _image(
                "camera_depth_optical_frame", "16UC1", 4, 2, 8,                # placeholder
                bytes([0, 0, 1, 0, 0, 1, 255, 255,                             # placeholder
                       2, 0, 3, 0, 4, 0, 5, 0]),                               # placeholder
            ),
        }

    def _respond(self, message):
        operation = message.get("op")
        if operation == "publish":
            if message.get("topic") == CMD_VEL_TOPIC:
                self.last_twist = copy.deepcopy(message.get("msg"))
                self.published.append(copy.deepcopy(message.get("msg")))
            return None
        if operation != "subscribe":
            return None
        topic = message.get("topic")
        if topic in self.silent_topics:
            return None
        if topic == POSE_TOPIC:
            body = copy.deepcopy(self.pose)
        elif topic == IMU_TOPIC:
            body = copy.deepcopy(self.imu)
        elif topic in self.images:
            body = copy.deepcopy(self.images[topic])
        else:
            return None
        return {"op": "publish", "topic": topic, "id": message.get("id"), "msg": body}

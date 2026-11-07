"""ROS-free canned fake for the MuJoCo ROS utilities plugin contract.

The fake models the wire contract declared in ``driver.py``:

* subscriptions to ``/clock`` (``rosgraph_msgs/msg/Clock``), ``/pose``
  (``geometry_msgs/msg/PoseStamped``), ``/vel``
  (``geometry_msgs/msg/TwistStamped``) and ``/box_rangefinder``
  (``mujoco_ros_utils/msg/ScalarStamped``);
* an advertise and a publish of ``std_msgs/msg/Float64`` on ``/camera_pan``.

It is an analytic contract stand-in, not a recording of captured traffic.  It
runs no ROS, MuJoCo plugin, physics or wall-clock loop.  Every number below is
test data and is marked ``# placeholder``; none is a device fact or a safety
limit.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeMujocoRosUtils(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.clock_sec = 12                  # placeholder
        self.clock_nanosec = 340000000       # placeholder
        self.pose_x = 0.0                    # placeholder
        self.pose_y = 0.0                    # placeholder
        self.pose_z = 1.0                    # placeholder
        self.twist_linear_x = 0.0            # placeholder
        self.twist_angular_z = 0.0           # placeholder
        self.rangefinder_distance = 0.5      # placeholder
        self.last_actuator_command = None    # placeholder echo state
        self.reject_publish = False          # placeholder negative-path switch
        self.omit_pose = False               # placeholder negative-path switch

    @staticmethod
    def _header(frame_id):
        return {
            "stamp": {"sec": 12, "nanosec": 340000000},  # placeholder
            "frame_id": frame_id,
        }

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            return self._observation(message)
        if operation == "advertise":
            return None
        if operation == "publish":
            self._record_publish(message)
            return None
        return None

    def _observation(self, message):
        topic = message.get("topic")
        ident = message.get("id")
        if topic == "/clock":
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {"clock": {"sec": self.clock_sec, "nanosec": self.clock_nanosec}},  # placeholder
            }
        if topic == "/pose":
            if self.omit_pose:
                return None
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "header": self._header("map"),  # placeholder frame name
                    "pose": {
                        "position": {"x": self.pose_x, "y": self.pose_y, "z": self.pose_z},  # placeholder
                        "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
                    },
                },
            }
        if topic == "/vel":
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "header": self._header("map"),  # placeholder frame name
                    "twist": {
                        "linear": {"x": self.twist_linear_x, "y": 0.0, "z": 0.0},  # placeholder
                        "angular": {"x": 0.0, "y": 0.0, "z": self.twist_angular_z},  # placeholder
                    },
                },
            }
        if topic == "/box_rangefinder":
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "header": self._header("map"),  # placeholder frame name
                    "value": {"data": self.rangefinder_distance},  # placeholder
                },
            }
        return None

    def _record_publish(self, message):
        if self.reject_publish:
            raise RuntimeError("fake rosbridge transport rejected the publication")  # placeholder
        if message.get("topic") == "/camera_pan":
            body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
            value = body.get("data")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                self.last_actuator_command = float(value)  # placeholder echo only

"""ROS-free contract fake for the src_dog rosbridge endpoints.

The fake models the pinned upstream wire contract: a flat Float64MultiArray
publication on the Gazebo effort-controller command topic, sensor_msgs/JointState
on /dog/joint_states, sensor_msgs/Imu on /dog/imu and nav_msgs/Odometry on
/ground_truth/state.  It runs no ROS, Gazebo, controller or physics.  The first
desired-position field of a publication is echoed into the placeholder base x so
an in-process test can see that the message arrived; that echo is not physics.

All numeric state below is placeholder test data, not a device fact.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

#: The twelve joints named by the default controller configuration.
JOINT_NAMES = (
    "fl_hip_x", "fl_hip_y", "fl_knee",
    "fr_hip_x", "fr_hip_y", "fr_knee",
    "bl_hip_x", "bl_hip_y", "bl_knee",
    "br_hip_x", "br_hip_y", "br_knee",
)


class FakeSrcDog(RecordingRosTransport):
    """A deterministic rosbridge peer with placeholder observations."""

    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.joint_names = list(JOINT_NAMES)
        self.joint_positions = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                                0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # placeholder
        self.base_position = {"x": 0.0, "y": 0.0, "z": 0.4}  # placeholder
        self.orientation = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}  # placeholder
        self.angular_velocity = {"x": 0.0, "y": 0.0, "z": 0.0}  # placeholder
        self.linear_acceleration = {"x": 0.0, "y": 0.0, "z": 0.0}  # placeholder
        self.command_topic = "/dog/gazebo_pve_controller/command"
        self.last_command = None
        self.publish_count = 0
        self.silent = False                 # placeholder negative-path switch
        self.wrong_joint_state = False      # placeholder negative-path switch

    def _respond(self, message):
        operation = message.get("op")
        ident = message.get("id")
        if operation == "subscribe":
            if self.silent:
                return None
            topic = message.get("topic")
            if topic == "/dog/joint_states":
                return {
                    "op": "publish",
                    "topic": topic,
                    "id": ident,
                    "msg": self._joint_state(),
                }
            if topic == "/dog/imu":
                return {
                    "op": "publish",
                    "topic": topic,
                    "id": ident,
                    "msg": {
                        "header": {"stamp": {"secs": 0, "nsecs": 0}},  # placeholder
                        "orientation": dict(self.orientation),
                        "angular_velocity": dict(self.angular_velocity),
                        "linear_acceleration": dict(self.linear_acceleration),
                    },
                }
            if topic == "/ground_truth/state":
                return {
                    "op": "publish",
                    "topic": topic,
                    "id": ident,
                    "msg": {
                        "header": {"stamp": {"secs": 0, "nsecs": 0}},  # placeholder
                        "pose": {
                            "pose": {
                                "position": dict(self.base_position),
                                "orientation": dict(self.orientation),
                            }
                        },
                        "twist": {
                            "twist": {
                                "linear": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
                                "angular": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
                            }
                        },
                    },
                }
            return None
        if operation == "publish":
            if message.get("topic") == self.command_topic:
                msg = message.get("msg")
                self.publish_count += 1
                self.last_command = msg
                data = msg.get("data") if isinstance(msg, dict) else None
                if isinstance(data, list) and data:
                    # Placeholder contract echo only: the first desired-position
                    # field is copied into the fake pose so a test can see that
                    # the publication arrived.  This is not physics.
                    self.base_position["x"] = float(data[0])
            return None
        if operation in ("advertise", "unadvertise", "unsubscribe"):
            return None
        return None

    def _joint_state(self):
        msg = {
            "header": {"stamp": {"secs": 0, "nsecs": 0}, "frame_id": ""},  # placeholder
            "name": list(self.joint_names),
            "velocity": [0.0] * 12,  # placeholder
            "effort": [0.0] * 12,    # placeholder
        }
        if not self.wrong_joint_state:
            msg["position"] = list(self.joint_positions)
        return msg

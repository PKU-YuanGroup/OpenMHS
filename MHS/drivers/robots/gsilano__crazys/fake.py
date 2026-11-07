"""ROS-free analytic transport fake for the CrazyS Crazyflie endpoints.

The fake models the two pinned wire endpoints declared in ``driver.py``: a
``mav_msgs/RollPitchYawrateThrustCrazyflie`` publication on the Crazyflie
command topic and a ``nav_msgs/Odometry`` subscription on the ideal odometry
topic, and the companion gazebo_ros services ``/gazebo/pause_physics`` and
``/gazebo/get_physics_properties`` (the e-stop and its read-back).  A paused
flag stands for the Gazebo world's: the pause sets it, the read-back reports it,
the odometry is silent while it is set, and a command stored while paused moves
nothing.  It is an analytic stand-in, not a recording of captured traffic and
not the Gazebo simulator.  It runs no physics, controller or ROS graph.

Every number below is test data, not a device fact; each invented value is
marked ``# placeholder``.  Missing fields in the publisher's message stay
missing to exercise the real rosbridge shape, and the negative-path switches
exercise a silent odometry topic and a failed transport send.
"""

import copy

from mhs.bridge.ros_transport import RecordingRosTransport

_COMMAND_TOPIC = "/crazyflie2/command/roll_pitch_yawrate_thrust"
_COMMAND_TYPE = "mav_msgs/RollPitchYawrateThrustCrazyflie"
_ODOMETRY_TOPIC = "/crazyflie2/odometry_sensor1/odometry"
_ODOMETRY_TYPE = "nav_msgs/Odometry"


class FakeCrazys(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # placeholder state: the last message accepted by the transport
        self.command = {
            "roll": 0.0,       # placeholder
            "pitch": 0.0,      # placeholder
            "yaw_rate": 0.0,   # placeholder
            "thrust": 0.0,     # placeholder
        }
        # placeholder odometry sample in the ROS 1 nav_msgs/Odometry shape (Header with seq and
        # secs/nsecs, child_frame_id, PoseWithCovariance, TwistWithCovariance); no dynamics or clock
        self.odometry = {
            "header": {
                "seq": 0,  # placeholder
                "frame_id": "world",  # placeholder
                "stamp": {"secs": 0, "nsecs": 0},  # placeholder
            },
            "child_frame_id": "crazyflie2/odometry_sensor1",  # placeholder
            "pose": {"pose": {
                "position": {"x": 0.0, "y": 0.0, "z": 1.0},  # placeholder
                "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
            }, "covariance": [0.0] * 36},  # placeholder
            "twist": {"twist": {
                "linear": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
                "angular": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
            }, "covariance": [0.0] * 36},  # placeholder
        }
        self.silent_odometry = False  # placeholder negative-path switch
        self.fail_publish = False     # placeholder negative-path switch
        self.paused = False           # placeholder: the fake starts running (the launch starts paused)
        self.fail_pause = False       # placeholder negative-path switch: the pause is not answered
        self.fail_readback = False    # placeholder negative-path switch: a non-ODE engine (success false)
        self.ignore_pause = False     # placeholder negative-path switch: another client unpaused

    def send(self, message, *, timeout_s=None):
        """Raise before the command publication when the negative switch is set."""
        if (self.fail_publish and isinstance(message, dict)
                and message.get("op") == "publish"
                and message.get("topic") == _COMMAND_TOPIC):
            raise ConnectionError("fake command transport failure")  # placeholder
        return super().send(message, timeout_s=timeout_s)

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if (message.get("topic") == _ODOMETRY_TOPIC
                    and message.get("type") == _ODOMETRY_TYPE
                    and not self.silent_odometry and not self.paused):
                return {
                    "op": "publish",
                    "topic": _ODOMETRY_TOPIC,
                    "id": message.get("id"),
                    "msg": copy.deepcopy(self.odometry),
                }
            return None
        if operation == "publish":
            # rosbridge publish messages carry the topic but not the type; the
            # preceding advertise message carries the type.
            if (message.get("topic") == _COMMAND_TOPIC
                    and isinstance(message.get("msg"), dict)):
                self.command = dict(message["msg"])
                if not self.paused:
                    # Placeholder analytic response, not physics: move the sample a little so a caller can see
                    # that the command reached the fake; a paused world moves nothing (the command is stored).
                    self.odometry["pose"]["pose"]["position"]["x"] += self.command.get("roll", 0.0) * 0.01
                    self.odometry["pose"]["pose"]["position"]["y"] += self.command.get("pitch", 0.0) * 0.01
                    self.odometry["pose"]["pose"]["position"]["z"] += self.command.get("thrust", 0.0) * 0.01
            return None
        if operation in ("advertise", "unadvertise", "unsubscribe"):
            return None
        if operation == "call_service":
            service = message.get("service")
            if service == "/gazebo/pause_physics":
                if self.fail_pause:
                    return None  # no answer: the e-stop's request times out
                self.paused = True
                return {"op": "service_response", "service": service, "id": message.get("id"), "result": True,
                        "values": {}}
            if service == "/gazebo/get_physics_properties":
                if self.fail_readback:
                    return {"op": "service_response", "service": service, "id": message.get("id"), "result": False,
                            "values": "get_physics_properties not supported"}  # placeholder
                return {"op": "service_response", "service": service, "id": message.get("id"), "result": True,
                        "values": {"time_step": 0.001, "pause": self.paused and not self.ignore_pause,  # placeholder
                                   "max_update_rate": 1000.0, "gravity": {"x": 0.0, "y": 0.0, "z": -9.8},
                                   "ode_config": {}, "success": True, "status_message": "placeholder"}}
            return {"op": "service_response", "service": service, "id": message.get("id"), "result": False,
                    "values": "no other service is declared for the CrazyS surface"}  # placeholder
        return None

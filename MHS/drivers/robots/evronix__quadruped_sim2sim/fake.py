"""ROS-free protocol fake for the pinned evronix quadruped ROS 2 endpoints.

The fake models the wire contract declared in ``driver.py``: one
``geometry_msgs/msg/PoseStamped`` publication on ``/robot_velocity_command``
and one-message subscriptions to ``sensor_msgs/msg/JointState`` on
``/joint_states`` and ``sensor_msgs/msg/Imu`` on ``/imu_plugin/out``.

It also answers the companion gazebo_ros services ``/pause_physics`` and
``/get_model_list`` (the e-stop and its stall read-back): a paused flag stands
for the Gazebo world's, ``get_model_list`` stamps each answer with a
placeholder sim time that advances on every answer unless the flag is set, and
both observations are silent while it is set.

It is an analytic contract stand-in, not a replay of captured ROS traffic.
It opens no ROS node, starts no Gazebo server and runs no policy inference.
Every value below is test data and is marked ``# placeholder``; none is a
device fact or a bound.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeQuadrupedSim2sim(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.joint_names = [                         # placeholder
            "FL_hip_joint", "FL_thigh_joint", "FL_calf_joint",       # placeholder
            "FR_hip_joint", "FR_thigh_joint", "FR_calf_joint",       # placeholder
            "RL_hip_joint", "RL_thigh_joint", "RL_calf_joint",       # placeholder
            "RR_hip_joint", "RR_thigh_joint", "RR_calf_joint",       # placeholder
        ]
        self.joint_positions = [0.0] * 12            # placeholder
        self.joint_velocities = [0.0] * 12           # placeholder
        self.joint_efforts = [0.0] * 12              # placeholder
        self.stamp_sec = 12                           # placeholder
        self.stamp_nanosec = 340000000                # placeholder
        self.frame_id = "base"                        # placeholder
        self.orientation = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}  # placeholder
        self.angular_velocity = {"x": 0.0, "y": 0.0, "z": 0.0}       # placeholder
        self.linear_acceleration = {"x": 0.0, "y": 0.0, "z": 0.0}    # placeholder

        # Negative-path switches used by the repository tests.
        self.silent = False              # placeholder
        self.wrong_id = False            # placeholder
        self.fail_subscribe = False      # placeholder
        self.fail_publish = False        # placeholder
        self.malformed = None            # placeholder

        # The Gazebo world's paused flag and the stall read-back's sim time (placeholders) and their switches.
        self.paused = False              # placeholder: the fake starts running
        self.sim_ns = 3_000_000_000      # placeholder sim time, advances 1 ms per answer while running
        self.fail_pause = False          # placeholder: the pause is not answered
        self.ignore_pause = False        # placeholder: the world keeps running
        self.fail_model_list = False     # placeholder: the read-back fails

        # Recording helpers for assertions; they carry no device meaning.
        self.last_velocity = None        # placeholder
        self.published = []
        self.subscriptions = 0           # placeholder counter

    def _imu_message(self):
        message = {
            "header": {
                "stamp": {"sec": self.stamp_sec, "nanosec": self.stamp_nanosec},  # placeholder
                "frame_id": self.frame_id,
            },
            "orientation": dict(self.orientation),
            "orientation_covariance": [0.0] * 9,       # placeholder
            "angular_velocity": dict(self.angular_velocity),
            "angular_velocity_covariance": [0.0] * 9,  # placeholder
            "linear_acceleration": dict(self.linear_acceleration),
            "linear_acceleration_covariance": [0.0] * 9,  # placeholder
        }
        if self.malformed == "missing_header":
            message.pop("header")
        elif self.malformed == "missing_orientation":
            message.pop("orientation")
        elif self.malformed == "missing_linear_acceleration":
            message.pop("linear_acceleration")
        elif self.malformed == "missing_angular_velocity":
            message.pop("angular_velocity")
        elif self.malformed == "string_orientation":
            message["orientation"]["x"] = "not-a-number"  # placeholder
        elif self.malformed == "bad_stamp":
            message["header"]["stamp"] = {"sec": "not-an-integer", "nanosec": 0}  # placeholder
        return message

    def _joint_state_message(self):
        message = {
            "header": {
                "stamp": {"sec": self.stamp_sec, "nanosec": self.stamp_nanosec},  # placeholder
                "frame_id": self.frame_id,
            },
            "name": list(self.joint_names),
            "position": list(self.joint_positions),
            "velocity": list(self.joint_velocities),
            "effort": list(self.joint_efforts),
        }
        if self.malformed == "missing_header":
            message.pop("header")
        elif self.malformed == "missing_position":
            message.pop("position")
        elif self.malformed == "short_position":
            message["position"] = message["position"][:1]  # placeholder
        elif self.malformed == "string_position":
            message["position"][0] = "not-a-number"        # placeholder
        return message

    def _observation(self, message):
        self.subscriptions += 1
        topic = message.get("topic")
        if self.fail_subscribe:
            raise ConnectionError("simulated ROS subscription failure")  # placeholder
        if topic not in ("/joint_states", "/imu_plugin/out"):
            return None
        if self.silent or self.paused:
            return None  # a paused world runs no joint_state_broadcaster update and no IMU plugin
        body = self._joint_state_message() if topic == "/joint_states" else self._imu_message()
        event = {
            "op": "publish",
            "topic": topic,
            "id": message.get("id"),
            "msg": body,
        }
        if self.wrong_id:
            event["id"] = "not-the-subscription-id"  # placeholder
        return event

    def _publish(self, message):
        if message.get("topic") != "/robot_velocity_command":
            return None
        if self.fail_publish:
            raise ConnectionError("simulated ROS publication failure")  # placeholder
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        pose = body.get("pose") if isinstance(body.get("pose"), dict) else {}
        position = pose.get("position") if isinstance(pose.get("position"), dict) else {}
        self.last_velocity = {
            "x": position.get("x"),   # placeholder echo
            "y": position.get("y"),   # placeholder echo
            "z": position.get("z"),   # placeholder echo
        }
        self.published.append(message)
        return None

    def _service(self, message):
        service = message.get("service")
        reply = {"op": "service_response", "service": service, "id": message.get("id"), "result": True}
        if service == "/pause_physics":
            if self.fail_pause:
                return None  # no answer: the e-stop's request times out
            self.paused = True
            return dict(reply, values={})
        if service == "/get_model_list":
            if self.fail_model_list:
                return dict(reply, result=False, values="get_model_list failed")  # placeholder
            if not self.paused or self.ignore_pause:
                self.sim_ns += 1_000_000  # placeholder: a running world's sim time advances
            stamp = {"sec": self.sim_ns // 1_000_000_000, "nanosec": self.sim_ns % 1_000_000_000}
            return dict(reply, values={"header": {"stamp": stamp, "frame_id": ""},
                                       "model_names": ["ground_plane", "go1"], "success": True})  # placeholder
        return dict(reply, result=False, values={})

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            return self._observation(message)
        if operation == "publish":
            return self._publish(message)
        if operation == "call_service":
            return self._service(message)
        return None

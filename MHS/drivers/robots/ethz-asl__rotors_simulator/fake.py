"""ROS-free recording fake for the pinned RotorS Gazebo ROS endpoints and the companion Gazebo pause.

The fake models the declared rosbridge contract only: the
``/firefly/odometry_sensor1/odometry`` ``nav_msgs/Odometry`` and ``/firefly/imu``
``sensor_msgs/Imu`` subscriptions, and the companion gazebo_ros services
``/gazebo/pause_physics`` and ``/gazebo/get_physics_properties`` (the e-stop and
its read-back).  A paused flag stands for the Gazebo world's: the pause sets it,
the read-back reports it, and both topics are silent while it is set (a paused
world runs no plugin update).  It runs no Gazebo physics, controller or sensor
model.  Every number below is test data and is marked ``# placeholder``; none is
a device fact, a limit or a reference.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeRotorsSimulator(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        #: The fake starts running so the observations can be exercised (the real hovering launch starts paused
        #: and hovering_example unpauses it).
        self.paused = False  # placeholder
        self.drop_odometry = False  # placeholder negative-path switch
        self.drop_imu = False  # placeholder negative-path switch
        self.fail_pause = False  # placeholder negative-path switch: the pause is not answered
        self.fail_readback = False  # placeholder negative-path switch: a non-ODE engine (success false, call fails)
        self.ignore_pause = False  # placeholder negative-path switch: another client unpaused (read-back false)

    def _odometry_message(self):
        return {
            "header": {
                "seq": 1,  # placeholder
                "stamp": {"secs": 12, "nsecs": 340000000},  # placeholder
                "frame_id": "world",
            },
            "child_frame_id": "firefly/odometry_sensor1",
            "pose": {
                "pose": {
                    "position": {"x": 0.0, "y": 0.0, "z": 1.0},  # placeholder
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
                },
                "covariance": [0.0] * 36,  # placeholder
            },
            "twist": {
                "twist": {
                    "linear": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
                    "angular": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
                },
                "covariance": [0.0] * 36,  # placeholder
            },
        }

    def _imu_message(self):
        return {
            "header": {
                "seq": 1,  # placeholder
                "stamp": {"secs": 12, "nsecs": 340000000},  # placeholder
                "frame_id": "firefly/imu",
            },
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
            "orientation_covariance": [0.0] * 9,  # placeholder
            "angular_velocity": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
            "angular_velocity_covariance": [0.0] * 9,  # placeholder
            "linear_acceleration": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
            "linear_acceleration_covariance": [0.0] * 9,  # placeholder
        }

    def _physics(self):
        return {"time_step": 0.001, "pause": self.paused and not self.ignore_pause,  # placeholder
                "max_update_rate": 1000.0, "gravity": {"x": 0.0, "y": 0.0, "z": -9.8},  # placeholder
                "ode_config": {}, "success": True, "status_message": "GetPhysicsProperties: got properties"}

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if self.paused:
                return None  # a paused world publishes no plugin output
            topic = message.get("topic")
            if topic == "/firefly/odometry_sensor1/odometry" and not self.drop_odometry:
                return {"op": "publish", "topic": topic, "id": message.get("id"), "msg": self._odometry_message()}
            if topic == "/firefly/imu" and not self.drop_imu:
                return {"op": "publish", "topic": topic, "id": message.get("id"), "msg": self._imu_message()}
            return None
        if operation != "call_service":
            return None
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
                    "values": self._physics()}
        return {"op": "service_response", "service": service, "id": message.get("id"), "result": False, "values": {}}

"""ROS-free protocol fake for the Coppolam ROS MAV swarm simulator package.

The fake models the declared rosbridge wire contract for one uav: a
nav_msgs/Odometry subscription, a geometry_msgs/Twist publication, the
hector_uav_msgs/EnableMotors service, the ROS 1 actionlib landing action, and
the companion gazebo_ros services ``/gazebo/pause_physics`` and
``/gazebo/get_physics_properties``.  A paused flag stands for the Gazebo
world's: the pause sets it, the read-back reports it, ground-truth odometry
is silent while it is set, and a stored cmd_vel moves no placeholder pose.
It contacts no ROS graph, Gazebo, hector_quadrotor or mav_controller node.
Every numeric value below is synthesized test data, not an upstream fact.
This is an analytic protocol stand-in, not a replay of captured ROS traffic.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

ODOM_TOPIC = "/uav1/ground_truth/state"
CMD_TOPIC = "/uav1/cmd_vel"
ARM_SERVICE = "/uav1/enable_motors"
LAND_ACTION = "/uav1/action/landing"


class FakeMavSwarm(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.odom_frame_id = "world"  # placeholder
        self.odom_position = {"x": 0.5, "y": 0.5, "z": 0.3}  # placeholder
        self.odom_orientation = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}  # placeholder
        self.odom_linear = {"x": 0.0, "y": 0.0, "z": 0.0}  # placeholder
        self.odom_angular = {"x": 0.0, "y": 0.0, "z": 0.0}  # placeholder
        self._odom_seq = 0  # placeholder
        self.motors_enabled = False
        self.landed = False
        self.last_cmd_vel = None
        self.fail_arm_service = False
        self.fail_arm_application = False
        self.fail_landing = False
        self.malformed_landing = False
        self.omit_odometry = False
        self.paused = False                 # placeholder: the fake starts running (normal.launch paused default false)
        self.fail_pause = False             # placeholder negative-path switch: the pause is not answered
        self.fail_readback = False          # placeholder negative-path switch: a non-ODE engine
        self.ignore_pause = False           # placeholder negative-path switch: another client left pause false
        self.stored_twist = None            # placeholder: twist_command_ kept across a pause

    def _odometry(self):
        self._odom_seq += 1  # placeholder
        return {
            "header": {
                "frame_id": self.odom_frame_id,
                "stamp": {"secs": 0, "nsecs": 0},  # placeholder
                "seq": self._odom_seq,  # placeholder
            },
            "child_frame_id": "uav1/base_link",  # placeholder
            "pose": {"pose": {
                "position": dict(self.odom_position),
                "orientation": dict(self.odom_orientation),
            }},
            "twist": {"twist": {
                "linear": dict(self.odom_linear),
                "angular": dict(self.odom_angular),
            }},
        }

    def _landing_result(self, goal_id, status, values):
        return {
            "op": "publish",
            "topic": LAND_ACTION + "/result",
            "id": str(goal_id) + ":result",
            "msg": {
                "status": {
                    "goal_id": {"id": goal_id},
                    "status": status,
                },
                "result": values,
            },
        }

    def _apply_cmd_vel(self, message):
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        linear = body.get("linear") if isinstance(body.get("linear"), dict) else {}
        angular = body.get("angular") if isinstance(body.get("angular"), dict) else {}
        self.last_cmd_vel = body
        self.stored_twist = {
            "linear": {
                "x": float(linear.get("x", 0.0)),  # placeholder
                "y": float(linear.get("y", 0.0)),  # placeholder
                "z": float(linear.get("z", 0.0)),  # placeholder
            },
            "angular": {
                "x": float(angular.get("x", 0.0)),  # placeholder
                "y": float(angular.get("y", 0.0)),  # placeholder
                "z": float(angular.get("z", 0.0)),  # placeholder
            },
        }
        # A paused world does not step the controller, so the stored twist moves nothing.
        # While running, the placeholder pose changes so the explicit odometry read can differ;
        # it is not Gazebo or controller dynamics, and the device resource does not read it.
        if self.paused:
            return
        self.odom_position["x"] = float(linear.get("x", 0.0)) + self.odom_position["x"]  # placeholder
        self.odom_position["y"] = float(linear.get("y", 0.0)) + self.odom_position["y"]  # placeholder
        self.odom_position["z"] = float(linear.get("z", 0.0)) + self.odom_position["z"]  # placeholder
        self.odom_linear = dict(self.stored_twist["linear"])
        self.odom_angular = dict(self.stored_twist["angular"])

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if message.get("topic") == ODOM_TOPIC and not self.omit_odometry and not self.paused:
                return {
                    "op": "publish",
                    "topic": ODOM_TOPIC,
                    "id": message.get("id"),
                    "msg": self._odometry(),
                }
            return None
        if operation == "advertise" or operation == "unadvertise":
            return None
        if operation == "unsubscribe":
            return None
        if operation == "publish":
            topic = message.get("topic")
            if topic == CMD_TOPIC:
                self._apply_cmd_vel(message)
                return None
            if topic == LAND_ACTION + "/goal":
                body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
                envelope = body.get("goal_id") if isinstance(body.get("goal_id"), dict) else {}
                goal_id = envelope.get("id")
                if not isinstance(goal_id, str) or not goal_id:
                    return None
                if self.paused:
                    # The pose controller does not update while the world is paused, so the landing
                    # action cannot succeed.  Abort at once; do not report landed and do not wait out
                    # the upstream action timeout.
                    return self._landing_result(goal_id, 4, {})  # placeholder status: ABORTED
                if self.fail_landing:
                    return self._landing_result(goal_id, 4, {})  # placeholder status: ABORTED
                if self.malformed_landing:
                    return {
                        "op": "publish",
                        "topic": LAND_ACTION + "/result",
                        "id": goal_id + ":result",
                        "msg": {
                            "status": {
                                "goal_id": {"id": goal_id},
                                "status": 3,  # placeholder status: SUCCEEDED
                            },
                            "result": None,
                        },
                    }
                self.landed = True
                self.motors_enabled = False
                return self._landing_result(goal_id, 3, {})  # placeholder status: SUCCEEDED
            if topic == LAND_ACTION + "/cancel":
                return None
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
                    return {"op": "service_response", "service": service, "id": message.get("id"),
                            "result": False, "values": "get_physics_properties not supported"}  # placeholder
                return {"op": "service_response", "service": service, "id": message.get("id"), "result": True,
                        "values": {"time_step": 0.001, "pause": self.paused and not self.ignore_pause,  # placeholder
                                   "max_update_rate": 1000.0, "gravity": {"x": 0.0, "y": 0.0, "z": -9.8},
                                   "ode_config": {}, "success": True, "status_message": "placeholder"}}
            if service == ARM_SERVICE:
                if self.fail_arm_service:
                    return {"op": "service_response", "service": service, "id": message.get("id"),
                            "result": False, "values": {}}
                args = message.get("args") if isinstance(message.get("args"), dict) else {}
                enabled = args.get("enable")
                if self.fail_arm_application:
                    return {"op": "service_response", "service": service, "id": message.get("id"),
                            "result": True, "values": {"success": False}}
                self.motors_enabled = bool(enabled)
                return {"op": "service_response", "service": service, "id": message.get("id"),
                        "result": True, "values": {"success": True}}
            return {"op": "service_response", "service": service, "id": message.get("id"),
                    "result": False, "values": {}}
        return None

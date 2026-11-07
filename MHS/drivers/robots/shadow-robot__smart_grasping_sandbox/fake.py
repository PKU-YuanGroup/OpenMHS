"""ROS-free contract fake for the Smart Grasping Sandbox ROS endpoints.

The fake models only the wire contract declared in ``driver.py``: the
``/joint_states`` publication, the Gazebo pause/unpause/reset services, the
``/gazebo/get_model_state`` observation and the fixed
``/gazebo/set_model_configuration`` commands.  It runs no Gazebo, ros_control,
MoveIt or ODE code and does not replay captured traffic.  All numeric state
below is test data, not a device fact.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeSmartGraspingSandbox(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.paused = False                    # placeholder state
        self.reset_count = 0                   # placeholder counter
        self.last_configuration = None         # placeholder request record
        # Placeholder joint sample in the 15-joint order of the upstream model.
        self.joint_names = [                                                     # placeholder sample order
            "shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint",
            "wrist_1_joint", "wrist_2_joint", "wrist_3_joint",
            "H1_F1J1", "H1_F1J2", "H1_F1J3",
            "H1_F2J1", "H1_F2J2", "H1_F2J3",
            "H1_F3J1", "H1_F3J2", "H1_F3J3",
        ]
        self.joint_positions = [0.4, -0.5, 0.6, 0.0, 0.0, 0.0,
                                0.0, -0.3, 0.0, 0.0, -0.3, 0.0, 0.0, -0.3, 0.0]  # placeholder
        self.joint_velocities = [0.0] * 15                                       # placeholder
        self.joint_efforts = [0.0] * 15                                          # placeholder
        self.object_pose = {                                                     # placeholder
            "position": {"x": 0.15, "y": 0.0, "z": 0.82},
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        }
        self.fail_pause_service = False        # placeholder negative-path switch
        self.fail_pause_application = False    # placeholder negative-path switch
        self.malformed_pause_response = False  # placeholder negative-path switch
        self.fail_pose_service = False         # placeholder negative-path switch
        self.fail_pose_application = False     # placeholder negative-path switch
        self.fail_configuration = False        # placeholder negative-path switch

    @staticmethod
    def _response(message, result, values):
        return {
            "op": "service_response",
            "service": message.get("service"),
            "id": message.get("id"),
            "result": result,
            "values": values,
        }

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if message.get("topic") == "/joint_states":
                return {
                    "op": "publish",
                    "topic": "/joint_states",
                    "id": message.get("id"),
                    "msg": {
                        "header": {"seq": 0, "stamp": {"secs": 0, "nsecs": 0}, "frame_id": ""},  # placeholder
                        "name": list(self.joint_names),
                        "position": list(self.joint_positions),
                        "velocity": list(self.joint_velocities),
                        "effort": list(self.joint_efforts),
                    },
                }
            return None
        if operation != "call_service":
            return None
        service = message.get("service")
        args = message.get("args") if isinstance(message.get("args"), dict) else {}
        if service == "/gazebo/pause_physics":
            if self.malformed_pause_response:
                return self._response(message, "not-a-bool", {})  # placeholder malformed reply
            if self.fail_pause_service:
                return self._response(message, False, {})
            self.paused = True
            if self.fail_pause_application:
                # The transport answered but the application predicate is not met.
                return self._response(message, True, {"rejected": True})  # placeholder
            return self._response(message, True, {})
        if service == "/gazebo/unpause_physics":
            self.paused = False
            return self._response(message, True, {})
        if service == "/gazebo/reset_world":
            self.reset_count += 1
            return self._response(message, True, {})
        if service == "/gazebo/get_model_state":
            if self.fail_pose_service:
                return self._response(message, False, {})
            return self._response(message, True, {
                "header": {"seq": 0, "stamp": {"secs": 0, "nsecs": 0}, "frame_id": "world"},  # placeholder
                "pose": self.object_pose,
                "success": not self.fail_pose_application,
                "status_message": "" if not self.fail_pose_application else "pose unavailable",  # placeholder
            })
        if service == "/gazebo/set_model_configuration":
            self.last_configuration = dict(args)
            if self.fail_configuration:
                return self._response(message, True, {"success": False,
                                                      "status_message": "configuration rejected"})  # placeholder
            return self._response(message, True, {"success": True, "status_message": ""})
        return self._response(message, False, {})

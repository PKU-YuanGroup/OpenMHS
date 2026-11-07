"""ROS-free wire mock for the pinned OpenMANIPULATOR controller endpoints.

The fake models the wire messages the RosDriver sends with hand-written replies, not a replay of captured traffic: a
``sensor_msgs/msg/JointState`` publication on ``/joint_states``, ROS 2
``send_action_goal``/``cancel_action_goal`` operations for
``control_msgs/action/FollowJointTrajectory`` and
``control_msgs/action/GripperCommand``, and the external
``std_srvs/srv/SetBool`` torque service.  It starts no ROS node, runs no
controller or physics, and every number below is test data, not a device
fact.
"""

from mhs.bridge.ros_transport import RecordingRosTransport


class FakeOpenManipulator(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.torque_enabled = True                       # placeholder state
        self.fail_torque_service = False                 # placeholder negative-path switch
        self.fail_torque_application = False             # placeholder negative-path switch
        self.fail_arm_result = False                     # placeholder negative-path switch
        self.fail_arm_application = False                # placeholder negative-path switch
        self.fail_gripper_result = False                 # placeholder negative-path switch
        self.fail_gripper_application = False            # placeholder negative-path switch
        self.hold_arm = False                            # placeholder delay/cancel switch
        self.arm_goals = []                              # placeholder recorded goals
        self.gripper_goals = []                          # placeholder recorded goals
        self.joint_names = [
            "joint1",
            "joint2",
            "joint3",
            "joint4",
            "joint5",
            "gripper_joint_1",
        ]
        self.positions = [0.3, 0.2, 0.1, 0.0, -0.1, 0.0]  # placeholder
        self.velocities = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # placeholder
        self.gripper_position = 0.0                      # placeholder
        self.gripper_effort = 0.0                        # placeholder

    def _joint_state(self, message):
        return {
            "op": "publish",
            "topic": "/joint_states",
            "id": message.get("id"),
            "msg": {
                "header": {"stamp": {"secs": 0, "nanosec": 0}, "frame_id": ""},  # placeholder
                "name": list(self.joint_names),
                "position": list(self.positions),
                "velocity": list(self.velocities),
            },
        }

    def _action_result(self, message, status, values, *, received=True):
        return {
            "op": "action_result",
            "action": message.get("action"),
            "action_type": message.get("action_type"),
            "id": message.get("id"),
            "result": received,
            "status": status,
            "values": values,
        }

    def _arm(self, message):
        args = message.get("args") or {}
        trajectory = args.get("trajectory") or {}
        points = trajectory.get("points") or []
        self.arm_goals.append({"joint_names": trajectory.get("joint_names"), "points": points})
        if self.hold_arm:
            return None
        if points and isinstance(points[0], dict) and isinstance(points[0].get("positions"), list):
            goal = points[0]["positions"]
            # Only the five arm joints are replaced; the gripper entry stays.
            for index, value in enumerate(goal[:5]):
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    self.positions[index] = float(value)  # placeholder state update
        if self.fail_arm_result:
            return self._action_result(message, 4, {"error_code": 0, "error_string": ""}, received=False)
        error = 1 if self.fail_arm_application else 0  # placeholder result code
        return self._action_result(
            message,
            4,
            {
                "error_code": error,
                "error_string": "placeholder rejected result" if error else "",
            },
        )

    def _gripper(self, message):
        command = (message.get("args") or {}).get("command") or {}
        self.gripper_goals.append(dict(command))
        position = command.get("position")
        effort = command.get("max_effort")
        if isinstance(position, (int, float)) and not isinstance(position, bool):
            self.gripper_position = float(position)  # placeholder state update
        if isinstance(effort, (int, float)) and not isinstance(effort, bool):
            self.gripper_effort = float(effort)  # placeholder state update
        if self.fail_gripper_result:
            return self._action_result(
                message, 4, {"reached_goal": True, "stalled": False, "position": 0.0, "effort": 0.0},
                received=False)
        return self._action_result(
            message,
            4,
            {
                "reached_goal": not self.fail_gripper_application,
                "stalled": bool(self.fail_gripper_application),
                "position": self.gripper_position,
                "effort": self.gripper_effort,
            },
        )

    def _torque(self, message):
        service = message.get("service")
        args = message.get("args") or {}
        data = args.get("data")
        if self.fail_torque_service:
            return {
                "op": "service_response",
                "service": service,
                "id": message.get("id"),
                "result": False,
                "values": "placeholder torque service failure",
            }
        self.torque_enabled = bool(data)
        if self.fail_torque_application:
            return {
                "op": "service_response",
                "service": service,
                "id": message.get("id"),
                "result": True,
                "values": {"success": False, "message": "placeholder rejected torque request"},
            }
        return {
            "op": "service_response",
            "service": service,
            "id": message.get("id"),
            "result": True,
            "values": {"success": True, "message": "placeholder torque acknowledgement"},
        }

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if message.get("topic") == "/joint_states":
                return self._joint_state(message)
            return None
        if operation == "send_action_goal":
            action = message.get("action")
            if action == "/arm_controller/follow_joint_trajectory":
                return self._arm(message)
            if action == "/gripper_controller/gripper_cmd":
                return self._gripper(message)
            return None
        if operation == "cancel_action_goal":
            return self._action_result(message, 5, {})
        if operation == "call_service":
            if message.get("service") == "/dynamixel_hardware_interface/set_dxl_torque":
                return self._torque(message)
            return {
                "op": "service_response",
                "service": message.get("service"),
                "id": message.get("id"),
                "result": False,
                "values": "placeholder unknown service",
            }
        return None

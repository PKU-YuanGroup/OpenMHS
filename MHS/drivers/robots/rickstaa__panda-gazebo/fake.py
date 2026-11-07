"""ROS-free recording fake for the pinned panda_gazebo ROS 1 endpoints.

The fake models the wire contract of the selected upstream endpoints: the
``/panda_control_server/panda_arm/follow_joint_trajectory`` actionlib server,
the ``/panda_control_server/panda_hand/set_gripper_width`` service, the
``/lock_unlock_panda_joints`` world-plugin service and one
``sensor_msgs/JointState`` subscription.  It is an in-memory analytic stand-in,
not a recording of captured traffic, not Gazebo and not the upstream plugin.

Every numeric state value and canned reply below is test data, marked
``# placeholder``; none is a device fact, a Limit or a reference.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_JOINT_STATE = "/joint_states"
_ARM_ACTION = "/panda_control_server/panda_arm/follow_joint_trajectory"
_GRIPPER_SERVICE = "/panda_control_server/panda_hand/set_gripper_width"
_LOCK_SERVICE = "/lock_unlock_panda_joints"

_ARM_JOINTS = [
    "panda_joint1",
    "panda_joint2",
    "panda_joint3",
    "panda_joint4",
    "panda_joint5",
    "panda_joint6",
    "panda_joint7",
]  # placeholder names copied from the pinned control_server PANDA_JOINTS literal
_ALL_JOINTS = _ARM_JOINTS + ["panda_finger_joint1", "panda_finger_joint2"]  # placeholder


class FakePandaGazebo(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.arm_positions = [0.0, -0.5, 0.0, -2.0, 0.0, 2.0, 0.0]  # placeholder
        self.finger_positions = [0.04, 0.04]  # placeholder
        self.last_width = 0.0  # placeholder total width sent to the service
        self.last_force = 0.0  # placeholder max_effort sent to the service
        self.locked = False  # placeholder
        self.locked_joints = []  # placeholder
        self.goals = []  # placeholder goal record
        self.cancelled_goals = []  # placeholder
        self.fail_lock_service = False  # placeholder negative-path switch
        self.fail_lock_application = False  # placeholder negative-path switch
        self.malformed_lock_result = False  # placeholder negative-path switch
        self.fail_gripper_service = False  # placeholder negative-path switch
        self.fail_gripper_application = False  # placeholder negative-path switch
        self.fail_trajectory_application = False  # placeholder negative-path switch
        self.malformed_trajectory_result = False  # placeholder negative-path switch

    def _joint_state(self, ident):
        return {
            "op": "publish",
            "topic": _JOINT_STATE,
            "id": ident,
            "msg": {
                "name": list(_ALL_JOINTS),  # placeholder
                "position": list(self.arm_positions) + list(self.finger_positions),  # placeholder
                "velocity": [0.0] * len(_ALL_JOINTS),  # placeholder
                "effort": [0.0] * len(_ALL_JOINTS),  # placeholder
            },
        }

    @staticmethod
    def _service_response(message, values, *, result=True):
        return {
            "op": "service_response",
            "service": message.get("service"),
            "id": message.get("id"),
            "result": result,
            "values": values,
        }

    def _action_result(self, ident, status, values):
        return {
            "op": "publish",
            "topic": _ARM_ACTION + "/result",
            "msg": {
                "status": {"goal_id": {"id": ident}, "status": status},
                "result": values,
            },
        }

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if message.get("topic") == _JOINT_STATE:
                return self._joint_state(message.get("id"))
            return None
        if operation in ("advertise", "unadvertise", "unsubscribe"):
            return None
        if operation == "call_service":
            return self._call_service(message)
        if operation == "publish":
            topic = message.get("topic")
            if isinstance(topic, str) and topic == _ARM_ACTION + "/goal":
                return self._goal(message)
            if isinstance(topic, str) and topic == _ARM_ACTION + "/cancel":
                return self._cancel(message)
        return None

    def _call_service(self, message):
        service = message.get("service")
        args = message.get("args") if isinstance(message.get("args"), dict) else {}
        if service == _LOCK_SERVICE:
            if self.fail_lock_service:
                return self._service_response(message, {}, result=False)
            self.locked_joints = list(args.get("joint_names") or [])  # placeholder
            if self.fail_lock_application:
                return self._service_response(message, {"success": False, "message": "placeholder lock rejection"})
            if self.malformed_lock_result:
                return self._service_response(message, {"message": "placeholder missing success"})
            self.locked = bool(args.get("lock"))
            return self._service_response(
                message, {"success": True, "message": "Joint locking successful"}  # placeholder
            )
        if service == _GRIPPER_SERVICE:
            if self.fail_gripper_service:
                return self._service_response(message, {}, result=False)
            width = args.get("width")
            force = args.get("max_effort")
            if isinstance(width, (int, float)) and not isinstance(width, bool):
                self.last_width = float(width)  # placeholder
                self.finger_positions = [float(width) / 2.0, float(width) / 2.0]  # placeholder
            if isinstance(force, (int, float)) and not isinstance(force, bool):
                self.last_force = float(force)  # placeholder
            if self.fail_gripper_application:
                return self._service_response(message, {"success": False, "message": "placeholder gripper rejection"})
            return self._service_response(
                message, {"success": True, "message": "Everything went OK"}  # placeholder
            )
        return self._service_response(message, {}, result=False)

    def _goal(self, message):
        envelope = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        goal_id = envelope.get("goal_id") if isinstance(envelope.get("goal_id"), dict) else {}
        goal = envelope.get("goal") if isinstance(envelope.get("goal"), dict) else {}
        ident = goal_id.get("id")
        if not isinstance(ident, str) or not ident:
            return None
        self.goals.append({"id": ident, "goal": goal})  # placeholder record
        points = ((goal.get("trajectory") or {}).get("points")
                  if isinstance(goal.get("trajectory"), dict) else None)
        if isinstance(points, list) and points:
            last = points[-1] if isinstance(points[-1], dict) else {}
            positions = last.get("positions")
            if isinstance(positions, list) and len(positions) == len(_ARM_JOINTS):
                self.arm_positions = [float(item) for item in positions]  # placeholder
        if self.malformed_trajectory_result:
            return {
                "op": "publish",
                "topic": _ARM_ACTION + "/result",
                "msg": {"status": {"goal_id": {"id": ident}, "status": 3},
                        "result": {"error_code": 0, "error_string": ""}},  # placeholder malformed envelope
            }
        if self.fail_trajectory_application:
            return self._action_result(ident, 3, {"error_code": -1, "error_string": "placeholder aborted"})
        return self._action_result(ident, 3, {"error_code": 0, "error_string": ""})  # placeholder success

    def _cancel(self, message):
        envelope = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        ident = envelope.get("id")
        if not isinstance(ident, str) or not ident:
            return None
        self.cancelled_goals.append(ident)  # placeholder record
        return self._action_result(ident, 2, {"error_code": -1, "error_string": "placeholder preempted"})

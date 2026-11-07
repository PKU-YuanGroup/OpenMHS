"""ROS-free recording fake for the pinned franka_gripper ROS 1 endpoints.

The fake models the wire contract of the four selected actionlib action servers and the
``sensor_msgs/JointState`` publication of ``franka_gripper_node``.  It is an
in-memory analytic stand-in, not a recording of a real gripper and not the
upstream Gazebo plugin.  Every numeric state value and canned reply below is
test data, marked ``# placeholder``; none is a device fact, a Limit or a
reference.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_STATE_TOPIC = "/franka_gripper/joint_states"
_ACTIONS = {
    "/franka_gripper/grasp": "franka_gripper/GraspAction",
    "/franka_gripper/move": "franka_gripper/MoveAction",
    "/franka_gripper/homing": "franka_gripper/HomingAction",
    "/franka_gripper/stop": "franka_gripper/StopAction",
}


class FakeFrankaGripper(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.finger_positions = [0.02, 0.02]   # placeholder
        self.force_applied = 0.0               # placeholder
        self.goals = []                         # placeholder outbound-goal record
        self.advertised = []                    # placeholder subscription/advertise record
        self.fail_grasp_application = False     # placeholder negative-path switch
        self.fail_move_service = False          # placeholder negative-path switch
        self.malformed_stop_result = False      # placeholder negative-path switch

    def _state(self, ident):
        return {
            "op": "publish",
            "topic": _STATE_TOPIC,
            "id": ident,
            "msg": {
                "name": ["panda_finger_joint1", "panda_finger_joint2"],  # placeholder
                "position": list(self.finger_positions),                 # placeholder
                "velocity": [0.0, 0.0],                                  # placeholder
                "effort": [0.0, 0.0],                                    # placeholder
            },
        }

    def _result(self, action, ident, status, values):
        return {
            "op": "publish",
            "topic": action + "/result",
            "msg": {
                "status": {"goal_id": {"id": ident}, "status": status},
                "result": values,
            },
        }

    def _goal_reply(self, action, ident, goal):
        self.goals.append({"action": action, "id": ident, "goal": dict(goal)})  # placeholder
        if action == "/franka_gripper/stop":
            if self.malformed_stop_result:
                return {
                    "op": "publish",
                    "topic": action + "/result",
                    "msg": {"status": {"goal_id": {"id": ident}, "status": "succeeded"},
                            "result": {"success": True, "error": ""}},  # placeholder malformed status
                }
            self.force_applied = 0.0  # placeholder
            return self._result(action, ident, 3, {"success": True, "error": ""})
        if action == "/franka_gripper/homing":
            self.finger_positions = [0.0, 0.0]  # placeholder
            return self._result(action, ident, 3, {"success": True, "error": ""})
        if action == "/franka_gripper/move":
            if self.fail_move_service:
                return self._result(action, ident, 4, {"success": False, "error": "placeholder move failure"})
            width = goal.get("width")  # metres in the upstream action
            if isinstance(width, (int, float)) and not isinstance(width, bool):
                self.finger_positions = [float(width) / 2.0, float(width) / 2.0]  # placeholder
            return self._result(action, ident, 3, {"success": True, "error": ""})
        if action == "/franka_gripper/grasp":
            if self.fail_grasp_application:
                return self._result(action, ident, 3, {"success": False, "error": ""})
            width = goal.get("width")
            force = goal.get("force")
            if isinstance(width, (int, float)) and not isinstance(width, bool):
                self.finger_positions = [float(width) / 2.0, float(width) / 2.0]  # placeholder
            if isinstance(force, (int, float)) and not isinstance(force, bool):
                self.force_applied = float(force)  # placeholder
            return self._result(action, ident, 3, {"success": True, "error": ""})
        return self._result(action, ident, 4, {"success": False, "error": "placeholder unknown action"})

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if message.get("topic") == _STATE_TOPIC:
                return self._state(message.get("id"))
            return None
        if operation == "advertise":
            self.advertised.append(message)  # placeholder
            return None
        if operation == "publish":
            topic = message.get("topic")
            if topic == _STATE_TOPIC:
                return None
            if isinstance(topic, str) and topic.endswith("/goal") and topic[:-5] in _ACTIONS:
                action = topic[:-5]
                envelope = message.get("msg") if isinstance(message.get("msg"), dict) else {}
                goal_id = envelope.get("goal_id") if isinstance(envelope.get("goal_id"), dict) else {}
                goal = envelope.get("goal") if isinstance(envelope.get("goal"), dict) else {}
                ident = goal_id.get("id")
                if isinstance(ident, str) and ident:
                    return self._goal_reply(action, ident, goal)
            return None
        return None

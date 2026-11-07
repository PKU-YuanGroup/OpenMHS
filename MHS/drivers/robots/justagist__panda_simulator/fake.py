"""Analytic ROS-free stand-in for the panda_simulator Franka Hand endpoints.

This fake models the wire shapes the driver declares: three
``franka_gripper`` actionlib servers on ``/franka_gripper/move``,
``/franka_gripper/grasp`` and ``/franka_gripper/stop`` and the
``sensor_msgs/JointState`` publication on ``/franka_gripper/joint_states``.
It does not replay captured traffic and runs no Gazebo, ros_control,
franka_interface or physics.  Every number and state below is test data, not a
device fact.  As in the pinned controller, cancelling a move or grasp goal
produces no PREEMPTED result: the C++ callbacks never check
is_preempt_requested (panda_gripper_controller.cpp:242-258, 306-321).
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_MOVE = "/franka_gripper/move"
_GRASP = "/franka_gripper/grasp"
_STOP = "/franka_gripper/stop"
_STATE = "/franka_gripper/joint_states"
_ACTIONS = (_MOVE, _GRASP, _STOP)
_NAMES = ["panda_finger_joint1", "panda_finger_joint2"]


class FakePandaSimulator(RecordingRosTransport):
    """Analytic franka_gripper actionlib and joint-state stand-in."""

    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.joint_names = list(_NAMES)
        self.positions = [0.0, 0.0]  # placeholder
        self.fail_move_result = False  # placeholder negative-path switch
        self.fail_grasp_result = False  # placeholder negative-path switch
        self.malformed_result = False  # placeholder negative-path switch
        # placeholder switch: move and grasp goals stay running (no status or
        # result), as an upstream goal does while its wait loop runs
        self.hold_goals = False

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if message.get("topic") == _STATE:
                return {
                    "op": "publish",
                    "topic": _STATE,
                    "id": message.get("id"),
                    "msg": {
                        # ROS 1 Header; timerUpdate never sets it (placeholder zeros)
                        "header": {"seq": 0, "stamp": {"secs": 0, "nsecs": 0}, "frame_id": ""},
                        "name": list(self.joint_names),
                        "position": list(self.positions),  # placeholder
                        "velocity": [0.0, 0.0],  # placeholder
                        "effort": [0.0, 0.0],  # placeholder
                    },
                }
            return None
        if operation == "publish":
            topic = message.get("topic")
            if isinstance(topic, str) and topic.endswith("/goal"):
                action = topic[:-len("/goal")]
                if action in _ACTIONS:
                    return self._goal(action, message)
            if isinstance(topic, str) and topic.endswith("/cancel"):
                action = topic[:-len("/cancel")]
                if action in _ACTIONS:
                    return self._cancel(action, message)
        return None

    def _goal(self, action, message):
        msg = message.get("msg")
        if not isinstance(msg, dict):
            return None
        goal_id = msg.get("goal_id")
        ident = goal_id.get("id") if isinstance(goal_id, dict) else None
        if not isinstance(ident, str) or not ident:
            return None
        goal = msg.get("goal") if isinstance(msg.get("goal"), dict) else {}
        if action in (_MOVE, _GRASP) and self.hold_goals:
            return None  # placeholder: the goal keeps running, no status or result yet
        if action in (_MOVE, _GRASP):
            width = goal.get("width")
            if isinstance(width, (int, float)) and not isinstance(width, bool):
                # Placeholder state transition: both fingers move to half the
                # requested opening; the real mimic joint may differ.
                self.positions = [float(width) / 2.0, float(width) / 2.0]
        if action == _MOVE:
            success = not self.fail_move_result
        elif action == _GRASP:
            success = not self.fail_grasp_result
        else:
            success = True
        status = 3 if success else 4  # placeholder actionlib SUCCEEDED / ABORTED
        status_event = {
            "op": "publish",
            "topic": action + "/status",
            "msg": {"status_list": [{"goal_id": {"id": ident}, "status": status}]},  # placeholder status
        }
        if self.malformed_result:
            return [status_event]
        result_event = {
            "op": "publish",
            "topic": action + "/result",
            "msg": {
                "status": {"goal_id": {"id": ident}, "status": status},
                "result": {"success": success, "error": ""},  # placeholder result
            },
        }
        return [status_event, result_event]

    @staticmethod
    def _cancel(action, message):
        # The pinned move and grasp callbacks never check is_preempt_requested,
        # so a cancel request produces no PREEMPTED result: a running goal ends
        # SUCCEEDED or ABORTED after its wait, and a finished goal sends nothing.
        return None

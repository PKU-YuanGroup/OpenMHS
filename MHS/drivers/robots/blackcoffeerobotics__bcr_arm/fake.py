"""ROS-free recording fake for the BCR arm ROS 2 trajectory controller.

The fake models the pinned upstream wire contract used by this package: the
ROS 2 native ``send_action_goal`` for
``control_msgs/action/FollowJointTrajectory`` at
``/joint_trajectory_controller/follow_joint_trajectory`` and a
``sensor_msgs/msg/JointState`` publication on ``/joint_states``, and the
companion controller manager services ``/controller_manager/switch_controller``
and ``/controller_manager/list_controllers`` (the e-stop, its read-back and the
re-enable).  It keeps the trajectory controller's lifecycle state: a switch
deactivates or activates it, the list reports it, and a goal is rejected while
it is inactive.  It opens no socket, starts no ROS node and runs no Gazebo or
controller.

Every state value and canned result below is test data, not a device fact;
those values are marked ``# placeholder``.  The ROS 2 action status 4
(SUCCEEDED) is a protocol enum, not a device fact.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_JOINTS = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6", "joint7"]


class FakeBcrArm(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Placeholder joint state: seven joints at zero position and velocity.
        self.joint_positions = [0.0] * 7        # placeholder
        self.joint_velocities = [0.0] * 7       # placeholder
        self.action_calls = 0                   # placeholder counter
        self.last_goal = None                   # placeholder
        self.drop_joint_state = False           # placeholder negative-path switch
        self.reject_goal = False                # placeholder negative-path switch
        self.fail_transport = False             # placeholder negative-path switch
        self.cancel_goals = False               # placeholder negative-path switch
        self.jtc_state = "active"               # placeholder: the spawner activated the trajectory controller
        self.fail_switch = False                # placeholder negative-path switch: the switch answers ok false
        self.ignore_switch = False              # placeholder negative-path switch: another client re-activated it
        self.duplicate_listing = False          # placeholder negative-path switch: the controller listed twice
        self.switch_requests = []               # recording helper, no device meaning

    def _joint_state(self, ident):
        return {
            "op": "publish",
            "topic": "/joint_states",
            "id": ident,
            "msg": {
                "name": list(_JOINTS),
                "position": [float(value) for value in self.joint_positions],   # placeholder
                "velocity": [float(value) for value in self.joint_velocities],   # placeholder
            },
        }

    @staticmethod
    def _goal_positions(goal):
        """The final commanded positions of a FollowJointTrajectory goal, or None."""
        if not isinstance(goal, dict):
            return None
        trajectory = goal.get("trajectory")
        if not isinstance(trajectory, dict):
            return None
        if trajectory.get("joint_names") != _JOINTS:
            return None
        points = trajectory.get("points")
        if not isinstance(points, list) or not points:
            return None
        last = points[-1]
        positions = last.get("positions") if isinstance(last, dict) else None
        if not isinstance(positions, list) or len(positions) != 7:
            return None
        values = []
        for position in positions:
            if isinstance(position, bool) or not isinstance(position, (int, float)):
                return None
            values.append(float(position))
        return values

    def _action_result(self, ident, action, values):
        return {
            "op": "action_result",
            "action": action,
            "id": ident,
            "result": True,
            "status": 4,  # ROS 2 action SUCCEEDED protocol status, not a device fact
            "values": values,
        }

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if message.get("topic") == "/joint_states":
                if self.drop_joint_state:
                    return None
                return self._joint_state(message.get("id"))
            return None
        if operation == "unsubscribe":
            return None
        if operation == "call_service":
            return self._service(message)
        if operation == "send_action_goal":
            self.action_calls += 1
            action = message.get("action")
            ident = message.get("id")
            self.last_goal = message.get("args")  # placeholder test data, never a device fact
            if self.fail_transport:
                return {
                    "op": "status",
                    "level": "error",
                    "id": ident,
                    "msg": "fake transport rejected the goal",  # placeholder
                }
            positions = self._goal_positions(message.get("args"))
            if self.reject_goal or positions is None or self.jtc_state != "active":
                return self._action_result(
                    ident,
                    action,
                    {"error_code": -1, "error_string": "rejected by the fake"},  # placeholder
                )
            if self.cancel_goals:
                return self._action_result(
                    ident,
                    action,
                    {"error_code": -2, "error_string": "cancelled by the fake"},  # placeholder
                )
            self.joint_positions = positions
            self.joint_velocities = [0.0] * 7  # placeholder stopped-command velocity
            return self._action_result(
                ident,
                action,
                {"error_code": 0, "error_string": ""},  # placeholder successful result
            )
        if operation == "cancel_action_goal":  # noqa: SIM102
            # A goal result is returned synchronously; a later cancellation is
            # not part of this recording.  Do not invent a terminal result for
            # an unknown goal id.
            return None
        return None

    def _service(self, message):
        service = message.get("service")
        reply = {"op": "service_response", "service": service, "id": message.get("id"), "result": True}
        args = message.get("args") if isinstance(message.get("args"), dict) else {}
        if service == "/controller_manager/switch_controller":
            self.switch_requests.append(args)
            if self.fail_switch:
                return dict(reply, values={"ok": False})  # placeholder: a timed-out or refused switch
            if "joint_trajectory_controller" in (args.get("deactivate_controllers") or []):
                self.jtc_state = "inactive"  # the goal is aborted and the trajectory dropped (placeholder)
            if "joint_trajectory_controller" in (args.get("activate_controllers") or []):
                self.jtc_state = "active"  # holds the current position (placeholder: joint values unchanged)
            return dict(reply, values={"ok": True})
        if service == "/controller_manager/list_controllers":
            state = "active" if self.ignore_switch else self.jtc_state
            listing = [{"name": "joint_state_broadcaster", "state": "active",  # placeholder
                        "type": "joint_state_broadcaster/JointStateBroadcaster"},
                       {"name": "joint_trajectory_controller", "state": state,  # placeholder
                        "type": "joint_trajectory_controller/JointTrajectoryController"}]
            if self.duplicate_listing:
                listing.append(dict(listing[1]))
            return dict(reply, values={"controller": listing})
        return dict(reply, result=False, values={})

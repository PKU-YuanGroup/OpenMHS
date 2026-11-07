"""ROS-free recording fake for the IFRA ROS 2 robot-simulation action servers.

The fake models only the declared ROS 2 native action wire contract for
/MoveJ, /MoveJs, /MoveXYZ and /MoveG: a goal sent with ``send_action_goal`` is
answered by one terminal ``action_result`` with the upstream result string.
It runs no Gazebo world, MoveIt planner, controller or physics loop.  Every
state value, flag and canned number below is test data, not a device fact.
"""

import copy

from mhs.bridge.ros_transport import RecordingRosTransport


#: Success strings are copied from the pinned action-server source, not
#: invented device facts: moveJ_action.cpp:327, moveXYZ_action.cpp:192,
#: moveG_action.cpp:196.  The corresponding failure strings are at :333,
#: :198 and :208.  They are the terminal result values the bridge matches.
_RESULTS = {
    "/MoveJ": ("MoveJ:SUCCESS", "MoveJ:FAILED", "MoveJ:CANCELED"),
    "/MoveJs": ("MoveJs:SUCCESS", "MoveJs:FAILED", "MoveJs:CANCELED"),
    "/MoveXYZ": ("MoveXYZ:SUCCESS", "MoveXYZ:FAILED", "MoveXYZ:CANCELED"),
    "/MoveG": ("MoveG:SUCCESS", "MoveG:FAILED", "MoveG:CANCELED"),
}

_TYPES = {
    "/MoveJ": "ros2_data/action/MoveJ",
    "/MoveJs": "ros2_data/action/MoveJs",
    "/MoveXYZ": "ros2_data/action/MoveXYZ",
    "/MoveG": "ros2_data/action/MoveG",
}


class FakeRos2Robotsimulation(RecordingRosTransport):
    """Canned ROS 2 action terminals; no ROS, Gazebo, MoveIt or hardware."""

    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.fail_protocol = set()      # placeholder negative-path switch
        self.fail_application = set()   # placeholder negative-path switch
        self.hold = set()               # placeholder event-control switch
        self.pending = None             # placeholder held goal
        self.action_calls = []          # placeholder recorded goal actions

    @staticmethod
    def _status_error(message):
        return {"op": "status", "level": "error", "id": message.get("id")}

    def _terminal(self, message, action, status, result):
        return {
            "op": "action_result",
            "action": action,
            "id": message.get("id"),
            "result": True,
            "status": status,           # placeholder ROS 2 status enum value
            "values": {"result": result},
        }

    def _respond(self, message):
        operation = message.get("op")
        if operation == "send_action_goal":
            action = message.get("action")
            if action not in _RESULTS:
                return self._status_error(message)
            if message.get("action_type") != _TYPES[action]:
                return self._status_error(message)
            if action in self.fail_protocol:
                return self._status_error(message)
            success, failure, _cancelled = _RESULTS[action]
            if action in self.fail_application:
                return self._terminal(message, action, 4, failure)  # placeholder status
            if action in self.hold:
                self.pending = copy.deepcopy(message)
                return None
            self.action_calls.append(action)
            return self._terminal(message, action, 4, success)      # placeholder status
        if operation == "cancel_action_goal":
            if self.pending is None or message.get("id") != self.pending.get("id"):
                return None
            action = self.pending["action"]
            _, _, cancelled = _RESULTS[action]
            self.pending = None
            return self._terminal(message, action, 5, cancelled)    # placeholder status
        return None

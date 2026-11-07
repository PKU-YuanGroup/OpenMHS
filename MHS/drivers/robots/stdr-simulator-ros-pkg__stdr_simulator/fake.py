"""ROS-free recording fake for the pinned STDR ROS 1 environment endpoints.

The fake models the actionlib wrapper traffic that ``RosDriver`` actually
sends and receives for ``/stdr_server/spawn_robot``, plus the latched
``/stdr_server/active_robots`` observation.  It is an analytic stand-in, not
a recording of captured traffic and not the upstream STDR simulator: no
nodelet, map, physics or sensor runs here.  Every canned name, description
and status below is test data, marked ``# placeholder``; none is a device
fact, a Limit or a reference.
"""

import copy

from mhs.bridge.ros_transport import RecordingRosTransport

_SPAWN = "/stdr_server/spawn_robot"
_ACTIVE = "/stdr_server/active_robots"

_GOAL_STATUS_SUCCEEDED = 3  # placeholder actionlib status
_GOAL_STATUS_ABORTED = 4    # placeholder actionlib status


class FakeStdrSimulator(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.robots = []                 # placeholder empty registry
        self.next_id = 0                 # placeholder numbering
        self.assigned_names = []         # placeholder assigned-name record
        self.goals = []                  # placeholder received goal record
        self.fail_spawn = False          # placeholder negative-path switch

    @staticmethod
    def _result(action, ident, status, values):
        return {
            "op": "publish",
            "topic": action + "/result",
            "msg": {
                "header": {"seq": 0, "stamp": {"secs": 0, "nsecs": 0}, "frame_id": ""},  # placeholder
                "status": {"goal_id": {"id": ident}, "status": status},
                "result": values,
            },
        }

    def _spawn_reply(self, ident, description):
        self.goals.append({"action": _SPAWN, "id": ident, "description": copy.deepcopy(description)})  # placeholder
        if self.fail_spawn:
            return self._result(_SPAWN, ident, _GOAL_STATUS_ABORTED,
                                {"indexedDescription": {"name": "", "robot": {}},  # placeholder
                                 "message": "placeholder duplicate frame_id"})  # placeholder
        name = "robot" + str(self.next_id)  # placeholder numbering
        self.next_id += 1
        self.assigned_names.append(name)
        entry = {"name": name, "robot": copy.deepcopy(description)}
        self.robots.append(entry)
        return self._result(_SPAWN, ident, _GOAL_STATUS_SUCCEEDED,
                            {"indexedDescription": copy.deepcopy(entry), "message": ""})  # placeholder empty message

    def _active_reply(self, ident):
        return {
            "op": "publish",
            "topic": _ACTIVE,
            "id": ident,
            "msg": {"robots": copy.deepcopy(self.robots)},  # placeholder registry copy
        }

    def _respond(self, message):
        operation = message.get("op")
        topic = message.get("topic")
        if operation == "subscribe":
            if topic == _ACTIVE:
                return self._active_reply(message.get("id"))
            return None
        if operation in ("advertise", "unadvertise", "unsubscribe"):
            return None
        if operation != "publish" or not isinstance(topic, str):
            return None
        if topic == _SPAWN + "/goal":
            envelope = message.get("msg") if isinstance(message.get("msg"), dict) else {}
            goal_id = envelope.get("goal_id") if isinstance(envelope.get("goal_id"), dict) else {}
            goal = envelope.get("goal") if isinstance(envelope.get("goal"), dict) else {}
            ident = goal_id.get("id")
            if isinstance(ident, str) and ident:
                return self._spawn_reply(ident, goal.get("description"))
        return None

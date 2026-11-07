"""ROS-free analytic stand-in for the pinned Astrobee ROS 1 action endpoints.

The fake models the actionlib wrapper traffic that ``RosDriver`` actually
sends and receives: it advertises the goal/cancel topics, subscribes to the
result/status topics, answers a Motion MOVE goal and a Control STOP goal, and
can hold a MOVE goal so a cancellation can be exercised.  It is an analytic
stand-in, not a recording of captured traffic and not the upstream Gazebo
simulator.  Every canned reply and state value below is test data, marked
``# placeholder``; none is a device fact, a Limit or a reference.
"""

from mhs.bridge.ros_transport import RecordingRosTransport

_MOTION = "/mob/motion"
_CONTROL = "/gnc/control"
_GOAL_STATUS_SUCCEEDED = 3   # placeholder actionlib status
_GOAL_STATUS_PREEMPTED = 2   # placeholder actionlib status
_GOAL_STATUS_ABORTED = 4     # placeholder actionlib status


class FakeAstrobee(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.goals = []                    # placeholder outbound-goal record
        self.pending_moves = {}            # placeholder goal id -> action
        self.last_states = []              # placeholder last MOVE state sequence
        self.segment_nsecs = 1             # placeholder segment stamp
        self.stopped = False               # placeholder quiescence marker
        self.hold_moves = False            # placeholder pending-MOVE switch
        self.fail_move_application = False  # placeholder negative-path switch
        self.fail_stop_application = False  # placeholder negative-path switch
        self.malformed_stop_result = False  # placeholder negative-path switch

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

    def _goal_reply(self, action, ident, goal):
        self.goals.append({"action": action, "id": ident, "goal": dict(goal)})  # placeholder
        if action == _CONTROL:
            if goal.get("command") == 0:
                if self.malformed_stop_result:
                    # A terminal status of the wrong JSON type: the bridge must report unknown,
                    # not a successful stop.
                    return {
                        "op": "publish",
                        "topic": action + "/result",
                        "msg": {
                            "status": {"goal_id": {"id": ident}, "status": "succeeded"},  # placeholder
                            "result": {"response": 1},  # placeholder
                        },
                    }
                if self.fail_stop_application:
                    return self._result(action, ident, _GOAL_STATUS_ABORTED,
                                        {"response": -2})  # placeholder CONTROL_FAILED
                self.stopped = True
                return self._result(action, ident, _GOAL_STATUS_SUCCEEDED,
                                    {"response": 1, "segment": [], "index": 0})  # placeholder
            return self._result(action, ident, _GOAL_STATUS_ABORTED,
                                {"response": -4})  # placeholder INVALID_COMMAND
        if action == _MOTION:
            command = goal.get("command")
            if command == 3:
                if self.fail_move_application:
                    return self._result(action, ident, _GOAL_STATUS_ABORTED,
                                        {"response": -4,
                                         "fsm_result": "placeholder control failure"})  # placeholder
                if self.hold_moves:
                    self.pending_moves[ident] = action
                    return None
                self.last_states = goal.get("states") or []
                self.segment_nsecs = (self.segment_nsecs + 1) % 1_000_000_000  # placeholder
                return self._result(action, ident, _GOAL_STATUS_SUCCEEDED,
                                    {"response": 1,
                                     "fsm_result": "Motion completed successfully"})  # placeholder
            if command == 0:
                return self._result(action, ident, _GOAL_STATUS_SUCCEEDED,
                                    {"response": 1, "fsm_result": "placeholder stopped"})  # placeholder
            return self._result(action, ident, _GOAL_STATUS_ABORTED,
                                {"response": -14})  # placeholder INVALID_COMMAND
        return None

    def release_move(self, ident=None):
        """Complete a held MOVE goal; a test hook, not a native operation."""
        if ident is None:
            if not self.pending_moves:
                return None
            ident = next(iter(self.pending_moves))
        action = self.pending_moves.pop(ident, None)
        if action is None:
            return None
        return self._result(action, ident, _GOAL_STATUS_SUCCEEDED,
                            {"response": 1,
                             "fsm_result": "Motion completed successfully"})  # placeholder

    def _segment(self, ident):
        return {
            "op": "publish",
            "topic": "/mob/choreographer/segment",
            "id": ident,
            "msg": {
                "header": {"seq": 0, "stamp": {"secs": 0, "nsecs": self.segment_nsecs},
                           "frame_id": "world"},  # placeholder
                "poses": [],  # placeholder
            },
        }

    def _respond(self, message):
        operation = message.get("op")
        topic = message.get("topic")
        if operation == "subscribe":
            if topic == "/mob/choreographer/segment":
                return self._segment(message.get("id"))
            return None
        if operation in ("advertise", "unadvertise", "unsubscribe"):
            return None
        if operation != "publish" or not isinstance(topic, str):
            return None
        if topic.endswith("/goal") and topic[:-5] in (_MOTION, _CONTROL):
            action = topic[:-5]
            envelope = message.get("msg") if isinstance(message.get("msg"), dict) else {}
            goal_id = envelope.get("goal_id") if isinstance(envelope.get("goal_id"), dict) else {}
            goal = envelope.get("goal") if isinstance(envelope.get("goal"), dict) else {}
            ident = goal_id.get("id")
            if isinstance(ident, str) and ident:
                return self._goal_reply(action, ident, goal)
            return None
        if topic.endswith("/cancel") and topic[:-7] in (_MOTION, _CONTROL):
            action = topic[:-7]
            envelope = message.get("msg") if isinstance(message.get("msg"), dict) else {}
            ident = envelope.get("id")
            if isinstance(ident, str) and ident in self.pending_moves:
                self.pending_moves.pop(ident, None)
                return self._result(action, ident, _GOAL_STATUS_PREEMPTED,
                                    {"response": 0, "fsm_result": "placeholder preempted"})  # placeholder
            return None
        return None

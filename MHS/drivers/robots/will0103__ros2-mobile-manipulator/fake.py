"""ROS-free recording fake for the pinned ROS 2 ``/move_robot`` action and the world pause.

The fake models the declared ROS 2 native action wire contract: it accepts
``send_action_goal`` for ``my_robot_interfaces/action/MoveRobot`` and answers
with one terminal ``action_result``.  It also keeps a serial goal queue and
models cancellation: the running goal is cancelled and a zero Twist is
recorded, while goals already in the queue remain and are started afterwards.
That queue is the upstream behaviour that prevents cancellation from being an
acknowledged stop.

It also models the companion gz-sim world control and statistics that the
operator's ros_gz bridges carry: the ``/world/empty/control`` service
(``ros_gz_interfaces/srv/ControlWorld``) and the ``/world/empty/stats`` topic
(``WorldStatistics``).  A paused flag is set by a world control request after
the next statistics sample (gz-sim answers the request when it queues it and
applies it in its step loop, after publishing that step's statistics).
Statistics are published every ``stats_period_s`` while subscribed.

It runs no Gazebo Harmonic world, physics, bridge, controller or ROS graph.
Every flag, counter and canned string below is test data, marked
``# placeholder``; none is a device fact, a Limit or a reference.
"""

import copy
import time

from mhs.bridge.ros_transport import RecordingRosTransport

#: The pinned action name and fully qualified type from the declaration.
_ACTION = "/move_robot"
_TYPE = "my_robot_interfaces/action/MoveRobot"
_WORLD = "/world/empty"

#: ROS 2 action terminal status values (the protocol enum, not device data).
_SUCCEEDED = 4
_CANCELED = 5
_ABORTED = 6


class FakeRos2MobileManipulator(RecordingRosTransport):
    """Canned MoveRobot action terminals and a canned world pause; no ROS or Gazebo."""

    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.goals = []                 # placeholder outbound-goal record
        self.active = None              # placeholder currently executing goal
        self.queue = []                 # placeholder serial goal queue
        self.completed = 0              # placeholder counter
        self.cancelled = 0              # placeholder counter
        self.zero_twists = 0            # placeholder counter of zero-velocity publications
        self.cancel_with_queued = 0     # placeholder counter, queued goals still present on cancel
        self.hold_goals = False         # placeholder hold switch for cancellation tests
        self.fail_protocol = False      # placeholder negative-path switch
        self.fail_application = False   # placeholder negative-path switch
        self.malformed_result = False   # placeholder negative-path switch
        # The companion world (gz-sim through the operator's ros_gz bridges).
        self.paused = False             # placeholder: the launch runs the world (-r)
        self.pending_pause = None       # a queued world control, applied after the next sample
        self.stats_period_s = 0.1       # placeholder: gz-sim throttles the statistics to 10 per second
        self.stats_subscriptions = set()  # recording helper
        self.last_stats_at = 0.0       # recording helper
        self.iterations = 5000          # placeholder
        self.controls = []              # recording helper: the world control requests received
        self.fail_control = False       # placeholder negative-path switch: the call is not answered
        self.reject_control = False     # placeholder negative-path switch: the bridge answers false
        self.ignore_pause = False       # placeholder negative-path switch: the world keeps running
        self.silent_stats = False       # placeholder negative-path switch: no statistics bridge

    @staticmethod
    def _status_error(message):
        return {"op": "status", "level": "error", "id": message.get("id")}

    @staticmethod
    def _terminal(message, status, values):
        return {
            "op": "action_result",
            "action": _ACTION,
            "id": message.get("id"),
            "result": True,
            "status": status,           # placeholder status value selected by the fake
            "values": values,
        }

    def _success(self, message):
        self.completed += 1
        self.zero_twists += 1           # placeholder: upstream publishes zero on completion
        if self.malformed_result:
            return {
                "op": "action_result",
                "action": _ACTION,
                "id": message.get("id"),
                "result": True,
                "status": _SUCCEEDED,   # placeholder
                "values": "placeholder malformed terminal values",
            }
        if self.fail_application:
            return self._terminal(message, _ABORTED,
                                  {"success": False,
                                   "message": "placeholder application failure"})
        return self._terminal(message, _SUCCEEDED,
                              {"success": True,
                               "message": "robot arrived destination !"})

    def _cancel(self, message):
        self.cancelled += 1
        self.zero_twists += 1           # placeholder: upstream publishes zero on cancel
        return self._terminal(message, _CANCELED,
                              {"success": False,
                               "message": "robot move is canceled!"})

    def _drain_after(self):
        """Start the next queued goal, as the upstream queue thread would."""
        while self.queue:
            goal = self.queue.pop(0)
            self.active = goal
            if goal["cancel_requested"]:
                self.active = None
                return self._cancel(goal["message"])
            if self.hold_goals:
                return None
            self.active = None
            return self._success(goal["message"])
        return None

    def release_goal(self):
        """Complete the held active goal; a test hook, not a native operation."""
        if self.active is None:
            return None
        message = self.active["message"]
        self.active = None
        reply = self._success(message)
        following = self._drain_after()
        return [reply, following] if following is not None else reply

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if message.get("topic") == _WORLD + "/stats":
                self.stats_subscriptions.add(message.get("id"))
            return None
        if operation == "unsubscribe":
            self.stats_subscriptions.discard(message.get("id"))
            return None
        if operation == "call_service":
            return self._service(message)
        if operation == "send_action_goal":
            if message.get("action") != _ACTION or message.get("action_type") != _TYPE:
                return self._status_error(message)
            if self.fail_protocol:
                return self._status_error(message)
            goal = {
                "message": copy.deepcopy(message),
                "args": copy.deepcopy(message.get("args") or {}),
                "cancel_requested": False,
            }
            self.goals.append(goal)      # placeholder record
            if self.active is not None:
                self.queue.append(goal)
                return None
            self.active = goal
            if self.hold_goals:
                return None
            self.active = None
            return self._success(message)
        if operation == "cancel_action_goal":
            identifier = message.get("id")
            if self.active is not None and identifier == self.active["message"].get("id"):
                if self.queue:
                    self.cancel_with_queued += 1
                reply = self._cancel(self.active["message"])
                self.active = None
                following = self._drain_after()
                return [reply, following] if following is not None else reply
            for goal in self.queue:
                if identifier == goal["message"].get("id"):
                    goal["cancel_requested"] = True
                    return None
            return None
        return None

    def _service(self, message):
        service = message.get("service")
        reply = {"op": "service_response", "service": service, "id": message.get("id"), "result": True}
        if service != _WORLD + "/control":
            return dict(reply, result=False, values={})
        request = (message.get("args") or {}).get("world_control") or {}
        self.controls.append(dict(request))
        if self.fail_control:
            return None  # no answer: the e-stop's request times out
        if self.reject_control:
            return dict(reply, values={"success": False})  # a failed gz request
        pause = bool(request.get("pause"))
        if not (pause and self.ignore_pause):
            self.pending_pause = pause
        return dict(reply, values={"success": True})  # true for any queued request

    def recv(self, *, timeout_s=None):
        now = time.monotonic()
        if self.stats_subscriptions and not self.silent_stats and now - self.last_stats_at >= self.stats_period_s:
            self.last_stats_at = now
            sample = {
                "header": {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": "", "data": []},  # unstamped gz header
                "sim_time": {"sec": 12, "nanosec": 0},                                       # placeholder
                "pause_time": {"sec": 0, "nanosec": 0},                                      # placeholder
                "real_time": {"sec": 12, "nanosec": 0},                                      # placeholder
                "paused": self.paused,
                "iterations": self.iterations,                                               # placeholder
                "model_count": 1,                                                            # placeholder
                "real_time_factor": 1.0,                                                     # placeholder
            }
            if self.pending_pause is not None:
                self.paused, self.pending_pause = self.pending_pause, None
            if not self.paused:
                self.iterations += 25  # placeholder
            return {"op": "publish", "topic": _WORLD + "/stats", "msg": sample}
        return super().recv(timeout_s=min(timeout_s or 0.01, 0.01))

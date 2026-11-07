"""ROS-free canned fake for the VRX competition bridge contract.

The fake models the pinned rosbridge wire shape used by the driver: a
``rosgraph_msgs/msg/Clock`` publication on ``/clock``, a
``ros_gz_interfaces/msg/ParamVec`` publication on ``/vrx/task/info``, the four
``std_msgs/msg/Float64`` thruster publications under ``/wamv``, and the
companion gz-sim world control and statistics that the operator's ros_gz
bridges carry: the ``/world/sydney_regatta/control`` service
(``ros_gz_interfaces/srv/ControlWorld``) and the ``/world/sydney_regatta/stats``
topic (``WorldStatistics``).  It runs no Gazebo physics, no scoring plugin and
no thruster system.  Every number below is test data, not device fact.

The world: a paused flag that a world control request sets after the next
statistics sample (gz-sim answers the request when it queues it and applies it
in its step loop, after publishing that step's statistics), statistics
published every ``stats_period_s`` while subscribed, and the task information
silent while paused (the scoring plugin publishes on simulation time);
``/clock`` keeps answering with the frozen time.
"""

import time

from mhs.bridge.ros_transport import RecordingRosTransport

_WORLD = "/world/sydney_regatta"
_THRUSTER_TOPICS = ("/wamv/thrusters/left/thrust", "/wamv/thrusters/right/thrust",
                    "/wamv/thrusters/left/pos", "/wamv/thrusters/right/pos")
#: rcl_interfaces/msg/ParameterType values the bridge's ParamVec conversion uses.
_BOOL, _INTEGER, _DOUBLE, _STRING = 1, 2, 3, 4


class FakeVrx(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.clock_sec = 12                        # placeholder
        self.clock_nanosec = 340000000             # placeholder
        self.task_state = "running"                # placeholder
        self.elapsed_time = 42.0                   # placeholder
        self.remaining_time = 258.0                # placeholder
        self.timed_out = False                     # placeholder
        self.num_collisions = 0                    # placeholder
        self.score = 0.0                           # placeholder
        self.last_thrust = {}                      # placeholder: topic -> data
        self.withhold_clock = False                # placeholder negative-path switch
        self.withhold_task_info = False            # placeholder negative-path switch
        self.malformed_clock = False               # placeholder negative-path switch
        # The companion world (gz-sim through the operator's ros_gz bridges).
        self.paused = False                        # placeholder: the launch runs the world (-r)
        self.pending_pause = None                  # a queued world control, applied after the next sample
        self.stats_period_s = 0.1                  # placeholder: gz-sim throttles the statistics to 10 per second
        self.stats_subscriptions = set()           # recording helper
        self.last_stats_at = 0.0                   # recording helper
        self.iterations = 5000                     # placeholder
        self.controls = []                         # recording helper: the world control requests received
        self.fail_control = False                  # placeholder negative-path switch: the call is not answered
        self.reject_control = False                # placeholder negative-path switch: the bridge answers false
        self.ignore_pause = False                  # placeholder negative-path switch: the world keeps running
        self.silent_stats = False                  # placeholder negative-path switch: no statistics bridge

    def _clock_message(self):
        if self.malformed_clock:
            return {"not_clock": {"sec": self.clock_sec, "nanosec": self.clock_nanosec}}  # placeholder
        return {"clock": {"sec": self.clock_sec, "nanosec": self.clock_nanosec}}  # placeholder

    def _task_message(self):
        return {
            "header": {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": ""},  # placeholder
            "params": [
                {"name": "name", "value": {"type": _STRING, "string_value": "vrx"}},  # placeholder
                {"name": "state", "value": {"type": _STRING, "string_value": self.task_state}},  # placeholder
                {"name": "elapsed_time", "value": {"type": _DOUBLE, "double_value": self.elapsed_time}},  # placeholder
                {"name": "remaining_time",
                 "value": {"type": _DOUBLE, "double_value": self.remaining_time}},  # placeholder
                {"name": "timed_out", "value": {"type": _BOOL, "bool_value": self.timed_out}},  # placeholder
                {"name": "num_collisions",
                 "value": {"type": _INTEGER, "integer_value": self.num_collisions}},  # placeholder
                {"name": "score", "value": {"type": _DOUBLE, "double_value": self.score}},  # placeholder
            ],
        }

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            topic = message.get("topic")
            if topic == _WORLD + "/stats":
                self.stats_subscriptions.add(message.get("id"))
                return None
            if topic == "/clock" and not self.withhold_clock:
                return {"op": "publish", "topic": topic, "id": message.get("id"),
                        "msg": self._clock_message()}
            if topic == "/vrx/task/info" and not self.withhold_task_info and not self.paused:
                return {"op": "publish", "topic": topic, "id": message.get("id"),
                        "msg": self._task_message()}
            return None
        if operation == "unsubscribe":
            self.stats_subscriptions.discard(message.get("id"))
            return None
        if operation == "publish":
            topic = message.get("topic")
            if topic in _THRUSTER_TOPICS:
                body = message.get("msg")
                if isinstance(body, dict):
                    self.last_thrust[topic] = body.get("data")  # placeholder: recorded request value
            return None
        if operation == "call_service":
            return self._service(message)
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
                "sim_time": {"sec": self.clock_sec, "nanosec": self.clock_nanosec},          # placeholder
                "pause_time": {"sec": 0, "nanosec": 0},                                      # placeholder
                "real_time": {"sec": self.clock_sec, "nanosec": 0},                          # placeholder
                "paused": self.paused,
                "iterations": self.iterations,                                               # placeholder
                "model_count": 40,                                                           # placeholder
                "real_time_factor": 1.0,                                                     # placeholder
            }
            if self.pending_pause is not None:
                self.paused, self.pending_pause = self.pending_pause, None
            if not self.paused:
                self.iterations += 25  # placeholder
            return {"op": "publish", "topic": _WORLD + "/stats", "msg": sample}
        return super().recv(timeout_s=min(timeout_s or 0.01, 0.01))

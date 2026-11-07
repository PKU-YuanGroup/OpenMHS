"""ROS-free contract fake for the pinned Spot ROS 2 topic surface.

The fake answers one fresh subscription per observation and records the
advertise/publish pair for ``/cmd_vel``.  It also answers the companion
Ignition world control and statistics that the operator's ros_gz bridges
carry: the ``/world/simple_tunnel/control`` service
(``ros_gz_interfaces/srv/ControlWorld``) and the ``/world/simple_tunnel/stats``
topic (``WorldStatistics``).  It is a rosbridge contract stand-in, not a
recording of captured traffic: it runs no Ignition Gazebo, CHAMP controller
or ROS graph.  Every number below is test data and is marked ``# placeholder``;
none is a device fact or a safety limit.

The world: a paused flag that a world control request sets after the next
statistics sample (the simulator answers the request when it queues it and
applies it in its step loop, after publishing that step's statistics),
statistics published every ``stats_period_s`` while subscribed, and
``/spot/odometry`` silent while paused.  ``/clock`` keeps answering with the
frozen placeholder time, and ``/spot/joint_states`` keeps answering, matching
the publishers that do not go silent when paused.

The fake starts unpaused.  A real server starts paused when the launch passes
no ``-r``; this stand-in starts running so the explicit reads succeed before
an e-stop, and so the ``ignore_pause`` switch (the world keeps running) cannot
look like a stop on a world that was already paused.
"""

import time

from mhs.bridge.ros_transport import RecordingRosTransport

_WORLD = "/world/simple_tunnel"

#: Placeholder joint order.  Not the model's joint_name list.
_JOINT_NAMES = [
    "front_left_hip_x",       # placeholder name
    "front_left_hip_y",       # placeholder name
    "front_left_knee",        # placeholder name
    "front_right_hip_x",      # placeholder name
    "front_right_hip_y",      # placeholder name
    "front_right_knee",       # placeholder name
    "rear_left_hip_x",        # placeholder name
    "rear_left_hip_y",        # placeholder name
    "rear_left_knee",         # placeholder name
    "rear_right_hip_x",       # placeholder name
    "rear_right_hip_y",       # placeholder name
    "rear_right_knee",        # placeholder name
]


class FakeSpotGazeboRos2(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.clock_sec = 12                      # placeholder
        self.clock_nanosec = 340000000           # placeholder
        self.odom_position = {"x": 0.0, "y": 0.0, "z": 0.0}              # placeholder
        self.odom_orientation = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}  # placeholder
        self.last_linear_velocity = 0.0         # placeholder
        self.last_lateral_velocity = 0.0        # placeholder
        self.last_angular_velocity = 0.0        # placeholder
        self.joint_names = list(_JOINT_NAMES)   # placeholder
        self.joint_positions = [0.0] * 12       # placeholder
        self.cmd_vel_messages = []
        self.silent_topics = set()              # placeholder negative-path switch
        self.reject_publish = False             # placeholder negative-path switch
        # The companion world (Ignition through the operator's ros_gz bridges).
        # Unpaused at start: see the module docstring.
        self.paused = False                     # placeholder
        self.pending_pause = None               # a queued world control, applied after the next sample
        self.stats_period_s = 0.1               # placeholder: the statistics are throttled to 10 per second
        self.stats_subscriptions = set()        # recording helper
        self.last_stats_at = 0.0                # recording helper
        self.iterations = 700                   # placeholder
        self.controls = []                      # recording helper: the world control requests received
        self.fail_control = False               # placeholder negative-path switch: the call is not answered
        self.reject_control = False             # placeholder negative-path switch: the bridge answers false
        self.ignore_pause = False               # placeholder negative-path switch: the world keeps running
        self.silent_stats = False               # placeholder negative-path switch: no statistics bridge

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            if message.get("topic") == _WORLD + "/stats":
                self.stats_subscriptions.add(message.get("id"))
                return None
            return self._observation(message)
        if operation == "unsubscribe":
            self.stats_subscriptions.discard(message.get("id"))
            return None
        if operation == "advertise":
            return None
        if operation == "publish":
            self._record_publish(message)
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
            return dict(reply, values={"success": False})  # a failed request
        pause = bool(request.get("pause"))
        # ignore_pause refuses to store a pause-true request, so a world that is running stays running and the
        # read-back cannot confirm.  The driver sends no pause-false request.
        if not (pause and self.ignore_pause):
            self.pending_pause = pause
        return dict(reply, values={"success": True})  # true for any queued request

    def recv(self, *, timeout_s=None):
        now = time.monotonic()
        if self.stats_subscriptions and not self.silent_stats and now - self.last_stats_at >= self.stats_period_s:
            self.last_stats_at = now
            sample = {
                "header": {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": "", "data": []},  # unstamped header
                "sim_time": {"sec": self.clock_sec, "nanosec": self.clock_nanosec},          # placeholder
                "pause_time": {"sec": 0, "nanosec": 0},                                      # placeholder
                "real_time": {"sec": self.clock_sec, "nanosec": 0},                          # placeholder
                "paused": self.paused,
                "iterations": self.iterations,                                               # placeholder
                "model_count": 2,                                                            # placeholder
                "real_time_factor": 1.0,                                                     # placeholder
            }
            if self.pending_pause is not None:
                self.paused, self.pending_pause = self.pending_pause, None
            if not self.paused:
                self.iterations += 10  # placeholder
            return {"op": "publish", "topic": _WORLD + "/stats", "msg": sample}
        return super().recv(timeout_s=min(timeout_s or 0.01, 0.01))

    def _observation(self, message):
        topic = message.get("topic")
        ident = message.get("id")
        if topic in self.silent_topics:
            return None
        if self.paused and topic == "/spot/odometry":
            return None  # OdometryPublisher::PostUpdate returns when paused
        if topic == "/clock":
            # Still answered while paused: PublishStats publishes the clock with sim time that does not advance.
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {"clock": {"sec": self.clock_sec, "nanosec": self.clock_nanosec}},  # placeholder
            }
        if topic == "/spot/joint_states":
            # Still answered while paused: JointStatePublisher::PostUpdate has no paused return.
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "name": list(self.joint_names),                 # placeholder
                    "position": list(self.joint_positions),         # placeholder
                    "velocity": [0.0] * len(self.joint_positions),  # placeholder
                    "effort": [0.0] * len(self.joint_positions),    # placeholder
                },
            }
        if topic == "/spot/odometry":
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "header": {"frame_id": "odom"},  # placeholder frame
                    "child_frame_id": "body",        # placeholder frame
                    "pose": {"pose": {
                        "position": dict(self.odom_position),          # placeholder
                        "orientation": dict(self.odom_orientation),    # placeholder
                    }},
                    "twist": {"twist": {
                        "linear": {"x": self.last_linear_velocity, "y": self.last_lateral_velocity,
                                   "z": 0.0},  # placeholder
                        "angular": {"x": 0.0, "y": 0.0, "z": self.last_angular_velocity},  # placeholder
                    }},
                },
            }
        return None

    def _record_publish(self, message):
        if self.reject_publish:
            raise RuntimeError("fake rosbridge transport rejected the publication")  # placeholder
        topic = message.get("topic")
        if topic != "/cmd_vel":
            return
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        linear = body.get("linear") if isinstance(body.get("linear"), dict) else {}
        angular = body.get("angular") if isinstance(body.get("angular"), dict) else {}
        self.last_linear_velocity = linear.get("x", 0.0)    # placeholder default
        self.last_lateral_velocity = linear.get("y", 0.0)   # placeholder default
        self.last_angular_velocity = angular.get("z", 0.0)  # placeholder default
        self.cmd_vel_messages.append(message)

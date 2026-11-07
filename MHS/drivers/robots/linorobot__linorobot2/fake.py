"""ROS-free analytic fake for the pinned linorobot2 Gazebo topic contract.

The fake models the wire contract declared in ``driver.py``:

* subscriptions to ``/odom/unfiltered``, ``/clock``, ``/imu/data`` and ``/scan``;
* an advertise and a publish of ``geometry_msgs/msg/Twist`` on ``/cmd_vel``;
* the companion gz-sim world control and statistics that the operator's
  ros_gz bridges carry: the ``/world/turtlebot3_world/control`` service
  (``ros_gz_interfaces/srv/ControlWorld``) and the
  ``/world/turtlebot3_world/stats`` topic (``WorldStatistics``).

It is an analytic contract stand-in, not a recording of captured traffic: it
answers canned observations and keeps the last publication in plain
attributes.  It runs no ROS, Gazebo, DiffDrive plugin, EKF, sensor or physics.
Every number below is test data and is marked ``# placeholder``; none is a
device fact or a safety limit.

The world: a paused flag that a world control request sets after the next
statistics sample (gz-sim answers the request when it queues it and applies
it in its step loop, after publishing that step's statistics), statistics
published every ``stats_period_s`` while subscribed, and the world-update
topics (odometry, IMU, scan) silent while paused; ``/clock`` keeps answering
with the frozen time.  The node's own 0.2 s zero-Twist timer is not modelled.
"""

import time

from mhs.bridge.ros_transport import RecordingRosTransport

_WORLD = "/world/turtlebot3_world"


class FakeLinorobot2(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Placeholder echo state.  A live odometry sample comes from the
        # Gazebo DiffDrive plugin; the fake echoes only the last published
        # twist so a command has an observable contract effect.
        self.last_linear_velocity = 0.0       # placeholder
        self.last_angular_velocity = 0.0      # placeholder
        self.pose_x = 0.0                     # placeholder
        self.pose_y = 0.0                     # placeholder
        self.clock_sec = 12                   # placeholder
        self.clock_nanosec = 340000000        # placeholder
        self.cmd_vel_messages = []            # recording helper, no device meaning
        self.malformed_odom = False           # placeholder negative-path switch
        self.reject_publish = False           # placeholder negative-path switch
        # The companion world (gz-sim through the operator's ros_gz bridges).
        self.paused = False                   # placeholder: the launch runs the world (-r)
        self.pending_pause = None             # a queued world control, applied after the next sample
        self.stats_period_s = 0.1             # placeholder: gz-sim throttles the statistics to 10 per second
        self.stats_subscriptions = set()      # recording helper
        self.last_stats_at = 0.0              # recording helper
        self.iterations = 1000                # placeholder
        self.controls = []                    # recording helper: the world control requests received
        self.fail_control = False             # placeholder negative-path switch: the control call is not answered
        self.reject_control = False           # placeholder negative-path switch: the bridge answers success false
        self.ignore_pause = False             # placeholder negative-path switch: another client keeps it running
        self.silent_stats = False             # placeholder negative-path switch: no statistics bridge

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
                "model_count": 3,                                                            # placeholder
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
        if self.paused and topic in ("/odom/unfiltered", "/imu/data", "/scan"):
            return None  # a paused world runs no DiffDrive, IMU or sensor update
        if topic == "/odom/unfiltered":
            if self.malformed_odom:
                return {"op": "publish", "topic": topic, "id": ident, "msg": "malformed"}  # placeholder
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "header": {"frame_id": "odom"},  # placeholder
                    "pose": {
                        "pose": {
                            "position": {"x": self.pose_x, "y": self.pose_y, "z": 0.0},  # placeholder
                            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
                        }
                    },
                    "twist": {
                        "twist": {
                            "linear": {"x": self.last_linear_velocity, "y": 0.0, "z": 0.0},  # placeholder
                            "angular": {"x": 0.0, "y": 0.0,
                                        "z": self.last_angular_velocity},  # placeholder
                        }
                    },
                },
            }
        if topic == "/clock":
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {"clock": {"sec": self.clock_sec, "nanosec": self.clock_nanosec}},  # placeholder
            }
        if topic == "/imu/data":
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "header": {"frame_id": "imu_link"},  # placeholder
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},  # placeholder
                    "angular_velocity": {"x": 0.0, "y": 0.0, "z": 0.0},  # placeholder
                    "linear_acceleration": {"x": 0.0, "y": 0.0, "z": 9.8},  # placeholder
                },
            }
        if topic == "/scan":
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "header": {"frame_id": "laser"},  # placeholder
                    "angle_min": -3.1416,             # placeholder; the real generic laser is 360 rays
                    "angle_max": 3.1416,              # placeholder
                    "angle_increment": 0.017453,       # placeholder
                    "range_min": 0.08,                 # placeholder
                    "range_max": 12.0,                 # placeholder
                    "ranges": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],  # placeholder, reduced array
                },
            }
        return None

    def _record_publish(self, message):
        if self.reject_publish:
            raise RuntimeError("fake rosbridge transport rejected the publication")  # placeholder
        topic = message.get("topic")
        body = message.get("msg") if isinstance(message.get("msg"), dict) else {}
        if topic == "/cmd_vel":
            linear = body.get("linear") if isinstance(body.get("linear"), dict) else {}
            angular = body.get("angular") if isinstance(body.get("angular"), dict) else {}
            self.last_linear_velocity = linear.get("x", 0.0)   # placeholder default
            self.last_angular_velocity = angular.get("z", 0.0)  # placeholder default
            self.cmd_vel_messages.append(message)

"""ROS-free canned transport fake for the pinned TurtleBot3 fake-node endpoints.

The fake models only the wire contract declared in ``driver.py``:

* a ``publish`` of ``geometry_msgs/msg/Twist`` on ``/cmd_vel``;
* subscriptions to ``nav_msgs/msg/Odometry`` on ``/odom``;
* subscriptions to ``sensor_msgs/msg/JointState`` on ``/joint_states``.

It runs no turtlebot3_fake_node code, no ROS graph and no physics.  Every
number below is test data, not a device fact, and is marked ``# placeholder``.
It is an analytic contract stand-in, not a recording of captured traffic.

The sensed-confirmation stop needs stamped samples.  An ``/odom`` subscription
is answered with a short burst.  The first sample is the stored pre-request
state.  Later samples use the current command.  A non-zero command is a
projection and is not stored, so two reads with no zero command agree.  A zero
command leaves the pose where it was and stores that rest.  The node applies
setpoints immediately and does not ramp, so a zero command freezes the pose on
the next sample.  Producer stamps advance by the subscription's
``throttle_rate`` (milliseconds), or by a placeholder 10 ms tick when the
subscription sets none.
"""

import math

from mhs.bridge.ros_transport import RecordingRosTransport

_BURST = 12             # placeholder: under the confirmation ring (capacity 16 for consecutive 5)
_TICK_MS = 10           # placeholder: stamp step when the subscription sets no throttle_rate
_INITIAL_LINEAR = 0.2   # placeholder: the fake starts driving, so the pose is not already at rest
_RADIUS = 0.033         # placeholder: burger.yaml wheels.radius, used only to fill joint velocities
_SEPARATION = 0.160     # placeholder: burger.yaml wheels.separation, used only to fill joint velocities


def _wheels(linear, angular):
    """Placeholder left and right wheel speeds for a commanded body twist.  Not a device limit."""
    half = _SEPARATION / 2.0
    return [round((linear - angular * half) / _RADIUS, 9),
            round((linear + angular * half) / _RADIUS, 9)]


class FakeTurtlebot3Simulations(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        self.stored_x = 0.0                 # placeholder
        self.stored_y = 0.0                 # placeholder
        self.stored_yaw = 0.0               # placeholder
        self.stored_linear = _INITIAL_LINEAR  # placeholder: pre-request body speed
        self.stored_angular = 0.0           # placeholder
        self.goal_linear = _INITIAL_LINEAR  # placeholder: the command the next samples follow
        self.goal_angular = 0.0             # placeholder
        self.clock_ns = 1_000_000_000       # placeholder: non-zero so the first stamp is set
        self.last_cmd_vel = None            # placeholder observation for tests
        self.cmd_vel_messages = []          # recording helper, no device meaning
        self.wheel_positions = [0.0, 0.0]   # placeholder
        self.silent_odom = False            # placeholder negative-path switch
        self.omit_odom_twist = False        # placeholder negative-path switch
        self.bad_pose_type = False          # placeholder negative-path switch
        self.silent_joint_states = False    # placeholder negative-path switch
        self.competing_publisher = False    # placeholder: another /cmd_vel publisher keeps driving
        self.ignore_zero = False            # placeholder: record a zero Twist and do not apply it
        self.frozen_stamps = False          # placeholder: every /odom sample repeats one stamp
        self.null_pose = False              # placeholder: pose.position.x is null in every /odom sample
        # placeholder: joint velocities are NaN while /odom stays the finite pose path.  This is the
        # wire state of radius 0, a non-zero separation and a zero command (cpp:204-210).  The pose
        # confirmation does not read it.
        self.nan_wheel_velocity = False

    def _stamp(self, stamp_ns):
        return {"sec": int(stamp_ns // 1_000_000_000), "nanosec": int(stamp_ns % 1_000_000_000)}

    def _orientation(self, yaw):
        return {"x": 0.0, "y": 0.0,                                          # placeholder
                "z": round(math.sin(yaw / 2.0), 9),                          # placeholder
                "w": round(math.cos(yaw / 2.0), 9)}                          # placeholder

    def _odom_message(self, ident, x, y, yaw, linear, angular, stamp_ns):
        if self.bad_pose_type:
            pose = "not-an-object"  # placeholder
        else:
            pose = {"pose": {
                "position": {"x": None if self.null_pose else x, "y": y, "z": 0.0},  # placeholder
                "orientation": self._orientation(yaw),
            }}
        message = {"header": {"stamp": self._stamp(stamp_ns), "frame_id": "odom"},  # placeholder
                   "pose": pose}
        if not self.omit_odom_twist:
            message["twist"] = {"twist": {
                "linear": {"x": linear, "y": 0.0, "z": 0.0},                  # placeholder
                "angular": {"x": 0.0, "y": 0.0, "z": angular},                # placeholder
            }}
        return {"op": "publish", "topic": "/odom", "id": ident, "msg": message}

    def _joint_message(self, ident):
        return {
            "op": "publish",
            "topic": "/joint_states",
            "id": ident,
            "msg": {
                "name": ["wheel_left_joint", "wheel_right_joint"],  # placeholder names match the source
                "position": list(self.wheel_positions),              # placeholder
                "velocity": ([float("nan"), float("nan")] if self.nan_wheel_velocity
                             else _wheels(self.goal_linear, self.goal_angular)),  # placeholder
                "effort": [0.0, 0.0],                                # placeholder, not exposed
            },
        }

    def _period_ns(self, message):
        rate = message.get("throttle_rate")
        period_ms = rate if type(rate) is int and rate > 0 else _TICK_MS
        return period_ms * 1_000_000  # placeholder: milliseconds to nanoseconds

    def _odom_burst(self, message):
        if self.silent_odom:
            return None
        if self.competing_publisher:
            self.goal_linear = _INITIAL_LINEAR  # placeholder: another publisher keeps the base moving
            self.goal_angular = 0.0             # placeholder
        ident = message.get("id")
        period_ns = self._period_ns(message)
        dt = period_ns / 1_000_000_000.0
        x, y, yaw = self.stored_x, self.stored_y, self.stored_yaw
        linear, angular = self.stored_linear, self.stored_angular
        frozen = self.clock_ns
        samples = []
        for index in range(_BURST):
            stamp_ns = frozen if self.frozen_stamps else self.clock_ns
            samples.append(self._odom_message(ident, x, y, yaw, linear, angular, stamp_ns))
            linear, angular = self.goal_linear, self.goal_angular
            if linear != 0.0 or angular != 0.0:
                yaw = yaw + angular * dt
                x = round(x + linear * math.cos(yaw) * dt, 9)
                y = round(y + linear * math.sin(yaw) * dt, 9)
            self.clock_ns += period_ns
        # The first sample was the stored state.  Later samples follow the command now in effect.
        # A zero command does not move the pose, so the rested pose is what gets stored.
        if (self.goal_linear == 0.0 and self.goal_angular == 0.0 and not self.competing_publisher):
            self.stored_x, self.stored_y, self.stored_yaw = x, y, yaw
            self.stored_linear = 0.0
            self.stored_angular = 0.0
        return samples

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            topic = message.get("topic")
            ident = message.get("id")
            if topic == "/odom":
                return self._odom_burst(message)
            if topic == "/joint_states":
                if self.silent_joint_states:
                    return None
                return self._joint_message(ident)
            return None
        if operation == "publish":
            topic = message.get("topic")
            if topic == "/cmd_vel":
                self._apply_cmd_vel(message.get("msg") or {})
            return None
        return None

    def _apply_cmd_vel(self, msg):
        linear = msg.get("linear") or {}
        angular = msg.get("angular") or {}
        self.last_cmd_vel = {
            "linear": {key: float(linear.get(key, 0.0)) for key in ("x", "y", "z")},  # placeholder
            "angular": {key: float(angular.get(key, 0.0)) for key in ("x", "y", "z")},  # placeholder
        }
        self.cmd_vel_messages.append(self.last_cmd_vel)
        commanded_linear = self.last_cmd_vel["linear"]["x"]
        commanded_angular = self.last_cmd_vel["angular"]["z"]
        if self.ignore_zero and commanded_linear == 0.0 and commanded_angular == 0.0:
            return
        # A publication updates the command the next samples follow.  It does not replace the stored
        # pose or the stored twist: the confirmation's first sample is still the pre-request state.
        self.goal_linear = commanded_linear
        self.goal_angular = commanded_angular

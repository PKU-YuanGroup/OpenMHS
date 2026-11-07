"""ROS-free analytic fake for the pinned ros2-amr-simulation topic contract.

The fake models the wire contract declared in ``driver.py``:

* subscriptions to ``/odom``, ``/clock`` and ``/joint_states``;
* an advertise and a publish of ``geometry_msgs/msg/Twist`` on ``/cmd_vel``.

It is an analytic contract stand-in, not a recording of captured traffic: it
answers canned observations and keeps the last publication in plain
attributes.  It runs no ROS 2 graph, Gazebo, diff-drive plugin, world or
physics.  Every number below is test data and is marked ``# placeholder``;
none is a device fact or a safety limit.

The clone exposes no ROS service or action that could stop the base, so the
fake does not model one.  The sensed-confirmation stop (SAFE-049) needs
stamped samples: an ``/odom`` subscription is answered with a short burst
whose ROS 2 stamps (sec, nanosec) increase on a placeholder clock, each sample
one tick of a placeholder speed-limiter ramp and pose integration; the first
sample of a burst is the stored state.  The fake starts driving, so nothing
satisfies the predicate before the zero Twist arrived.  While a non-zero
velocity is commanded the burst is a projection that is not stored (so two
reads without a command agree, as the protocol requires of a device that is
not being commanded); once zero velocity is commanded the ramp-down to rest
is stored.
"""

import math

from mhs.bridge.ros_transport import RecordingRosTransport

_BURST = 16            # placeholder: samples per /odom subscription
_DT = 0.1              # placeholder: simulated seconds per sample
_LINEAR_ACCEL = 1.0    # placeholder ramp, the value of max_linear_acceleration at gazebo.xacro:196
_ANGULAR_ACCEL = 2.0   # placeholder ramp, the value of max_angular_acceleration at gazebo.xacro:197


class FakeRos2AmrSimulation(RecordingRosTransport):
    def __init__(self, **_options):
        super().__init__(handler=self._respond)
        # Placeholder echo state.  Real odometry comes from the Gazebo
        # DiffDrive plugin; the fake echoes only the last published twist so a
        # publication has an observable contract effect.
        self.last_linear_velocity = 0.3       # placeholder: driving at the menu's default speed
        self.last_angular_velocity = 0.0      # placeholder
        self.linear = 0.3                     # placeholder actual speed (the ramp follows the command)
        self.angular = 0.0                    # placeholder actual yaw rate
        self.pose_x = 0.0                     # placeholder
        self.pose_y = 0.0                     # placeholder
        self.yaw = 0.0                        # placeholder
        self.clock_ns = 100_000_000_000       # placeholder simulated clock for the /odom stamps
        self.clock_sec = 12                   # placeholder
        self.clock_nanosec = 340000000        # placeholder
        self.joint_names = ["left_wheel_joint", "right_wheel_joint"]  # placeholder
        self.joint_positions = [0.0, 0.0]     # placeholder
        self.joint_velocities = [0.0, 0.0]    # placeholder
        self.cmd_vel_messages = []            # recording helper, no device meaning
        self.malformed_odom = False           # placeholder negative-path switch
        self.reject_publish = False           # placeholder negative-path switch
        self.competing_publisher = False      # placeholder: another /cmd_vel publisher keeps the base moving
        self.frozen_stamps = False            # placeholder: every /odom sample repeats one stamp
        self.null_pose = False                # placeholder: pose.position.x is null in every /odom sample
        self.silent_odom = False              # placeholder: /odom answers nothing

    def _ramp(self, actual, target, limit):
        step = limit * _DT
        if abs(target - actual) <= step:
            return target
        return actual + step if target > actual else actual - step

    def _step(self, state):
        """One placeholder tick of (x, y, yaw, linear, angular) toward the commanded twist."""
        x, y, yaw, linear, angular = state
        linear = round(self._ramp(linear, float(self.last_linear_velocity), _LINEAR_ACCEL), 9)
        angular = round(self._ramp(angular, float(self.last_angular_velocity), _ANGULAR_ACCEL), 9)
        yaw = yaw + angular * _DT
        x = round(x + linear * math.cos(yaw) * _DT, 9)
        y = round(y + linear * math.sin(yaw) * _DT, 9)
        return x, y, yaw, linear, angular

    def _respond(self, message):
        operation = message.get("op")
        if operation == "subscribe":
            return self._observation(message)
        if operation == "advertise":
            return None
        if operation == "publish":
            self._record_publish(message)
            return None
        return None

    def _observation(self, message):
        topic = message.get("topic")
        ident = message.get("id")
        if topic == "/odom":
            if self.malformed_odom:
                return {"op": "publish", "topic": topic, "id": ident, "msg": "malformed"}  # placeholder
            if self.silent_odom:
                return None
            if self.competing_publisher:
                self.last_linear_velocity = 0.3  # placeholder: amr_menu.py republishes its speed
            state = (self.pose_x, self.pose_y, self.yaw, self.linear, self.angular)
            samples = []
            for _ in range(_BURST):
                x, y, yaw = state[0], state[1], state[2]
                samples.append({
                    "op": "publish",
                    "topic": topic,
                    "id": ident,
                    "msg": {
                        "header": {"stamp": {"sec": self.clock_ns // 1_000_000_000,
                                             "nanosec": self.clock_ns % 1_000_000_000},
                                   "frame_id": "odom"},  # placeholder
                        "pose": {
                            "pose": {
                                "position": {"x": None if self.null_pose else x, "y": y,
                                             "z": 0.0},  # placeholder
                                "orientation": {"x": 0.0, "y": 0.0, "z": round(math.sin(yaw / 2), 9),
                                                "w": round(math.cos(yaw / 2), 9)},  # placeholder
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
                })
                state = self._step(state)
                if not self.frozen_stamps:
                    self.clock_ns += int(_DT * 1_000_000_000)
            if self.last_linear_velocity == 0.0 and self.last_angular_velocity == 0.0:
                # Zero velocity commanded: the ramp-down to rest is stored (placeholder).
                self.pose_x, self.pose_y, self.yaw, self.linear, self.angular = state
            return samples
        if topic == "/clock":
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {"clock": {"sec": self.clock_sec, "nanosec": self.clock_nanosec}},  # placeholder
            }
        if topic == "/joint_states":
            return {
                "op": "publish",
                "topic": topic,
                "id": ident,
                "msg": {
                    "header": {"frame_id": "base_link"},  # placeholder
                    "name": list(self.joint_names),        # placeholder
                    "position": list(self.joint_positions),   # placeholder
                    "velocity": list(self.joint_velocities),  # placeholder
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

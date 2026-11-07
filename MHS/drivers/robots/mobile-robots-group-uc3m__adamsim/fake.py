"""Pure-Python kinematic fake for the ADAMSim differential-drive base.

The fake mirrors the pinned surface the driver relies on: ``FakeAdam.step``, ``FakeAdam.t``,
``FakeAdam.navigation`` with ``send_velocity`` and ``move_wheels``, ``FakeAdam.sensors`` with
``get_camera_angle`` and ``FakeAdam.arm_kinematics`` with ``get_arm_joint_angles``.  It runs no
PyBullet, ROS, physics, contacts, wheel friction or GUI, and it is not a recording of captured
simulator traffic.  Every number below is either a placeholder test value or an upstream constructor
value copied to mirror the pinned clamp/period; none is a device limit or a Fact.
"""

import math


class _FakeNavigation:
    """Stand-in for scripts.navigation.Navigation (public API only)."""

    def __init__(self):
        # Upstream constructor defaults, scripts/navigation.py:12-15, copied to mirror the pinned
        # conversion and clamp.  They are configurable defaults, not device limits.
        self.wheel_radius = 0.0762
        self.wheel_distance = 0.436
        self.linear_speed = 6.55
        self.angular_speed = 1.0
        self.start_pos = [0.0, 0.0, 0.0]  # placeholder
        self._linear = 0.0  # placeholder state
        self._angular = 0.0  # placeholder state

    def move_wheels(self, left_wheel_speed, right_wheel_speed, force=100):
        # Mirrors the inverse of the conversion in scripts/navigation.py:211-212.
        self._linear = self.wheel_radius * (float(right_wheel_speed) + float(left_wheel_speed)) / 2.0
        self._angular = self.wheel_radius * (float(right_wheel_speed) - float(left_wheel_speed)) / self.wheel_distance

    def send_velocity(self, v, w, force=100):
        # Mirrors the clamp in scripts/navigation.py:208-209.
        self._linear = max(-self.linear_speed, min(self.linear_speed, float(v)))
        self._angular = max(-self.angular_speed, min(self.angular_speed, float(w)))


class _FakeSensors:
    """Stand-in for scripts.sensors.Sensors.get_camera_angle."""

    def __init__(self, adam):
        self.adam = adam
        self.camera_angle = 0.0  # placeholder

    def get_camera_angle(self):
        return self.camera_angle  # placeholder


class _FakeArmKinematics:
    """Stand-in for scripts.arms_kinematics.ArmsKinematics.get_arm_joint_angles."""

    def __init__(self, adam):
        self.adam = adam
        self._angles = {
            "left": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],   # placeholder state
            "right": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # placeholder state
        }

    def get_arm_joint_angles(self, arm):
        if arm not in ("left", "right"):
            raise ValueError("arm must be 'left' or 'right'")
        return list(self._angles[arm])  # placeholder state


class FakeAdam:
    """Kinematic stand-in for scripts.adam.ADAM, restricted to the members this driver uses."""

    def __init__(self, **_options):
        self.t = 0.01  # upstream constructor value, scripts/adam.py:77
        self.use_realtime = False  # placeholder configuration
        self.use_ros = False  # placeholder configuration
        self.robot_id = 0  # placeholder simulator handle
        self.navigation = _FakeNavigation()
        self.sensors = _FakeSensors(self)
        self.arm_kinematics = _FakeArmKinematics(self)
        self._x = 0.0  # placeholder state
        self._y = 0.0  # placeholder state
        self._theta = 0.0  # placeholder state
        self._tick = 0  # placeholder state

    def step(self):
        # Mirrors one ADAM.step control period (scripts/adam.py:173-193) with simple dead reckoning.
        self._tick += 1
        self._x += self.navigation._linear * math.cos(self._theta) * self.t
        self._y += self.navigation._linear * math.sin(self._theta) * self.t
        self._theta += self.navigation._angular * self.t

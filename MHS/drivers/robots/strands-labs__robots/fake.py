"""Fake backend of the Yahboom M3 Pro driver: an in-memory stand-in for the upstream ROS 2 driver.

Gate G7: every public member defined here is a method or property of
``strands_robots.drivers.yahboom_m3pro:YahboomM3ProDriver`` at the pinned commit
f19439bf8c80e7ae6f0fdc0f003d850d638dd97d, with the upstream parameter names.  It keeps the last commanded servo
degrees and Twist, and answers the upstream envelopes (``status``/``content``) the driver parses.

All joint positions, odometry and IMU values below are test data, not facts about a robot; each literal is marked
``# placeholder``.  The fake has no kinematics, no motion over time and no ROS graph: a command is recorded when the
call returns.  Nothing here talks to a device.
"""

import math

#: Servo travel in degrees, mirroring the upstream vendor table (yahboom_m3pro_wire.py:61-71).  Test data here.
SERVO_LIMITS = ((0, 180), (0, 180), (0, 180), (0, 180), (0, 270), (30, 180))  # placeholder
#: The upstream grasp-init pose, with the gripper open (yahboom_m3pro_wire.py:82-84).  Test data here.
HOME_DEG = (90, 120, 0, 0, 90, 180)  # placeholder
#: The upstream default servo travel time.  Test data here.
DEFAULT_MOVE_TIME_MS = 1500  # placeholder


def _refuse(reason):
    return {"status": "error", "content": [{"text": reason}]}


def _success(payload):
    return {"status": "success", "content": [{"json": dict(payload)}]}


class FakeYahboomM3Pro:
    """The upstream driver's surface, in memory, with no transport."""

    def __init__(self, **_options):
        self._connected = False
        self._connect_error = None
        self._last_arm_deg = None
        self._last_twist = None
        self._odom = {"position": {"x": 0.0, "y": 0.0, "z": 0.0}}  # placeholder
        self._imu = {"orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}}  # placeholder
        self._stop_calls = 0

    @property
    def is_connected(self):
        """Whether the fake graph is up."""
        return self._connected

    def connect_eagerly(self):
        """Reach the fake graph; idempotent like the upstream method."""
        self._connected = True
        self._connect_error = None
        return None

    def get_observation(self):
        """The model-shaped joint positions, or {} before a command (the upstream returns {} without /joint_states)."""
        if not self._connected:
            return {}
        return self.last_arm_command() or {}

    def last_arm_command(self):
        """The last commanded arm pose in model radians, or None before a command."""
        if self._last_arm_deg is None:
            return None
        pose = {}
        for index, degrees in enumerate(self._last_arm_deg, start=1):
            name = "gripper" if index == 6 else f"arm{index}"
            pose[f"{name}.pos"] = _model_radians(index, degrees)
        return pose

    def read_state(self):
        """One cached odometry and IMU sample."""
        return {"odom": dict(self._odom) if self._odom else None,
                "imu": dict(self._imu) if self._imu else None}

    def set_arm_degrees(self, joints, time_ms=None):
        """Record six servo angles in degrees; the upstream checks the servo travel."""
        if not self._connected:
            return _refuse("set_arm_degrees: not connected - call connect_eagerly() first")
        if not isinstance(joints, (list, tuple)) or len(joints) != 6:
            return _refuse("set_arm_degrees: joints must be six servo angles in degrees")
        try:
            degrees = [int(round(float(angle))) for angle in joints]
        except (TypeError, ValueError):
            return _refuse("set_arm_degrees: every joint must be a number")
        for index, angle in enumerate(degrees, start=1):
            low, high = SERVO_LIMITS[index - 1]
            if not low <= angle <= high:
                return _refuse(f"set_arm_degrees: joint{index}={angle} is outside {low}-{high} degrees")
        duration = DEFAULT_MOVE_TIME_MS if time_ms is None else int(time_ms)
        self._last_arm_deg = tuple(degrees)
        return _success({"arm_deg": list(degrees), "time_ms": duration})

    def set_gripper(self, open, time_ms=None):  # noqa: A002 - the upstream verb's own word
        """Open (180 degrees) or close (30 degrees) the gripper, leaving the other servos where they are."""
        if not isinstance(open, bool):
            return _refuse("set_gripper: open must be true or false")
        degrees = list(self._last_arm_deg or HOME_DEG)
        degrees[5] = 180 if open else 30  # placeholder
        return self.set_arm_degrees(degrees, time_ms=time_ms)

    def home(self, time_ms=None):
        """The vendor grasp-init pose, gripper open."""
        return self.set_arm_degrees(list(HOME_DEG), time_ms=time_ms)

    def move(self, linear_x=0.0, linear_y=0.0, angular_z=0.0, duration_s=None, *, tool_context=None):
        """Record a Twist for the duration and send the trailing zero Twist, without waiting."""
        del tool_context
        if not self._connected:
            return _refuse("move: not connected - call connect_eagerly() first")
        if duration_s is None:
            return _refuse("move: duration_s is required")
        try:
            duration = float(duration_s)
        except (TypeError, ValueError):
            return _refuse("move: duration_s must be a number")
        if duration <= 0.0:  # placeholder
            return _refuse("move: duration_s must be positive")
        twist = {"linear.x": float(linear_x), "linear.y": float(linear_y),
                 "angular.z": float(angular_z)}  # placeholder
        self._last_twist = dict(twist)
        stopped = self.stop_task()
        if stopped.get("status") != "success":
            return stopped
        return _success({"commanded": twist, "held_s": duration, "frames": 1, "stopped": True})  # placeholder

    def stop_task(self, *, tool_context=None):
        """Command the zero Twist (the base halt); the arm keeps its pose."""
        del tool_context
        self._stop_calls += 1
        if not self._connected:
            return _refuse("stop_task: not connected")
        zero = {"linear.x": 0.0, "linear.y": 0.0, "angular.z": 0.0}  # placeholder
        self._last_twist = dict(zero)
        return _success({"driver": "yahboom_m3pro", "twist": zero})


def _model_radians(index, degrees):
    """Servo degrees -> the model radians the upstream reports; the inverse of its map."""
    value = float(degrees)
    if index <= 5:
        return math.radians(value - 90.0)  # placeholder constant; upstream map yahboom_m3pro.py:58
    fraction_closed = (value - 180.0) / (30.0 - 180.0)  # placeholder endpoints; upstream map yahboom_m3pro.py:61-62
    return 0.0 + fraction_closed * (-1.54 - 0.0)  # placeholder endpoints; upstream map yahboom_m3pro.py:61-62

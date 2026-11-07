"""Fake backend of the Cozmo driver: an in-memory stand-in for cozmo.robot:Robot.

Gate G7: every public member defined here is a method or property of Robot (src/cozmo/robot.py): the
properties head_angle (robot.py:1023), lift_height (1033), lift_ratio (1041), is_charging (993) and
is_cliff_detected (998), the commands set_head_angle (1515), set_lift_height (1548) and stop_all_motors (1371).
The two setters take the arguments the upstream takes (a cozmo.util.Angle for the head, a ratio for the lift)
and return an action object that reports is_completed, like the upstream does (action.py:337).  No engine, no
network and no robot is involved; the loop the hardware backend would run is not needed because the fake
applies a command at once.

The values here are test data, not facts about a robot: they are marked ``# placeholder`` and never copied
into a Fact, a Limit or the reference.  The lift height follows the ratio because the upstream SetLiftHeight
converts it that way (robot.py:501), but with placeholder millimetre values.
"""

import math

# The placeholder millimetre range the fake's ratio is mapped onto (test data only).
_PLACEHOLDER_MIN_HEIGHT_MM = 32.0
_PLACEHOLDER_MAX_HEIGHT_MM = 92.0


class _Angle:
    """The little of cozmo.util.Angle (src/cozmo/util.py:91-172) the driver uses: construct with radians, read them."""

    def __init__(self, radians=None, degrees=None):
        if radians is None and degrees is None:
            raise ValueError("Expected either the degrees or radians keyword argument")
        if degrees is not None:
            radians = float(degrees) * math.pi / 180.0
        self._radians = float(radians)

    @property
    def radians(self):
        return self._radians

    @property
    def degrees(self):
        return self._radians / math.pi * 180.0

    def __lt__(self, other):
        return self._radians < other.radians

    def __gt__(self, other):
        return self._radians > other.radians


class _Distance:
    """The little of cozmo.util.Distance (src/cozmo/util.py:191-250) the driver uses: read millimetres."""

    def __init__(self, distance_mm):
        self._distance_mm = float(distance_mm)

    @property
    def distance_mm(self):
        return self._distance_mm


class _Action:
    """A robot action object: the fake applies every command at once, so it is already complete (action.py:337)."""

    def __init__(self):
        self._completed = True

    @property
    def is_completed(self):
        return self._completed


class FakeCozmoRobot:
    """An in-memory Robot: five reads, a head command, a lift command and the native stop."""

    def __init__(self, **_options):
        self._head_angle_rad = 0.0                    # placeholder: head centred
        self._lift_ratio = 0.0                        # placeholder: lift at the bottom
        self._is_charging = False                     # placeholder
        self._is_cliff_detected = False               # placeholder
        self._stop_calls = 0                          # placeholder counter: the native stop is observable

    # -- what the robot reports -------------------------------------------------------------------------------
    @property
    def head_angle(self):
        return _Angle(radians=self._head_angle_rad)

    @property
    def lift_ratio(self):
        return self._lift_ratio

    @property
    def lift_height(self):
        span = _PLACEHOLDER_MAX_HEIGHT_MM - _PLACEHOLDER_MIN_HEIGHT_MM
        return _Distance(_PLACEHOLDER_MIN_HEIGHT_MM + self._lift_ratio * span)

    @property
    def is_charging(self):
        return self._is_charging

    @property
    def is_cliff_detected(self):
        return self._is_cliff_detected

    # -- what the robot is told to do ---------------------------------------------------------------------------
    def set_head_angle(self, angle, accel=10.0, max_speed=10.0, duration=0.0, warn_on_clamp=True,
                       in_parallel=False, num_retries=0):
        self._head_angle_rad = float(angle.radians)
        return _Action()

    def set_lift_height(self, height, accel=10.0, max_speed=10.0, duration=0.0, in_parallel=False,
                        num_retries=0):
        self._lift_ratio = float(height)
        return _Action()

    def stop_all_motors(self):
        self._stop_calls += 1

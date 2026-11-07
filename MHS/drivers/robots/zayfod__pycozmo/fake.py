"""Fake backend of the Cozmo driver: an in-memory stand-in for pycozmo.client:Client.

Gate G7: every public method defined here exists on pycozmo.client:Client (pycozmo/client.py:41) and keeps its
upstream parameter names and defaults: set_head_angle(angle, accel=10.0, max_speed=10.0, duration=0.0)
(pycozmo/client.py:364-368), set_lift_height(height, accel=10.0, max_speed=10.0, duration=0.0)
(pycozmo/client.py:374-378), stop_all_motors() (pycozmo/client.py:394-396), disconnect() and stop().  The attributes
the driver reads are the client's own: head_angle and lift_position hold the value objects of the clone
(util.Angle and util.Distance behind robot.LiftPosition, pycozmo/util.py:37-181, pycozmo/robot.py:109-171), and
battery_voltage, robot_picked_up and robot_moving are its plain attributes (pycozmo/client.py:77-81, 315-327).

The real client is asynchronous: a command is a packet and the state follows from the RobotState messages
(pycozmo/client.py:278-295).  The fake is synchronous: a command applies at once, so the driver's bounded wait sees
the target immediately.  The starting head angle and lift height are the ones the client starts in
(pycozmo/client.py:70-73); the battery voltage is the value the client holds before the first RobotState packet.
Nothing here talks to a device.
"""

import math

#: The head and lift state the upstream client starts in (pycozmo/client.py:70-73): the head at its minimum angle
#: (pycozmo/robot.py:34) and the lift at its minimum height (pycozmo/robot.py:39).
HEAD_MIN_RAD = math.radians(-25.0)
LIFT_MIN_HEIGHT_MM = 32.0
#: The lift travel and geometry of the clone (pycozmo/robot.py:39-46).
LIFT_MAX_HEIGHT_MM = 92.0
LIFT_ARM_LENGTH_MM = 66.0
LIFT_PIVOT_HEIGHT_MM = 45.0


class _Angle:
    """A stand-in for util.Angle (pycozmo/util.py:37-121): the angle kept in radians."""

    def __init__(self, radians=0.0, degrees=None):
        self._radians = math.radians(float(degrees)) if degrees is not None else float(radians)

    @property
    def radians(self):
        return self._radians

    @property
    def degrees(self):
        return math.degrees(self._radians)


class _Distance:
    """A stand-in for util.Distance (pycozmo/util.py:125-181): the distance kept in millimetres."""

    def __init__(self, mm=0.0):
        self._mm = float(mm)

    @property
    def mm(self):
        return self._mm

    @property
    def inches(self):
        return self._mm / 25.4


class _LiftPosition:
    """A stand-in for robot.LiftPosition (pycozmo/robot.py:109-171): the lift height and its arm angle."""

    def __init__(self, height=0.0):
        self._height = _Distance(mm=height)

    @property
    def height(self):
        return self._height

    @property
    def ratio(self):
        return (self._height.mm - LIFT_MIN_HEIGHT_MM) / (LIFT_MAX_HEIGHT_MM - LIFT_MIN_HEIGHT_MM)

    @property
    def angle(self):
        return _Angle(radians=math.asin((self._height.mm - LIFT_PIVOT_HEIGHT_MM) / LIFT_ARM_LENGTH_MM))


class FakeClient:
    def __init__(self, **_options):
        # The state the upstream client starts in (pycozmo/client.py:70-73, 77-81).
        self.head_angle = _Angle(radians=HEAD_MIN_RAD)
        self.lift_position = _LiftPosition(height=LIFT_MIN_HEIGHT_MM)
        self.battery_voltage = 0.0      # placeholder: the value the client holds before the first RobotState packet
        self.robot_picked_up = False
        self.robot_moving = False
        # Nothing here talks to a device; the commands are kept for a test that wants to look at them.
        self._commands = []

    def set_head_angle(self, angle, accel=10.0, max_speed=10.0, duration=0.0):
        del accel, max_speed, duration
        self.head_angle = _Angle(radians=float(angle))
        self._commands.append(("set_head_angle", float(angle)))

    def set_lift_height(self, height, accel=10.0, max_speed=10.0, duration=0.0):
        del accel, max_speed, duration
        self.lift_position = _LiftPosition(height=float(height))
        self._commands.append(("set_lift_height", float(height)))

    def stop_all_motors(self):
        self.robot_moving = False
        self._commands.append(("stop_all_motors", None))

    def disconnect(self):
        self._commands.append(("disconnect", None))

    def stop(self):
        self._commands.append(("stop", None))

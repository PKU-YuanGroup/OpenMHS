"""OpenMHS driver for gh.zayfod/pycozmo: the head and lift joints of a Cozmo robot over pycozmo.client:Client.

A direct Driver (decorated methods) over the upstream class pycozmo.client:Client (pycozmo/client.py:41), the
library's protocol client and high-level API.  The client is asynchronous: set_head_angle() and set_lift_height()
send one packet each and return (pycozmo/client.py:364-378), and the reported state only follows from the RobotState
packets the robot sends (pycozmo/client.py:278-295).  The joint action therefore sends both commands and then waits,
for a bounded time, until the reported joint positions reach the targets.

* reads: the head angle and the lift height in the units the protocol uses, radian and millimetre
  (docs/functions.md:150-173), the lift arm angle that follows from the reported height, the battery voltage and the
  two boolean state flags the client keeps (pycozmo/client.py:315-327);
* ``cap.motion.joint_position.v1``: the two joints of the robot, joint 1 the head and joint 2 the lift arm, in rad.
  The clone states the head travel as -25 to 44.5 degrees (pycozmo/robot.py:33-36) and the lift travel as a height of
  32 to 92 mm (pycozmo/robot.py:38-41); the arm angle of a lift height follows from the arm length and the pivot
  height (pycozmo/robot.py:43-51, 146-171);
* the native stop is Client.stop_all_motors (pycozmo/client.py:394-396), the message the clone documents as stopping
  the head and lift motors (docs/functions.md:156, 175).

Not exposed: the wheel motors, the lights, the display, the speaker, the camera stream, the animations, the
procedural face and the behaviours of the client.  The hardware backend (native.py) was never run: the package is
checked on the fake backend only.  Every Fact cites a line of the clone at the pinned commit
1b6dcd9b869a3784f1d8b02e820bb033f95fd13a.  This package is model-authored and unreviewed (driver.lock.json
reviewed_by is null), so nothing here ran on a robot.
"""

import math
import time

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read

#: Joint order of cap.motion.joint_position.v1 for this device.
JOINT_NAMES = ["head", "lift"]

#: Head travel, -25 to 44.5 degrees (pycozmo/robot.py:33-36), in the radian the class requires.
HEAD_MIN_RAD = math.radians(-25.0)
HEAD_MAX_RAD = math.radians(44.5)
#: Lift geometry: the arm is 66.0 mm long and its pivot point 45.0 mm above the ground (pycozmo/robot.py:43-46).
LIFT_ARM_LENGTH_MM = 66.0
LIFT_PIVOT_HEIGHT_MM = 45.0
#: Lift travel as the heights 32.0 mm to 92.0 mm (pycozmo/robot.py:38-41), in the arm angle the class requires:
#: asin((height - pivot) / arm length) (pycozmo/robot.py:48-51).
LIFT_MIN_RAD = math.asin((32.0 - LIFT_PIVOT_HEIGHT_MM) / LIFT_ARM_LENGTH_MM)
LIFT_MAX_RAD = math.asin((92.0 - LIFT_PIVOT_HEIGHT_MM) / LIFT_ARM_LENGTH_MM)

#: How long the joint action waits for the reported state, in seconds: the client has no motion-complete callback a
#: driver package could use without importing the clone's event classes, and a two-joint move takes the 2000 ms the
#: catalogue class states as typical (cap.motion.joint_position.v1 typical_duration_ms).
MOVE_WAIT_S = 2.0
#: The tolerance within which the reported joint positions count as reached, in radian.
REACH_TOLERANCE_RAD = 0.02


def _lift_height_mm(angle_rad):
    """The lift height of an arm angle: sin(angle) * arm length + pivot height (pycozmo/robot.py:146-150)."""
    return math.sin(float(angle_rad)) * LIFT_ARM_LENGTH_MM + LIFT_PIVOT_HEIGHT_MM


class Cozmo(Driver):
    device_id = "cozmo"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R1"
    native = "pycozmo.client:Client"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeClient"}
    vendor, model = "Digital Dream Labs", "Cozmo robot"
    display_name = "Digital Dream Labs Cozmo (pycozmo.Client)"
    tags = ["robot", "cozmo", "head", "lift", "joint control", "pycozmo"]
    facts = [
        Fact("Client is the protocol client and high-level API class of the library", source="upstream_code",
             ref="pycozmo/client.py:41"),
        Fact("The client starts with the head at its minimum angle and the lift at its minimum height",
             source="upstream_code", ref="pycozmo/client.py:70-73"),
        Fact("RobotState packets update the reported pose, head angle, wheel speeds, lift position, battery voltage, "
             "acceleration, gyro and status", source="upstream_code", ref="pycozmo/client.py:278-295"),
        Fact("robot_picked_up and robot_moving follow the picked-up and wheels-moving events the client handles",
             source="upstream_code", ref="pycozmo/client.py:315-327"),
        Fact("set_head_angle sends a SetHeadAngle packet with the angle in radians", source="upstream_code",
             ref="pycozmo/client.py:364-368"),
        Fact("set_lift_height sends a SetLiftHeight packet with the height in millimetres", source="upstream_code",
             ref="pycozmo/client.py:374-378"),
        Fact("stop_all_motors sends a StopAllMotors packet", source="upstream_code", ref="pycozmo/client.py:394-396"),
        Fact("The minimum head angle is -25 degrees and the maximum is 44.5 degrees", source="upstream_code",
             ref="pycozmo/robot.py:33-36"),
        Fact("The minimum lift height is 32.0 mm and the maximum is 92.0 mm", source="upstream_code",
             ref="pycozmo/robot.py:38-41"),
        Fact("The lift arm is 66.0 mm long and its pivot point is 45.0 mm above the ground", source="upstream_code",
             ref="pycozmo/robot.py:43-46"),
        Fact("The minimum and maximum lift arm angles are asin((height - pivot) / arm length) of the minimum and "
             "maximum heights", source="upstream_code", ref="pycozmo/robot.py:48-51"),
        Fact("LiftPosition builds a height from an arm angle as sin(angle) * arm length + pivot height and reports "
             "the angle of a height back", source="upstream_code", ref="pycozmo/robot.py:146-171"),
        Fact("The head is controlled with the DriveHead and SetHeadAngle messages and its angle is read from the "
             "head_angle_rad field of RobotState, whose head_in_pos status flag says whether it is in position",
             source="vendor_doc", ref="docs/functions.md:150-154"),
        Fact("The lift is controlled with the DriveLift and SetLiftHeight messages and its height is read from the "
             "lift_height_mm field of RobotState, whose lift_inpos status flag says whether it is in position",
             source="vendor_doc", ref="docs/functions.md:169-173"),
        Fact("The head motor is stopped with the StopAllMotors message", source="vendor_doc",
             ref="docs/functions.md:156"),
        Fact("The README connects a robot with Client(), start(), connect() and wait_for_robot(), and disconnects "
             "and stops it afterwards", source="vendor_doc", ref="README.md:35-43"),
        Fact("The README warns that the project is a tool for exploring the robot, unstable and heavily under "
             "development", source="vendor_doc", ref="README.md:12-13"),
    ]
    safe_state = "all motors stopped: the head and the lift hold and the wheels stop (Client.stop_all_motors)"

    # -- reads -----------------------------------------------------------------------------------------------------
    @read("head_angle", unit="rad",
          description="Angle of the head relative to its lowest position, as the robot reports it")
    def head_angle(self):
        return float(self.native.head_angle.radians)

    @read("lift_height", unit="mm", description="Height of the lift above the ground, as the robot reports it")
    def lift_height(self):
        return float(self.native.lift_position.height.mm)

    @read("lift_angle", unit="rad",
          description="Angle of the lift arm relative to the ground, computed from the reported lift height")
    def lift_angle(self):
        return float(self.native.lift_position.angle.radians)

    @read("battery_voltage", unit="V", description="Battery voltage as the robot reports it")
    def battery_voltage(self):
        return float(self.native.battery_voltage)

    @read("is_picked_up", type="boolean", description="True while the robot reports that it is picked up")
    def is_picked_up(self):
        return bool(self.native.robot_picked_up)

    @read("is_moving", type="boolean", description="True while the robot reports that its wheels are moving")
    def is_moving(self):
        return bool(self.native.robot_moving)

    # -- motion ----------------------------------------------------------------------------------------------------
    @action(cap="cap.motion.joint_position.v1",
            description="Move the head and the lift joint to target angles (joint 1 the head, joint 2 the lift arm) "
                        "and wait a bounded time for the robot to report them reached",
            input={"joint_positions": Field(
                unit="rad", length=2,
                description="Target angles of the two joints in rad: the head angle and the lift arm angle",
                limit=Limit.operator_required(
                    "the head travels -25 to 44.5 degrees (pycozmo/robot.py:33-36), but the lift range is a height, "
                    "32 to 92 mm (pycozmo/robot.py:38-41), whose arm angle follows from the lift geometry "
                    "(pycozmo/robot.py:48-51) and is shown on no line: the site states both ranges in rad "
                    "(site-limits.example.json carries the converted values)"))})
    def move_joints(self, joint_positions):
        head, lift = float(joint_positions[0]), float(joint_positions[1])
        self.native.set_head_angle(head)
        self.native.set_lift_height(_lift_height_mm(lift))
        reached = self._wait_until_reached(head, lift)
        return {"reached": reached, "joint_positions": [self._head_rad(), self._lift_rad()]}

    # -- safety ----------------------------------------------------------------------------------------------------
    @estop(native="stop_all_motors")
    def stop(self):
        """The native stop: the runtime latches first, then StopAllMotors stops every motor."""
        self.native.stop_all_motors()

    def teardown(self):
        self.native.disconnect()
        self.native.stop()

    # -- helpers ---------------------------------------------------------------------------------------------------
    def _head_rad(self):
        return float(self.native.head_angle.radians)

    def _lift_rad(self):
        return float(self.native.lift_position.angle.radians)

    def _wait_until_reached(self, head, lift):
        """Wait up to MOVE_WAIT_S for the reported joints to reach the targets; False when it ends first."""
        deadline = time.monotonic() + MOVE_WAIT_S
        while True:
            if (abs(self._head_rad() - head) <= REACH_TOLERANCE_RAD
                    and abs(self._lift_rad() - lift) <= REACH_TOLERANCE_RAD):
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.02)

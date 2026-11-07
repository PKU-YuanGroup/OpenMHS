"""OpenMHS driver for gh.anki/cozmo-python-sdk: the Anki Cozmo robot over cozmo.robot:Robot.

A direct Driver over the upstream class.  The SDK is built on asyncio: the Robot object is fed by the engine
messages on its own event loop (native.py starts that loop), and every command returns an action object that
can be asked whether it has completed (``SetHeadAngle``, ``SetLiftHeight``, robot.py:449-521, action.py:453-462).
The driver methods are plain ``def`` and poll ``action.is_completed`` (a plain property, no cross-loop await),
so they also work from the bridge's request thread; ``_wait_completed`` bounds that wait and reports
``OutcomeUnknown`` when it expires, because the robot may still be moving.

* reads: the head angle in radians, the lift ratio, the lift height in millimetres, the charging state and the
  cliff detection;
* ``cap.motion.joint_position.v1``: the head joint to an angle in radians.  The range is MIN_HEAD_ANGLE to
  MAX_HEAD_ANGLE (robot.py:98-102), written in degrees (``util.degrees(-25)``, ``util.degrees(44.5)``); the
  ``Limit`` holds the radian equivalents;
* an extension action sets the lift ratio (the SDK's ``set_lift_height`` takes a ratio from 0.0 to 1.0,
  robot.py:1552-1554).  No catalogue class drives a lift by ratio, so the package uses an extension id;
* an extension action stops every motor (the native ``stop_all_motors``), and so does the e-stop.
  ``cap.motion.stop.v1`` is not bound: it declares a deceleration profile, and the robot stop has
  no deceleration parameter.

Cozmo's wheels are not driven by this package (the SDK's drive/turn actions are not exposed); head and lift are
the two joints it controls.  This package is model-authored and unreviewed: it is checked on the fake backend
only, and nothing here ran on a robot.  The pinned commit is dd29edef18748fcd816550469195323842a7872e.
"""

import math
import time

from mhs.driver import Driver, Fact, Field, Limit, OutcomeUnknown, action, estop, read

ROBOT = "src/cozmo/robot.py"
ROBOT_ACTION = "src/cozmo/action.py"

#: The head range MIN_HEAD_ANGLE..MAX_HEAD_ANGLE (robot.py:99, 102) in radians; the SDK writes them as
#: util.degrees(-25) and util.degrees(44.5).
HEAD_MIN_RAD = math.radians(-25.0)
HEAD_MAX_RAD = math.radians(44.5)
#: How long a driver-side wait for the robot's own action object may take.  This is a client-side bound, not a
#: device limit: a move that has not finished by then is reported as an unknown outcome, never as reached.
WAIT_TIMEOUT_S = 10.0
POLL_S = 0.01


class Cozmo(Driver):
    device_id = "cozmo"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R1"
    native = "cozmo.robot:Robot"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeCozmoRobot"}
    vendor, model = "Anki", "Cozmo"
    display_name = "Anki Cozmo robot (cozmo.robot.Robot)"
    tags = ["robot", "cozmo", "anki", "head", "lift", "mobile robot"]
    facts = [
        Fact("The head can be set from MIN_HEAD_ANGLE (util.degrees(-25)) to MAX_HEAD_ANGLE "
             "(util.degrees(44.5))", source="upstream_code", ref=f"{ROBOT}:98-102"),
        Fact("SetHeadAngle clamps a head target to MIN_HEAD_ANGLE..MAX_HEAD_ANGLE and logs a warning",
             source="upstream_code", ref=f"{ROBOT}:456-463"),
        Fact("The head angle is received from the robot in radians and stored as a util.Angle",
             source="upstream_code", ref=f"{ROBOT}:1160"),
        Fact("set_head_angle returns a SetHeadAngle action object that can be queried to see when it is complete",
             source="upstream_code", ref=f"{ROBOT}:1515-1546"),
        Fact("set_lift_height takes a ratio from 0.0 (bottom) to 1.0 (top) and clamps it to that range",
             source="upstream_code", ref=f"{ROBOT}:494-501"),
        Fact("SetLiftHeight converts the ratio to millimetres between MIN_LIFT_HEIGHT_MM and MAX_LIFT_HEIGHT_MM",
             source="upstream_code", ref=f"{ROBOT}:501"),
        Fact("The lift height is reported in millimetres and the lift ratio from 0.0 to 1.0",
             source="upstream_code", ref=f"{ROBOT}:1033-1044"),
        Fact("stop_all_motors tells the robot to stop all motors", source="upstream_code",
             ref=f"{ROBOT}:1371-1374"),
        Fact("An action can be polled with is_completed and awaited with wait_for_completed(timeout)",
             source="upstream_code", ref=f"{ROBOT_ACTION}:337-345"),
    ]
    safe_state = "all motors stopped (the native stop_all_motors); the robot holds its last pose"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("head_angle", unit="rad", description="Head angle in radians (up and down)")
    def head_angle(self):
        return self.native.head_angle.radians

    @read("lift_ratio", unit="1", description="Lift position as a ratio from 0.0 (bottom) to 1.0 (top)")
    def lift_ratio(self):
        return self.native.lift_ratio

    @read("lift_height", unit="mm", description="Height of the lift above the ground in millimetres")
    def lift_height(self):
        return self.native.lift_height.distance_mm

    @read("is_charging", type="boolean", description="True while the robot is on its charger and charging")
    def is_charging(self):
        return self.native.is_charging

    @read("cliff_detected", type="boolean", description="True while the robot detects a cliff under it")
    def cliff_detected(self):
        return self.native.is_cliff_detected

    # -- actions ----------------------------------------------------------------------------------------------
    @action(cap="cap.motion.joint_position.v1",
            description="Move the head joint to an angle in radians and wait until the robot reports it complete",
            input={"joint_positions": Field(
                unit="rad", length=1, description="Target angle of the head joint, in radians (one joint: head)",
                limit=Limit(min=[HEAD_MIN_RAD], max=[HEAD_MAX_RAD], names=["head"], source="upstream_code",
                            ref=f"{ROBOT}:98-102",
                            reason="MIN_HEAD_ANGLE and MAX_HEAD_ANGLE are the head range; the SDK writes them as "
                                   "util.degrees(-25) and util.degrees(44.5) and this holds the radian values"))})
    def move_head(self, joint_positions):
        target = float(joint_positions[0])
        action_object = self.native.set_head_angle(type(self.native.head_angle)(radians=target))
        self._wait_completed(action_object, "head move")
        return {"reached": True, "joint_positions": [self.native.head_angle.radians]}

    @action(name="x-cap.anki.set_lift_ratio.v1",
            description="Move the lift to a ratio between 0.0 (bottom) and 1.0 (top) and wait until it is there",
            input={"lift_ratio": Field(
                "number", unit="1", description="Lift position as a ratio from 0.0 (bottom) to 1.0 (top)",
                limit=Limit(min=0.0, max=1.0, source="upstream_code", ref=f"{ROBOT}:494-499",
                            reason="SetLiftHeight clamps the ratio to the 0.0..1.0 the method documents"))},
            output={"lift_ratio": Field("number", unit="1", description="Lift ratio reported after the move"),
                    "lift_height": Field("number", unit="mm", description="Lift height in mm reported after the move")})
    def set_lift_ratio(self, lift_ratio):
        action_object = self.native.set_lift_height(float(lift_ratio))
        self._wait_completed(action_object, "lift move")
        return {"lift_ratio": self.native.lift_ratio, "lift_height": self.native.lift_height.distance_mm}

    @action(name="x-cap.anki.stop_all_motors.v1",
            description="Stop every motor of the robot at once (the native stop_all_motors); it takes no input",
            output={"stopped": Field("boolean", description="True once the robot was told to stop every motor")})
    def stop_all(self):
        self.native.stop_all_motors()
        return {"stopped": True}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop(native="stop_all_motors")
    def stop(self):
        """The native stop: the runtime latches first, then every motor is told to stop."""
        self.native.stop_all_motors()

    # -- helpers ----------------------------------------------------------------------------------------------
    def _wait_completed(self, action_object, what):
        """Wait (bounded) for the robot's own action object; a move past the bound has an unknown outcome."""
        deadline = time.monotonic() + WAIT_TIMEOUT_S
        while not action_object.is_completed:
            self.check_cancelled()
            if time.monotonic() >= deadline:
                raise OutcomeUnknown(f"the {what} did not report completion within {WAIT_TIMEOUT_S:g} s; the "
                                     f"robot may still be moving")
            time.sleep(POLL_S)

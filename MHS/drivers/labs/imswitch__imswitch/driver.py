"""OpenMHS driver for gh.imswitch/imswitch: the Standa rotation mount used by ImSwitch.

ImSwitch is a microscope-control application; this package implements one device of it, the first confirmed device
class of the card: the Standa motor controller for a motorized rotation mount
(imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:5-8).  The other entry symbols of the card are not
one device: ViewSetupInfo is the setup/configuration dataclass, HyphaController is the application controller that
publishes a microscope over Hypha, IC_Camera is one camera interface, and SmarACTPositionerManager is another
positioner.  The playbook asks for one device class per repository; the remaining symbols are named in facts.md.

The upstream class StandaMotor talks to the controller through the libximc wrapper: it converts an angle in degrees
to steps and microsteps (imswitch/imcontrol/model/interfaces/standamotor.py:108-122) and sends command_move,
command_movr, command_sstp and the query commands of the library.  This is a direct Driver over that class with a
native.py factory because the constructor needs the libximc directory, the controller index and the two step counts
(standamotor.py:18-24), and because the stop is a native command of the controller.

* read: the rotation angle in degrees (get_pos waits for the motor to stop, standamotor.py:85-90);
* action cap.motion.joint_position.v1: one joint, target in rad, converted once to the device's degrees; the native
  move is command_move (moveabs, standamotor.py:97-100), followed by the controller's wait-for-stop (standamotor.py:
  102-103) and a read-back;
* action cap.motion.stop.v1: the native stop command_sstp (stop_cont_rot, standamotor.py:149-150);
* the same native stop is the e-stop;
* no text file of the clone states the travel range of the mount.  The conversion in standamotor.py:108-122 accepts
  any angle, and the range depends on the mounted stage, so the joint input is Limit.operator_required: every move is
  refused MHS.SAFETY.LIMITS_UNSET until the site supplies the axis envelope (site-limits.example.json is an example,
  not a statement about a unit).

This package is model-authored and unreviewed.  It is R1, so the loader does not refuse the hardware backend on
review grounds; nothing here ran on hardware and the hardware backend was never executed.  The pinned commit is
37bf1df6de0ee4746b05bef9684c782e4995b2e8.
"""

import math
import time

from mhs.driver import Cancelled, Driver, Fact, Field, Limit, OutcomeUnknown, action, estop, read

#: The driver's reach criterion for the read-back, not a device specification: the controller reports a position
#: after command_wait_for_stop returns, and the class asks whether the target was reached within a tolerance.
POSITION_TOLERANCE_DEG = 0.01

#: The travel of this rotation mount is not stated in the clone; the site supplies the envelope.
TRAVEL_REASON = ("no line of the clone states the travel range of the rotation mount: dist_translate maps any angle "
                 "to steps and microsteps (imswitch/imcontrol/model/interfaces/standamotor.py:108-122) and the range "
                 "depends on the mounted stage; the site declares the axis envelope")


class ImSwitchStandaRotator(Driver):
    device_id = "standa-rotator"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "imswitch.imcontrol.model.interfaces.standamotor:StandaMotor"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeStandaMotor"}
    vendor, model = "Standa", "8SMC5 rotation mount controller"
    display_name = "Standa rotation mount via ImSwitch (StandaMotor)"
    tags = ["rotation mount", "standa", "libximc", "motion", "imswitch"]
    facts = [
        Fact("StandaRotatorManager drives a Standa-branded motor controller, for example an 8SMC5 for a motorized "
             "rotation mount", source="upstream_code",
             ref="imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:5-8"),
        Fact("The rotator's absolute position is in degrees", source="upstream_code",
             ref="imswitch/imcontrol/controller/controllers/RotatorController.py:57-63"),
        Fact("A relative rotator step is in degrees", source="upstream_code",
             ref="imswitch/imcontrol/controller/controllers/RotatorController.py:52"),
        Fact("The rotator widget displays the position in deg and the speed in mrpm", source="upstream_code",
             ref="imswitch/imcontrol/view/widgets/RotatorWidget.py:27-34"),
        Fact("The speed the rotator widget passes on is in mrpm", source="upstream_code",
             ref="imswitch/imcontrol/view/widgets/RotatorWidget.py:93-95"),
        Fact("StandaMotor is constructed with the controller device id, the libximc directory, steps_per_turn and "
             "microsteps_per_step", source="upstream_code",
             ref="imswitch/imcontrol/model/interfaces/standamotor.py:18-24"),
        Fact("The upstream manager reads motorListIndex, ximcLibLocation, stepsPerTurn and microstepsPerStep from "
             "the setup and passes them to StandaMotor", source="upstream_code",
             ref="imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:15-20"),
        Fact("The upstream class opens the controller through libximc and sets the default sync-in and sync-out "
             "settings after opening it", source="upstream_code",
             ref="imswitch/imcontrol/model/interfaces/standamotor.py:25-50"),
        Fact("close closes the libximc device", source="upstream_code",
             ref="imswitch/imcontrol/model/interfaces/standamotor.py:52-54"),
        Fact("get_pos waits for the motor to stop and returns the angle in degrees from the controller's step and "
             "microstep position", source="upstream_code",
             ref="imswitch/imcontrol/model/interfaces/standamotor.py:85-90"),
        Fact("dist_translate_inv converts steps and microsteps to degrees with steps_per_turn and "
             "microsteps_per_step", source="upstream_code",
             ref="imswitch/imcontrol/model/interfaces/standamotor.py:120-122"),
        Fact("moveabs and moverel convert an angle in degrees to steps and microsteps and send command_move or "
             "command_movr", source="upstream_code",
             ref="imswitch/imcontrol/model/interfaces/standamotor.py:92-100"),
        Fact("wait_for_stop sends command_wait_for_stop with an interval", source="upstream_code",
             ref="imswitch/imcontrol/model/interfaces/standamotor.py:102-103"),
        Fact("stop_cont_rot sends command_sstp and start_cont_rot sends command_right", source="upstream_code",
             ref="imswitch/imcontrol/model/interfaces/standamotor.py:146-150"),
    ]
    safe_state = "rotation stopped (the controller's stop command, command_sstp)"

    # -- read ---------------------------------------------------------------------------------------------------
    @read("position", unit="deg", description="Rotation angle of the mount in degrees, as the controller reports it")
    def position(self):
        return float(self.native.get_pos())

    # -- motion -------------------------------------------------------------------------------------------------
    @action(cap="cap.motion.joint_position.v1", long_running=True, cancellable=True, max_duration_ms=120000,
            description="Move the rotation mount to an absolute angle and report the angle the controller reports "
                        "after the motor stopped",
            input={"joint_positions": Field(
                "array", items="number", length=1, unit="rad",
                description="Target angle of the single rotation axis, in radians",
                limit=Limit.operator_required(TRAVEL_REASON))})
    def move_absolute(self, joint_positions):
        target_deg = math.degrees(float(joint_positions[0]))
        started = time.monotonic()
        # moveabs commands the controller and returns; a failure here means the command was not accepted.
        self.native.moveabs(target_deg)
        try:
            self.check_cancelled()
            measured_deg = float(self.native.get_pos())
            self.check_cancelled()
        except Cancelled:
            # The move was commanded; stop the axis before the cancellation is reported.
            self.native.stop_cont_rot()
            raise
        except BaseException as exc:  # noqa: BLE001 - the command is out, the position is not known
            raise OutcomeUnknown(f"moveabs({target_deg} deg) was commanded but the read-back failed: {exc}") from None
        return {"reached": abs(measured_deg - target_deg) <= POSITION_TOLERANCE_DEG,
                "joint_positions": [math.radians(measured_deg)],
                "tolerance_rad": math.radians(POSITION_TOLERANCE_DEG),
                "duration_ms": int((time.monotonic() - started) * 1000)}

    @action(cap="cap.motion.stop.v1",
            description="Stop the rotation mount with the controller's stop command (command_sstp)",
            input={"deceleration": Field(
                unit="m/s2", description="Accepted for the class only: the controller's stop command takes no "
                                         "deceleration argument and stops with its own profile")})
    def stop_motion(self, deceleration=None):
        self.native.stop_cont_rot()
        return {"stopped": True}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop(native="stop_cont_rot")
    def stop_rotation(self):
        """The native stop: command_sstp, sent without waiting for the motor."""
        self.native.stop_cont_rot()

    # -- lifecycle ----------------------------------------------------------------------------------------------
    def teardown(self):
        self.native.close()

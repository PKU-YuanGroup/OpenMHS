"""OpenMHS driver for gh.imswitch2/imswitch2: the Standa rotation mount manager.

ImSwitch2 is a microscope-control application.  This package implements one device of it: the Standa motor
controller for a motorized rotation mount,
``imswitch.imcontrol.model.managers.rotators.StandaRotatorManager:StandaRotatorManager``.  The other entry symbols
of the card belong to other parts of the application (a NI-DAQ manager, a recording manager and two Cobolt laser
interfaces); they are named in facts.md and are not part of this package.

The upstream manager owns a StandaMotor object and exposes the mount through ``get_pos``, ``move_abs``,
``move_rel``, ``set_zero_pos``, ``set_rot_speed``, ``start_cont_rot``, ``stop_cont_rot`` and ``close``
(imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:29-54, 68-69).  The manager passes the angle
in degrees to the motor's ``moveabs``/``moverel`` (StandaRotatorManager.py:32-38), and StandaMotor translates the
angle to steps and microsteps without a range check (imswitch/imcontrol/model/interfaces/standamotor.py:129-143).
The position property of the manager's base class returns the degrees the motor reported
(RotatorManager.py:27-30, StandaRotatorManager.py:29-30).

This is a direct Driver with a native.py factory, not the card's PythonObjectDriver helper: the absolute move needs
a rad-to-degrees conversion before the native call and a read-back after it (the manager's move_abs blocks in the
motor's wait-for-stop), and the stop is a native controller command.  A command table cannot express that.

Capabilities:

* read ``position`` in degrees, refreshed from the controller;
* ``cap.motion.joint_position.v1``: one joint, target in rad, converted once to the device's degrees, then the
  manager's blocking move and a read-back; the travel range is not stated anywhere in the clone, so the joint
  input is ``Limit.operator_required`` and every move is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site
  supplies the axis envelope (site-limits.example.json is an example, not a statement about a unit);
* ``cap.motion.stop.v1``: the native stop command, ``stop_cont_rot``;
* the same native stop is the e-stop.

Every Fact cites a line of the clone at the pinned commit.  The package is model-authored and unreviewed.  It is
R1, so the loader does not refuse the hardware backend on review grounds; the hardware backend was never executed
and no hardware run is claimed.
"""

import math
import time

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read

#: The driver's reach criterion for the read-back, not a device specification: the controller reports a position
#: after the motor stops, and this class asks whether the target was reached within a tolerance.
POSITION_TOLERANCE_DEG = 0.01

#: The travel of this rotation mount is not stated in the clone; the site supplies the envelope.
TRAVEL_REASON = ("no text file of the clone states the travel range of the rotation mount: dist_translate maps any "
                 "angle in degrees to steps and microsteps (imswitch/imcontrol/model/interfaces/standamotor.py:"
                 "129-140), the documentation defines stepsPerTurn only as the resolution of one turn "
                 "(docs/devices/rotators.rst:77-82), and the range depends on the mounted stage; the site declares "
                 "the axis envelope")


class ImSwitch2StandaRotator(Driver):
    device_id = "imswitch2-rotator"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "imswitch.imcontrol.model.managers.rotators.StandaRotatorManager:StandaRotatorManager"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeStandaRotator"}
    vendor, model = "Standa", "8SMC5 rotation mount controller via ImSwitch2"
    display_name = "ImSwitch2 Standa rotation mount"
    tags = ["rotation mount", "standa", "8smc5", "libximc", "motion", "imswitch2"]
    facts = [
        Fact("StandaRotatorManager drives a Standa-branded motor controller, for example 8SMC5 for a motorized "
             "rotation mount", source="upstream_code",
             ref="imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:5-8"),
        Fact("The manager reads motorListIndex, ximcLibLocation, stepsPerTurn and microstepsPerStep from the "
             "rotator setup and constructs a StandaMotor with them", source="upstream_code",
             ref="imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:15-20"),
        Fact("The manager's get_pos stores the value the motor reports in _position", source="upstream_code",
             ref="imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:29-30"),
        Fact("The position property returns the manager's _position field", source="upstream_code",
             ref="imswitch/imcontrol/model/managers/rotators/RotatorManager.py:27-30"),
        Fact("The manager's move_abs passes its argument to the motor's moveabs and refreshes the position",
             source="upstream_code",
             ref="imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:36-38"),
        Fact("The manager's move_rel passes its argument to the motor's moverel and refreshes the position",
             source="upstream_code",
             ref="imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:32-34"),
        Fact("The manager's set_zero_pos calls the motor's set_zero_pos and refreshes the position",
             source="upstream_code",
             ref="imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:40-42"),
        Fact("The manager's stop_cont_rot calls the motor's stop_cont_rot", source="upstream_code",
             ref="imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:50-51"),
        Fact("StandaMotor.stop_cont_rot sends command_sstp", source="upstream_code",
             ref="imswitch/imcontrol/model/interfaces/standamotor.py:170-171"),
        Fact("The widget documents the absolute position and the relative step of the rotation mount in degrees",
             source="upstream_code", ref="imswitch/imcontrol/view/widgets/RotatorWidget.py:80-91"),
        Fact("The widget displays the rotation position in deg", source="upstream_code",
             ref="imswitch/imcontrol/view/widgets/RotatorWidget.py:104-105"),
        Fact("StandaMotor.dist_translate converts an angle in degrees to steps and microsteps, and "
             "dist_translate_inv converts a reported step position back to degrees", source="upstream_code",
             ref="imswitch/imcontrol/model/interfaces/standamotor.py:129-143"),
        Fact("The documentation defines stepsPerTurn as the full motor steps per 360 degrees and "
             "microstepsPerStep as the microstep subdivision", source="vendor_doc",
             ref="docs/devices/rotators.rst:77-82"),
        Fact("The manager's close calls the motor's close", source="upstream_code",
             ref="imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:68-69"),
    ]
    safe_state = "rotation stopped (the controller's stop command, command_sstp)"

    # -- read ---------------------------------------------------------------------------------------------------
    @read("position", unit="deg",
          description="Rotation angle of the mount in degrees, as the controller reports it")
    def position(self):
        self.native.get_pos()
        return float(self.native.position)

    # -- motion -------------------------------------------------------------------------------------------------
    @action(cap="cap.motion.joint_position.v1", long_running=True, cancellable=True, max_duration_ms=120000,
            description="Move the rotation mount to an absolute angle and report the angle the controller reports "
                        "after the motor stopped",
            input={"joint_positions": Field(
                "array", items="number", length=1, unit="rad",
                description="Target angle of the single rotation axis, in radians",
                limit=Limit.operator_required(TRAVEL_REASON))})
    def move_absolute(self, joint_positions):
        target_rad = float(joint_positions[0])
        target_deg = math.degrees(target_rad)
        started = time.monotonic()
        self.check_cancelled()
        # The manager's move_abs sends the move and waits for the motor to stop before it refreshes the position.
        self.native.move_abs(target_deg)
        self.check_cancelled()
        measured_deg = float(self.native.position)
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

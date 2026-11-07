"""OpenMHS driver for gh.knerlab/sim_control_software: the motorized polarizer of the SIM/AO microscope.

The repository is a microscope-control application, not a single-device package.  This package implements one of its
three confirmed entry symbols, the motorized polarizer class ``A8MRU`` (motorized_pol_v2.py:23), a rotation stage
driven through USMCDLL.dll with ctypes.  The other two entry symbols, the Andor camera wrapper ``ccd``
(pyAndor_P35_a.py:14) and the Alpao deformable-mirror wrapper ``DM`` (Lib64/asdk37.py:95), are separate devices
with their own vendor DLLs; facts.md names them and this package does not cover them.

DEVIATION FROM THE CARD: the card reads the repository as a family-config SerialDriver.  The A8MRU class opens no
serial port and writes no text command: it loads USMCDLL.dll with ctypes (motorized_pol_v2.py:20) and calls the DLL
functions USMC_Init, USMC_Start and USMC_Stop, building each argument structure in Python.  A SerialDriver command
table cannot reproduce that binary interface, so this is a direct Driver over the upstream class with a native.py
factory, as driver-authoring.md "Choosing the shape" prescribes.  Only the fake backend is checked here.

Capabilities:

* read ``position`` in degrees, from ``getCurPos`` (motorized_pol_v2.py:101-105);
* ``cap.motion.joint_position.v1``: one joint, target in rad converted once to the device's degrees, then the native
  ``MoveAbs`` (motorized_pol_v2.py:64-69) and a bounded read-back loop;
* ``cap.motion.stop.v1``: the native ``Stop`` (motorized_pol_v2.py:133-135);
* the same native ``Stop`` is the e-stop.

The travel range is not stated by any text of the clone and the class disables both trailer limit switches
(motorized_pol_v2.py:148-149), so the joint input is ``Limit.operator_required``: every move is refused
MHS.SAFETY.LIMITS_UNSET until the site supplies the axis envelope.  site-limits.example.json is an example, not a
statement about a unit.

This package is model-authored and unreviewed.  It is R1, so the loader does not refuse its hardware backend on
review grounds (that refusal is for R2 and R3 only); no hardware backend was executed and no hardware run is
claimed.  The pinned commit is 4abc7e9ddafa89bc0ab0fc8f6e25321fe676d95c.
"""

import math
import time

from mhs.driver import Cancelled, Driver, Fact, Field, Limit, OutcomeUnknown, action, estop, read

MOTOR = "motorized_pol_v2.py"
HEADER = "USMCDLL.h"

#: The driver's reach criterion for the read-back, not a device specification: the controller reports a position in
#: 0.075 degree units (motorized_pol_v2.py:33, 104), so 0.1 degree is one step plus a small margin.
POSITION_TOLERANCE_DEG = 0.1

#: How long the driver waits for the controller to report the target angle.  This is a driver policy, not a device
#: bound; the native class has no timeout of its own and MoveAbsWait can loop forever (motorized_pol_v2.py:71-79).
MOVE_TIMEOUT_S = 30.0
POLL_INTERVAL_S = 0.02

#: The class disables both trailer limit switches and accepts any angle; the range depends on the mounted stage.
TRAVEL_REASON = ("no text of the clone states the travel range of the polarizer: MoveAbs divides any angle by "
                 "degperstep and sends it to USMC_Start (motorized_pol_v2.py:64-69), getCurPos only converts the "
                 "controller's microsteps (motorized_pol_v2.py:101-105), and the initial mode disables both trailer "
                 "limit switches (motorized_pol_v2.py:148-149); the site declares the axis envelope")


class SimControlPolarizer(Driver):
    device_id = "polarizer"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "motorized_pol_v2:A8MRU"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeA8MRU"}
    display_name = "Motorized polarizer (knerlab SIM/AO microscope)"
    tags = ["motorized polarizer", "rotation stage", "usmc", "structured illumination", "motion"]
    facts = [
        Fact("The repository's motorized polarizer class is A8MRU in motorized_pol_v2.py, and the module loads "
             "USMCDLL.dll through ctypes", source="upstream_code", ref=f"{MOTOR}:20-23"),
        Fact("The module appends an external MicroSMC directory to sys.path and imports the USMC parameter "
             "structures from pol_rotator_p35.Mot_pol_params", source="upstream_code", ref=f"{MOTOR}:14-16"),
        Fact("The A8MRU constructor calls USMC_Init and writes the mode, parameters and start parameters it built",
             source="upstream_code", ref=f"{MOTOR}:25-32"),
        Fact("The initial mode sets ResetD=1 (power off and make a whole step) and disables both trailer limit "
             "switches (Tr1En and Tr2En are 0)", source="upstream_code", ref=f"{MOTOR}:139-150"),
        Fact("degperstep is 0.075 degrees per microstep", source="upstream_code", ref=f"{MOTOR}:33"),
        Fact("getCurPos converts the controller's CurPos to degrees as CurPos * (360. / 4800.)",
             source="upstream_code", ref=f"{MOTOR}:101-105"),
        Fact("MoveAbs divides the target position in degrees by degperstep and calls USMC_Start",
             source="upstream_code", ref=f"{MOTOR}:64-69"),
        Fact("MoveAbsWait polls getCurPos until the angle is within 2 degrees and has no timeout",
             source="upstream_code", ref=f"{MOTOR}:71-79"),
        Fact("MoveRel reads the state, adds the jog divided by degperstep, and calls USMC_Start",
             source="upstream_code", ref=f"{MOTOR}:81-85"),
        Fact("Stop calls USMC_Stop", source="upstream_code", ref=f"{MOTOR}:133-135"),
        Fact("The vendor header documents USMC_State.CurPos as the current position in microsteps",
             source="upstream_code", ref=f"{HEADER}:106-108"),
        Fact("The vendor header documents USMC_Stop as stopping the device", source="upstream_code",
             ref=f"{HEADER}:216-219"),
        Fact("The vendor header documents USMC_Start as taking a destination position, a speed and the start "
             "parameters", source="upstream_code", ref=f"{HEADER}:208-214"),
        Fact("The microscope application enables the motor with MotorOn after constructing A8MRU",
             source="upstream_code", ref="microscope_p35.py:67-68"),
    ]
    safe_state = "rotation stopped by the controller (A8MRU.Stop sends USMC_Stop)"

    # -- read ---------------------------------------------------------------------------------------------------
    @read("position", unit="deg", description="Polarizer angle in degrees, as the controller reports it")
    def position(self):
        return float(self.native.getCurPos())

    # -- motion -------------------------------------------------------------------------------------------------
    @action(cap="cap.motion.joint_position.v1", long_running=True, cancellable=True, max_duration_ms=60000,
            description="Move the polarizer to an absolute angle and report the angle the controller reports",
            input={"joint_positions": Field(
                "array", items="number", length=1, unit="rad",
                description="Target angle of the single polarizer axis, in radians",
                limit=Limit.operator_required(TRAVEL_REASON))})
    def move_absolute(self, joint_positions):
        target_deg = math.degrees(float(joint_positions[0]))
        started = time.monotonic()
        self.check_cancelled()
        # MoveAbs only starts the move (motorized_pol_v2.py:64-69); the read-back below waits for it, bounded.
        self.native.MoveAbs(target_deg)
        try:
            while True:
                self.check_cancelled()
                measured_deg = float(self.native.getCurPos())
                if abs(measured_deg - target_deg) <= POSITION_TOLERANCE_DEG:
                    break
                if time.monotonic() - started > MOVE_TIMEOUT_S:
                    raise OutcomeUnknown(
                        f"MoveAbs({target_deg} deg) was commanded but the controller did not report the target "
                        f"within {MOVE_TIMEOUT_S:.0f} s")
                time.sleep(POLL_INTERVAL_S)
        except Cancelled:
            # The move was commanded; stop the axis before the cancellation is reported.
            self.native.Stop()
            raise
        except OutcomeUnknown:
            raise
        except BaseException as exc:  # noqa: BLE001 - the command is out, the position is not known
            raise OutcomeUnknown(f"MoveAbs({target_deg} deg) was commanded but the read-back failed: {exc}") from None
        return {"reached": True,
                "joint_positions": [math.radians(measured_deg)],
                "tolerance_rad": math.radians(POSITION_TOLERANCE_DEG),
                "duration_ms": int((time.monotonic() - started) * 1000)}

    @action(cap="cap.motion.stop.v1",
            description="Stop the polarizer with the controller's native stop (USMC_Stop)",
            input={"deceleration": Field(
                unit="m/s2", description="Accepted for the class only: the controller's stop call takes no "
                                         "deceleration argument and stops with its own profile")})
    def stop_motion(self, deceleration=None):
        self.native.Stop()
        try:
            position_deg = float(self.native.getCurPos())
        except BaseException as exc:  # noqa: BLE001 - the stop was sent, the stopping position is not known
            raise OutcomeUnknown(f"Stop was sent but the position read-back failed: {exc}") from None
        return {"stopped": True, "stopped_position": {"position_deg": position_deg}}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop(native="Stop")
    def emergency_stop(self):
        """The native stop: USMC_Stop, sent without waiting for a running move."""
        self.native.Stop()

    # -- lifecycle ----------------------------------------------------------------------------------------------
    def teardown(self):
        self.native.close()

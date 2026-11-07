"""OpenMHS driver for gh.itheima1/mcp_robot: a six-servo robot arm over sources.servo_control_standalone:ServoControllerStandalone.

A direct Driver over the upstream class.  The upstream is not a text-command wrapper: it builds SCS (Feetech) frames
from a servo ID, a register address, an instruction and a checksum (sources/servo_control_standalone.py:369-374), and
every command is a method call with structured arguments and a bool/None result.  The card's decision is
direct-driver; the package therefore uses a direct Driver with native.py rather than the PythonObjectDriver helper.

Units.  The upstream speaks degrees and raw SCS position units; the catalogue motion classes speak radians.  The
driver converts at its edge: joint angles in rad, positions in the 0-180 degree range the servos accept (the upstream
set_servo_angle converts 0-180 degrees to the 1024-3072 position range, sources/servo_control_standalone.py:468-471).

Interface.

* read ``joint_positions``: the present angle of servos 1 to 6, from get_multiple_servo_angles (degrees converted to
  rad); a servo whose reply is missing is a fault, never a zero;
* ``cap.motion.joint_position.v1``: move servos 1 to 6 with set_multiple_servo_angles.  The native call writes the
  moving speed and then the goal position and returns only whether the write was accepted, so the driver polls the
  present positions until the target is reached or the request deadline is almost gone, and reports ``reached`` from
  that read-back;
* ``cap.motion.home.v1``: the upstream go_home pose, read back the same way; ``homed`` is whether the read-back
  matches the pose the clone lists (sources/servo_control_standalone.py:922-929);
* ``x-cap.itheima1.disable_all_torque.v1``: the safe-state action; sync_disable_torque turns the torque off on all
  six servos (sources/servo_control_standalone.py:865-900).  The clone documents no independent hardware e-stop, so
  this safe-state action is what satisfies SAFE-045 for this R2 arm;
* ``x-cap.itheima1.enable_all_torque.v1``: the declared re-enable after a safety reset (``reenable=True``,
  CORE-086); sync_enable_torque turns the torque back on (sources/servo_control_standalone.py:828-863), the call
  the upstream's own arm_tighten tool makes (sources/mcp_server.py:333-347).  The runtime refuses it while the
  e-stop is latched;
* ``@estop``: the same native torque-off call.  There is no ``@reset``: a safety reset releases the latch and
  re-arms nothing (SAFE-042); the torque stays off until the re-enable is sent.

The package is model-authored and unreviewed (driver.lock.json reviewed_by is null).  It is checked on the fake
backend only; the loader refuses the hardware backend of an unreviewed R2 package until a human signs reviewed_by.
Nothing here ran on an arm.  The pinned commit is 18f9ea5ff42c6bf01bc16d659e422c048be6d312.
"""

import math
import time

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, OutcomeUnknown, action, estop, read

CLONE = "sources/servo_control_standalone.py"
SERVO_IDS = (1, 2, 3, 4, 5, 6)
JOINT_NAMES = [f"joint{number}" for number in SERVO_IDS]
#: set_servo_angle accepts 0-180 degrees, clamps to the 1024-3072 position range (CLONE:468-471); in rad that is
#: 0..pi.  A zero bound is never warned about by G4; pi is the unit conversion of the 180 the cited lines state.
JOINT_MIN = [0.0] * len(SERVO_IDS)
JOINT_MAX = [math.pi] * len(SERVO_IDS)
#: One SCS position step: 180 degrees span 2048 position steps (CLONE:469), so a step is pi/2048 rad.  This is the
#: read-back comparison tolerance, not a device limit.
POSITION_STEP_RAD = math.pi / 2048.0
#: Poll interval and response margin: the controller's own reply timeout (CLONE:289) is 0.1 s, and the driver leaves
#: that much of the request deadline for the receipt.
POLL_INTERVAL_S = 0.1
RESPONSE_MARGIN_MS = int(POLL_INTERVAL_S * 1000)
#: Home pose of go_home in degrees, servo IDs 1 to 6 in order (CLONE:922-929).  The comment on servo 4 disagrees
#: with the value; the code writes 180 and the code is what the arm receives.
HOME_ANGLES_RAD = tuple(math.radians(angle) for angle in (90, 0, 180, 180, 90, 90))


class McpRobot(Driver):
    device_id = "mcp-robot"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    native = "sources.servo_control_standalone:ServoControllerStandalone"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeServoControllerStandalone"}
    vendor, model = "itheima1", "Bambot/SO100 six-servo arm (Feetech SCS bus)"
    display_name = "itheima1 mcp_robot six-servo arm (ServoControllerStandalone)"
    tags = ["robot arm", "six joints", "feetech", "scs", "servo bus", "joint control", "homing"]
    facts = [
        Fact("The application runs simulations and controls a Bambot and an SO100 arm", source="vendor_doc",
             ref="sources/README.md:3"),
        Fact("The application controls real robot arms with Feetech SCS servo motors whose IDs are 1 to 6",
             source="vendor_doc", ref="sources/README.md:14"),
        Fact("The servo IDs are configured from 1 to 6 matching the joint numbers, the bus runs at a fixed "
             "1,000,000 bps and the protocol is SCS (1)", source="vendor_doc", ref="sources/README.md:31-33"),
        Fact("The controller's constructor defaults are port COM4, 1,000,000 baud and a 0.1 s timeout",
             source="upstream_code", ref=f"{CLONE}:289"),
        Fact("The serial port is opened with eight data bits, no parity and one stop bit (8N1)",
             source="upstream_code", ref=f"{CLONE}:308-315"),
        Fact("Every SCS packet starts with two 0xFF bytes and carries the servo ID, the length, the instruction, its "
             "parameters and a one-byte checksum", source="upstream_code", ref=f"{CLONE}:369-374"),
        Fact("set_servo_angle accepts an angle of 0-180 degrees, converts it to the 1024-3072 position range and "
             "clamps it there", source="upstream_code", ref=f"{CLONE}:468-471"),
        Fact("A moving speed is 0-32767 and a speed of 0 means the highest speed", source="upstream_code",
             ref=f"{CLONE}:463"),
        Fact("read_position returns the present-position register value, documented as 0-4095", source="upstream_code",
             ref=f"{CLONE}:565"),
        Fact("get_servo_angle converts the 1024-3072 present position back to 0-180 degrees", source="upstream_code",
             ref=f"{CLONE}:515-516"),
        Fact("enable_torque writes 1 and disable_torque writes 0 to the torque-enable register",
             source="upstream_code", ref=f"{CLONE}:814-826"),
        Fact("sync_disable_torque writes 0 to the torque-enable register of every named servo and falls back to "
             "disable_torque one servo at a time when the sync write fails", source="upstream_code",
             ref=f"{CLONE}:878-900"),
        Fact("sync_enable_torque writes 1 to the torque-enable register of every named servo and falls back to "
             "enable_torque one servo at a time when the sync write fails", source="upstream_code",
             ref=f"{CLONE}:841-863"),
        Fact("The upstream MCP tool arm_tighten enables the torque of servos 1 to 6 with sync_enable_torque and "
             "documents that the arm then holds its current position", source="upstream_code",
             ref="sources/mcp_server.py:333-347"),
        Fact("go_home moves servos 1 to 6 to 90, 0, 180, 180, 90 and 90 degrees; the comment on servo 4 says 0 but "
             "the code writes 180", source="upstream_code", ref=f"{CLONE}:922-929"),
        Fact("read_position returns None when the command send or the reply fails", source="upstream_code",
             ref=f"{CLONE}:573-589"),
        Fact("_write_register returns False when the command send or the reply fails", source="upstream_code",
             ref=f"{CLONE}:646-666"),
    ]
    safe_state = ("torque disabled on servos 1 to 6, so the arm is limp; a reset leaves it off until the declared "
                  "re-enable x-cap.itheima1.enable_all_torque.v1 turns it back on")

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("joint_positions", type="array", items="number", length=len(SERVO_IDS), unit="rad",
          description="Present angle of servos 1 to 6, in rad (0 to pi is the upstream's 0-180 degrees)")
    def get_joint_positions(self):
        return self._read_angles()

    # -- motion --------------------------------------------------------------------------------------------------
    @action(cap="cap.motion.joint_position.v1", long_running=True, cancellable=True,
            description="Move servos 1 to 6 to the given joint angles and report whether they reached the target",
            input={"joint_positions": Field(
                unit="rad", length=len(SERVO_IDS), description="Target angle of joints 1 to 6, in rad",
                limit=Limit(min=JOINT_MIN, max=JOINT_MAX, names=JOINT_NAMES, source="upstream_code",
                            ref=f"{CLONE}:462-471",
                            reason="set_servo_angle documents its angle as 0-180 degrees (line 462) and clamps "
                                   "the converted position to 1024-3072; 0-180 degrees is 0-pi rad"))})
    def move_joints(self, joint_positions):
        angles = {servo_id: math.degrees(float(value)) for servo_id, value in zip(SERVO_IDS, joint_positions)}
        if not self.native.set_multiple_servo_angles(angles, speed=0):
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "set_multiple_servo_angles returned False: a servo did not accept the target")
        actual, reached = self._wait_for([float(value) for value in joint_positions])
        return {"reached": reached, "joint_positions": actual, "tolerance_rad": POSITION_STEP_RAD}

    @action(cap="cap.motion.home.v1", long_running=True, cancellable=True,
            description="Move servos 1 to 6 to the upstream go_home pose and report whether the pose was reached",
            input={"speed_scale": Field(
                "number", unit="1",
                description="Fraction of the upstream 0-32767 moving-speed range; omit it for go_home's default",
                limit=Limit.operator_required(
                    "the catalogue class defines only a dimensionless 0..1 fraction and the clone states no "
                    "speed-scale range for the arm; the site sets the allowed fraction"))})
    def home(self, speed_scale=None):
        if speed_scale is None:
            accepted = self.native.go_home()
        else:
            # 1.0 is the top of the 0-32767 range the upstream documents (CLONE:463,721); the class defines the
            # fraction in 0..1.
            accepted = self.native.go_home(speed=int(round(float(speed_scale) * 32767)))
        if not accepted:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "go_home returned False: a servo did not accept the home target")
        actual, homed = self._wait_for(list(HOME_ANGLES_RAD))
        return {"homed": homed, "joint_positions": actual}

    # -- safety ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.itheima1.disable_all_torque.v1", safe_state=True,
            description="Disable the torque of servos 1 to 6 (the safe state); it takes no input",
            output={"disabled": Field("boolean",
                                      description="True once the torque of all six servos was disabled")})
    def disable_all_torque(self):
        if not self.native.sync_disable_torque(list(SERVO_IDS)):
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "sync_disable_torque returned False: at least one servo did not disable its torque")
        return {"disabled": True}

    @action(name="x-cap.itheima1.enable_all_torque.v1", reenable=True,
            description="Re-enable the torque of servos 1 to 6 after a safety reset (the declared re-enable); it "
                        "takes no input, is refused while the e-stop is latched and is never run by the reset. The "
                        "upstream arm_tighten documents that the arm then holds its current position; treat it as "
                        "an actuation",
            output={"enabled": Field("boolean",
                                     description="True once the torque of all six servos was enabled")})
    def enable_all_torque(self):
        """The new start command after a reset (SAFE-042, CORE-086): sync_enable_torque (CLONE:828-863)."""
        if not self.native.sync_enable_torque(list(SERVO_IDS)):
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "sync_enable_torque returned False: at least one servo did not enable its torque")
        return {"enabled": True}

    @estop(native="sync_disable_torque")
    def stop(self):
        """The native stop: the runtime latches first, then the torque of all six servos is disabled."""
        if not self.native.sync_disable_torque(list(SERVO_IDS)):
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "the e-stop could not disable the torque of every servo")

    # No @reset: a safety reset releases the latch and re-arms nothing (SAFE-042).  The torque stays off until the
    # declared re-enable above is sent as its own command.

    def teardown(self):
        self.native.close()

    # -- helpers ---------------------------------------------------------------------------------------------------
    def _read_angles(self):
        """Read servos 1 to 6 through get_multiple_servo_angles and return their angles in rad."""
        angles = self.native.get_multiple_servo_angles(list(SERVO_IDS))
        values = []
        for servo_id in SERVO_IDS:
            angle = angles.get(servo_id)
            if angle is None:
                raise DriverFailed("MHS.DEVICE.FAULTED",
                                   f"the reply of servo {servo_id} carried no present position")
            values.append(math.radians(float(angle)))
        return values

    def _wait_for(self, targets):
        """Poll the present angles until they match ``targets`` or the request deadline is almost reached.

        The upstream commands are accepted by the bus, not confirmed by the mechanical move (CLONE:646-666), so the
        only completion signal is the present-position read-back.  A cancellation (an e-stop) ends the wait with
        Cancelled (CLONE:347-385 sends and receives on the serial port; the loop checks before every sleep).
        """
        while True:
            try:
                actual = self._read_angles()
            except DriverFailed as exc:
                raise OutcomeUnknown("the move command was accepted, but the present-position read-back failed: "
                                     "whether the servos moved is unknown") from exc
            reached = all(abs(value - target) <= POSITION_STEP_RAD for value, target in zip(actual, targets))
            if reached:
                return actual, True
            self.check_cancelled()
            remaining = self.ctx.remaining_ms() if self.ctx is not None else RESPONSE_MARGIN_MS
            if remaining <= RESPONSE_MARGIN_MS:
                return actual, False
            time.sleep(min(POLL_INTERVAL_S, (remaining - RESPONSE_MARGIN_MS) / 1000.0))

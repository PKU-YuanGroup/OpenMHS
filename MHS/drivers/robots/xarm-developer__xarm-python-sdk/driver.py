"""OpenMHS driver for gh.xarm-developer/xarm-python-sdk: a UFACTORY xArm with 7 axes over xarm.wrapper.xarm_api:XArmAPI.

A direct Driver over the upstream class.  The SDK is synchronous, so every method here is a plain ``def``, and it
reports a failure as an integer API code (0 is success, doc/api/xarm_api_code.md:15-58), so every call is checked
by ``_check_code``: a non-zero code raises ``DriverFailed`` (``OutcomeUnknown`` when the code says the effect may have
happened).  Every call passes ``is_radian=True``: the SDK's default unit is degrees (xarm_api.py:25-26).

* reads: the joint angles, the tool pose, the controller state, the control mode and the error and warning codes;
* ``cap.motion.joint_position.v1``: seven joint angles, bounded per joint by the SDK's table for robot type
  XARM7_X4 (xarm/core/config/x_config.py:129-137);
* ``cap.motion.cartesian_pose.v1``: a tool position bounded by the SDK's TCP table for that type (x_config.py
  :229-231); the orientation is ``Limit.operator_required``, because the table states only the full circle;
* ``cap.motion.joint_velocity.v1``: joint velocities for a bounded time.  The SDK states no velocity range, so both
  inputs are ``operator_required``.  The ``duration`` of such a command is the arm's own watchdog: over it the arm
  sets the speed to 0 (xarm_api.py:3298-3302), so ``watchdog_ms`` is declared (the longest ``duration_s`` the
  catalogue class accepts, 60 s) and a duration of 0 (which never stops) is refused;
* the native stop ``emergency_stop`` is the e-stop.  A safety reset only releases the latch: the driver has no
  ``@reset`` hook and sends the arm nothing (SAFE-042).  The declared re-enable
  ``x-cap.xarm-developer.enable_motion.v1`` (``reenable=True``, CORE-086) runs the whole recovery the SDK
  documents: ``clean_error`` and ``clean_warn`` (xarm_api.py:1588-1604), then ``motion_enable(True)``,
  ``set_mode(0)`` and ``set_state(0)``, which ``clean_error`` says must follow it by hand (xarm_api.py:1590) and
  which the upstream examples start with (example/wrapper/xarm7/2001-move_joint.py:44-46).

This package is model-authored and unreviewed: it is checked on the fake backend only, and the loader refuses its
hardware backend (R2) until a human signs ``reviewed_by`` (README.md).  The pinned commit is
d911319cebc45142613e18086aabb8067b18ab7f.
"""

import math

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, OutcomeUnknown, action, estop, read

X_CONFIG = "xarm/core/config/x_config.py"
API = "xarm/wrapper/xarm_api.py"
API_CODES_DOC = "doc/api/xarm_api_code.md"

JOINT_NAMES = [f"joint{number}" for number in range(1, 8)]
_TWO_PI = 2 * math.pi
#: XCONF.Robot.JOINT_LIMITS[Axis.XARM7][Type.XARM7_X4] in radians, one (min, max) pair per joint (x_config.py:129-137)
JOINT_MIN = [-_TWO_PI, -2.059488, -_TWO_PI, -0.191986, -_TWO_PI, -1.692969, -_TWO_PI]
JOINT_MAX = [_TWO_PI, 2.094395, _TWO_PI, 3.92699, _TWO_PI, math.pi, _TWO_PI]

#: The wait of a blocking move, in seconds: below the 120000 ms the catalogue class allows a joint or Cartesian move
#: (cap.motion.joint_position.v1 max_duration_ms), so the SDK gives up (API code 100) before the runtime does.
MOVE_TIMEOUT_S = 100
#: The longest ``duration_s`` of a velocity command: the maximum of cap.motion.joint_velocity.v1 (60 s).  The arm
#: stops itself that long after the last velocity command at the latest (the duration is sent to it, xarm.py:1704).
VELOCITY_WATCHDOG_MS = 60000
TCP_REASON = "SDK TCP table for the 7-axis robot type XARM7_X4 (TCP_LIMITS); the SDK itself does not enforce it"
ORIENTATION_REASON = ("the SDK table states only the full circle (-pi..pi, x_config.py:232-234); the tool orientation "
                      "envelope depends on the tool and the workspace, so the site sets it")
#: First firmware that honours the ``duration`` of a velocity command (xarm_api.py:3299, xarm/x3/xarm.py:1704)
VELOCITY_DURATION_FIRMWARE = (1, 8, 0)

#: The API codes the driver names, with the wording of doc/api/xarm_api_code.md (line numbers in the comments)
API_CODES = {
    -9: "emergency stop",                                                                # :18
    -8: "out of range",                                                                  # :19
    -7: "joint angle limit",                                                             # :20
    -6: "cartesian pos limit",                                                           # :21
    -2: "xArm is not ready, may be the motion is not enable or not set state",           # :25
    -1: "xArm is disconnect or not connect",                                             # :26
    1: "there are errors that have not been cleared",                                    # :28
    2: "there are warnings that have not been cleared",                                  # :29
    3: "get response timeout",                                                           # :30
    9: "state is not ready to move",                                                     # :36
    100: "wait finish timeout",                                                          # :52
    101: "too many consecutive failed tests",                                            # :53
}
#: The effect of the command may have happened, nothing says whether (a response or a wait timed out)
UNKNOWN_OUTCOME = frozenset({3, 100, 101})
#: The arm is not ready to move (motion not enabled, state not set, paused or stopped): fix the state, then retry
NOT_READY = frozenset({-2, 9})
#: The arm refused the target by its own limits (the SDK's checks, which the runtime's limits should make unreachable)
OWN_LIMIT = frozenset({-8, -7, -6})


class XArm7(Driver):
    device_id = "xarm7"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    native = "xarm.wrapper.xarm_api:XArmAPI"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeXArmAPI"}
    vendor, model = "UFACTORY", "xArm, 7 axes (robot type XARM7_X4)"
    display_name = "UFACTORY xArm 7 (xarm.XArmAPI)"
    tags = ["robot arm", "7-axis", "ufactory", "xarm", "joint control", "cartesian control", "velocity control"]
    facts = [
        Fact("The README warns to keep away from the robot arm to avoid personal injury or equipment damage and to "
             "make a safety assessment before moving to prevent collisions", source="vendor_doc",
             ref="README.md:8-11"),
        Fact("Robot type XARM7_X4 has the number 7", source="upstream_code", ref=f"{X_CONFIG}:41"),
        Fact("The SDK parses the axis count, the robot type and the firmware version out of the controller's version "
             "string (axis, device_type, version_number)", source="upstream_code", ref="xarm/x3/base.py:473-485"),
        Fact("The SDK picks the joint range table of an arm by its axis count and robot type, and the table numbered "
             "<axis>1305 (71305 for 7 axes) when characters 3 to 6 of the serial number are from 1305 to below 8500",
             source="upstream_code", ref="xarm/x3/xarm.py:71-72"),
        Fact("The 1305 table of the 7-axis type XARM7_X4 narrows joint 2 to -2.042035..2.024581 rad and joint 4 to "
             "-0.10472..3.92699 rad", source="upstream_code", ref=f"{X_CONFIG}:138-146"),
        Fact("The SDK's own joint range check is on by default (check_joint_limit) and covers set_servo_angle and "
             "set_servo_angle_j", source="upstream_code", ref=f"{API}:77-78"),
        Fact("The SDK's own TCP range check is off by default (check_tcp_limit) and documented to check only roll, "
             "pitch and yaw, so the position ranges of TCP_LIMITS are not checked by it", source="upstream_code",
             ref=f"{API}:75-76"),
        Fact("Every API call returns a code: 0 is success, a negative code is an SDK-side failure and a positive "
             "code comes from the controller or the protocol", source="upstream_code",
             ref=f"{API_CODES_DOC}:15-58"),
        Fact("The controller reports error 1 when its Emergency Stop Button is pushed, 2 when the Emergency IO of "
             "the Control Box is triggered and 3 when the Emergency Stop Button of the Three-state Switch is pressed",
             source="upstream_code", ref=f"{API_CODES_DOC}:68-70"),
        Fact("emergency_stop() sets state 4 (stop) and repeats it every 0.1 s for up to 3 s until the controller "
             "reports state 4", source="upstream_code", ref="xarm/x3/xarm.py:1109-1118"),
        Fact("The wrapper documents emergency_stop as set_state(4), motion_enable(True), set_state(0) and says it "
             "does not clear an error", source="upstream_code", ref=f"{API}:1897-1899"),
        Fact("set_state selects the motion state (0), pause (3), stop (4) or deceleration stop (6)",
             source="upstream_code", ref=f"{API}:1530-1534"),
        Fact("clean_error is documented to need motion enabled (motion_enable(True)) and state 0 set "
             "(set_state(state=0)) by hand after it", source="upstream_code", ref=f"{API}:1588-1595"),
        Fact("clean_warn cleans the warnings and returns an API code", source="upstream_code",
             ref=f"{API}:1597-1604"),
        Fact("motion_enable takes enable True or False and a servo_id of 1 to the number of axes, or None",
             source="upstream_code", ref=f"{API}:1606-1615"),
        Fact("The upstream xArm 7 move example enables motion, then sets mode 0 and state 0, before it moves",
             source="upstream_code", ref="example/wrapper/xarm7/2001-move_joint.py:44-46"),
        Fact("Joint velocity control needs joint velocity control mode (set_mode(4)) and, in the upstream example, "
             "set_state(0) after it", source="upstream_code",
             ref="example/wrapper/common/2000-joint_velocity_control.py:50-53"),
        Fact("Watchdog of a velocity command: over its duration (seconds) the arm sets the speed to 0 by itself "
             "(firmware 1.8.0 or newer); a duration of 0 or less never stops it", source="upstream_code",
             ref=f"{API}:3298-3302"),
        Fact("An arm with firmware older than 1.8.0 is sent -1 instead of the duration, and -1 is equivalent to 0, "
             "which never stops", source="upstream_code", ref="xarm/x3/xarm.py:1704"),
        Fact("The SDK's speed ranges for position moves are 0.1 to 1000 mm/s for the tool and 0.0001 to 4.0 rad/s for "
             "the joints", source="upstream_code", ref="xarm/x3/base.py:105-111"),
        Fact("A move that names no speed runs at the last used speed: 100 mm/s (tool) and 20 deg/s (joints) after "
             "start", source="upstream_code", ref="xarm/x3/base.py:128-131"),
    ]
    safe_state = ("arm stopped in stop state 4 (emergency_stop); an operator reset only releases the latch and "
                  "sends the arm nothing; the declared re-enable then clears errors and warnings, enables motion "
                  "and selects mode 0 and state 0")
    #: A hardware e-stop the clone documents: the controller error codes of the Emergency Stop Button, the Control Box's
    #: emergency IO and the Three-state Switch (SAFE-045 for R2 hardware; no safe-state action is needed)
    estop_physical_ref = f"{API_CODES_DOC}:68-70"
    #: A device-side watchdog the clone documents (the Fact above); see VELOCITY_WATCHDOG_MS
    watchdog_ms = VELOCITY_WATCHDOG_MS

    # -- reads (each getter returns the value; the SDK returns (code, value)) -----------------------------------
    @read("joint_positions", type="array", items="number", length=7, unit="rad",
          description="Angles of joints 1 to 7")
    def get_joint_positions(self):
        code, angles = self.native.get_servo_angle(is_radian=True)
        self._check_code(code, "get_servo_angle")
        return list(angles)

    @read("tcp_pose", type="object", description="Tool pose in the base frame: position in mm, orientation in rad",
          properties={
              "position": Field("object", properties={"x": Field("number", unit="mm"), "y": Field("number", unit="mm"),
                                                      "z": Field("number", unit="mm")}),
              "orientation": Field("object", properties={"roll": Field("number", unit="rad"),
                                                         "pitch": Field("number", unit="rad"),
                                                         "yaw": Field("number", unit="rad")}),
          })
    def get_tcp_pose(self):
        code, pose = self.native.get_position(is_radian=True)
        self._check_code(code, "get_position")
        return self._pose_of(pose)

    @read("state", type="integer",
          description="Controller state: 1 in motion, 2 sleeping, 3 suspended, 4 stopping (the SDK's list); 0 is "
                      "the motion state set_state(0) selects")
    def get_state(self):
        return self.native.state

    @read("mode", type="integer",
          description="Control mode: 0 position, 1 servo motion, 4 joint velocity, 5 Cartesian velocity (the SDK's "
                      "list; only reported over a socket connection with the report enabled)")
    def get_mode(self):
        return self.native.mode

    @read("error_code", type="integer",
          description="Controller error code, 0 when none (doc/api/xarm_api_code.md lists them; 1 to 3 are the "
                      "emergency stop inputs)")
    def get_error_code(self):
        return self.native.error_code

    @read("warn_code", type="integer", description="Controller warning code, 0 when none")
    def get_warn_code(self):
        return self.native.warn_code

    # -- motion --------------------------------------------------------------------------------------------------
    @action(cap="cap.motion.joint_position.v1", long_running=True, cancellable=True,
            description="Move the seven joints to the given angles and wait until the arm has finished the move",
            input={"joint_positions": Field(
                unit="rad", length=7, description="Target angle of joints 1 to 7, in rad",
                limit=Limit(min=JOINT_MIN, max=JOINT_MAX, names=JOINT_NAMES, source="upstream_code",
                            ref=f"{X_CONFIG}:129-137",
                            reason="SDK joint range table for the 7-axis robot type XARM7_X4 (JOINT_LIMITS)"))})
    def move_joints(self, joint_positions):
        self._select_mode(0)
        self._check_code(self.native.set_servo_angle(angle=list(joint_positions), is_radian=True, wait=True,
                                                     timeout=MOVE_TIMEOUT_S), "set_servo_angle")
        code, angles = self.native.get_servo_angle(is_radian=True)
        self._check_code(code, "get_servo_angle", after_motion=True)
        return {"reached": True, "joint_positions": list(angles)}

    @action(cap="cap.motion.cartesian_pose.v1", long_running=True, cancellable=True,
            description="Move the tool to a base-frame pose and wait until the move ends; omit orientation to keep it",
            input={
                "position": Field(description="Tool position in the base frame, mm", properties={
                    "x": Field(limit=Limit(min=-750, max=750, source="upstream_code", ref=f"{X_CONFIG}:229",
                                           reason=TCP_REASON)),
                    "y": Field(limit=Limit(min=-750, max=750, source="upstream_code", ref=f"{X_CONFIG}:230",
                                           reason=TCP_REASON)),
                    "z": Field(limit=Limit(min=-400, max=1000, source="upstream_code", ref=f"{X_CONFIG}:231",
                                           reason=TCP_REASON)),
                }),
                "orientation": Field(description="Tool orientation, rad (roll, pitch, yaw about x, y, z)", properties={
                    "roll": Field(limit=Limit.operator_required(ORIENTATION_REASON)),
                    "pitch": Field(limit=Limit.operator_required(ORIENTATION_REASON)),
                    "yaw": Field(limit=Limit.operator_required(ORIENTATION_REASON)),
                }),
            })
    def move_pose(self, position, orientation=None):
        angles = {} if orientation is None else {name: orientation[name] for name in ("roll", "pitch", "yaw")}
        self._select_mode(0)
        self._check_code(self.native.set_position(x=position["x"], y=position["y"], z=position["z"], is_radian=True,
                                                  wait=True, timeout=MOVE_TIMEOUT_S, **angles), "set_position")
        code, pose = self.native.get_position(is_radian=True)
        self._check_code(code, "get_position", after_motion=True)
        return {"reached": True, "position": self._pose_of(pose)["position"]}

    @action(cap="cap.motion.joint_velocity.v1",
            description="Command joint velocities for duration_s seconds, then the arm sets the speed to 0 by itself "
                        "(its own watchdog, firmware 1.8.0 or newer); returns when the command is accepted",
            input={
                "joint_velocities": Field(
                    unit="rad/s", length=7, description="Velocity of joints 1 to 7, in rad/s",
                    limit=Limit.operator_required(
                        "the SDK states no velocity range for velocity control mode (its 0.0001..4.0 rad/s are for "
                        "the speed of position moves, base.py:110); the site sets it")),
                "duration_s": Field(
                    unit="s", description="How long the arm keeps the velocities; it must be greater than 0",
                    limit=Limit.operator_required(
                        "the SDK states no maximum for the duration of a velocity command (xarm_api.py:3298-3302); "
                        "the site sets it, within the 60 s of the catalogue class")),
            })
    def jog_joints(self, joint_velocities, duration_s):
        if duration_s <= 0:
            # duration 0 or less is "always effective, will not stop automatically" (xarm_api.py:3300-3302)
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               "duration_s must be greater than 0: the arm never stops by itself on a duration of 0")
        if tuple(self.native.version_number) < VELOCITY_DURATION_FIRMWARE:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"firmware {self.native.version_number} is older than "
                               f"{VELOCITY_DURATION_FIRMWARE}: it ignores the duration, so the velocity would never "
                               "stop")
        self._select_mode(4)
        self._check_code(self.native.vc_set_joint_velocity(list(joint_velocities), is_radian=True,
                                                           duration=duration_s), "vc_set_joint_velocity")
        return {"applied": True, "joint_velocities": list(joint_velocities)}

    # -- safety --------------------------------------------------------------------------------------------------
    @action(name="x-cap.xarm-developer.enable_motion.v1", reenable=True,
            description="Re-enable the arm after a safety reset (the declared re-enable): clean_error, clean_warn, "
                        "motion_enable(True), set_mode(0) and set_state(0), the recovery the SDK documents after an "
                        "error; it takes no input, is refused while the e-stop is latched and is never run by the "
                        "reset",
            output={"enabled": Field("boolean", description="True once all five calls returned API code 0")})
    def enable_motion(self):
        """The new start command after a reset (SAFE-042, CORE-086).

        clean_error and clean_warn (xarm_api.py:1588-1604), then the start sequence clean_error asks for by hand
        (xarm_api.py:1590; example/wrapper/xarm7/2001-move_joint.py:44-46).  The first non-zero code stops it.
        """
        self._check_code(self.native.clean_error(), "clean_error")
        self._check_code(self.native.clean_warn(), "clean_warn")
        self._make_ready()
        return {"enabled": True}

    @estop(native="emergency_stop")
    def stop(self):
        """The native stop: the runtime latches first, then the arm goes to stop state 4 (it returns no code)."""
        self.native.emergency_stop()

    # No @reset hook: a driver that declares a re-enable is reset by releasing the latch only (SAFE-042,
    # CORE-086); clearing the controller's errors belongs to the re-enable above.

    def setup(self):
        self._make_ready()

    def teardown(self):
        self.native.disconnect()

    # -- helpers ---------------------------------------------------------------------------------------------------
    def _make_ready(self):
        """The sequence every upstream example starts with (example/wrapper/xarm7/2001-move_joint.py:44-46)."""
        self._check_code(self.native.motion_enable(enable=True), "motion_enable")
        self._check_code(self.native.set_mode(0), "set_mode")
        self._check_code(self.native.set_state(state=0), "set_state")

    def _select_mode(self, mode):
        """Select the control mode a motion needs, unless the arm is paused or stopped (that takes the re-enable).

        Setting state 0 here would also clear a pause or a stop somebody else asked for, so a paused or stopped arm
        is refused instead (xarm_api.py:1530-1534; wait_move, base.py:2531-2541, treats state 4 and above as stopped
        and state 3 as paused).
        """
        state = self.native.state
        if state >= 3:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"the arm is in state {state} (paused or stopped); after an e-stop, reset and then send "
                               "the declared re-enable x-cap.xarm-developer.enable_motion.v1")
        if self.native.mode != mode:
            self._check_code(self.native.set_mode(mode), "set_mode")
            self._check_code(self.native.set_state(state=0), "set_state")

    @staticmethod
    def _pose_of(pose):
        x, y, z, roll, pitch, yaw = pose
        return {"position": {"x": x, "y": y, "z": z}, "orientation": {"roll": roll, "pitch": pitch, "yaw": yaw}}

    @staticmethod
    def _check_code(code, what, after_motion=False):
        """Raise for a non-zero API code (doc/api/xarm_api_code.md:15-58); 0 is the only success.

        ``after_motion`` is for the read-back after a move that finished: the arm moved, so a failure to read where it
        is now is an unknown outcome, never a failed move that a client may retry.
        """
        if code == 0:
            return
        message = f"{what} returned API code {code} ({API_CODES.get(code, 'see doc/api/xarm_api_code.md')})"
        if after_motion:
            raise OutcomeUnknown(f"{message} after the move finished: the arm moved, where it is now is unknown",
                                 native_code=code)
        if code in UNKNOWN_OUTCOME:
            raise OutcomeUnknown(message, native_code=code)
        if code in NOT_READY:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", message, native_code=code)
        if code in OWN_LIMIT:
            raise DriverFailed("MHS.SAFETY.ENVELOPE_VIOLATION", message, native_code=code)
        raise DriverFailed("MHS.DEVICE.FAULTED", message, native_code=code)

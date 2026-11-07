"""OpenMHS driver for gh.dobot-arm/tcp-ip-python-v4: a Dobot V4 series arm over its TCP/IP dashboard protocol.

The upstream SDK is a *composite* object (``DobotRobot``) whose modules (``motion``, ``robot_control``, ``io``,
``communication``) each hold the same connection handle and build every command from parts, for example
``MovJ(joint={0.000000,...},a=...)`` (dobot_sdk/api/motion.py:31-46, :52-87).  This package therefore binds its
native object to the class every command actually travels through, the SDK's own TCP transport
``DobotConnection`` (dobot_sdk/core/connection.py:20), and sends the exact command text the SDK's modules build, so
the hardware backend uses the same wire syntax as the upstream SDK.  ``native.py`` returns that object.

Units.  The dashboard protocol speaks millimetres and degrees for a Cartesian pose and degrees for a joint pose
(assets/SDK_API文档_完整版.md:253-280, :1244-1267); the catalogue classes speak rad and mm, so the pose inputs are
converted to degrees once, at the boundary, and the reads report the device's own degrees.

Motion is queued: ``MovJ`` and ``MovL`` are queue commands that return a result id as soon as the controller accepted
them (assets/SDK_API文档_完整版.md:2362-2365), so a move is reported as *reached* only after the joint or Cartesian
read-back agrees with the target.  ``block`` (joint moves only) waits for that agreement within ``MOVE_TIMEOUT_S``;
without it the action reports the state it read once.  A move is never retried and a value is never clamped: the
runtime owns the envelope.

Limits.  The clone states no joint travel range and no workspace: the SDK supports the CR3/CR5/CR10, E6, CRAF and
NovaLite families (README.md:282-289) whose ranges differ, and the vendor text gives no numbers.  Every motion input
is therefore ``Limit.operator_required``: the site declares the envelope in ``site-limits.json``, and until then every
move is refused with ``MHS.SAFETY.LIMITS_UNSET``.

This package is model-authored and unreviewed: the acceptance gate runs the fake backend only, nothing here ran on
an arm, and the loader refuses the hardware backend until a human signs ``reviewed_by``.  The pinned commit is
55ec1ec82201aaf2e6d54aa47b6272bbaa14c815.
"""

import math
import time

from mhs.driver import Cancelled, Driver, DriverFailed, Fact, Field, Limit, OutcomeUnknown, action, estop, read

CONNECTION = "dobot_sdk/core/connection.py"
MOTION = "dobot_sdk/api/motion.py"
CONTROL = "dobot_sdk/api/robot_control.py"
DOC = "assets/SDK_API文档_完整版.md"
README = "README.md"

#: The arm the SDK drives has six joints (assets/SDK_API文档_完整版.md:253-280, a MovJ joint pose of six values).
JOINT_COUNT = 6
#: A joint within 0.01 degree of its target counts as reached.  This is the driver's reach criterion, not a device
#: specification: the protocol carries a joint angle in degrees (the SDK formats them with six decimals,
#: dobot_sdk/api/motion.py:34) and the controller reports no separate position tolerance.
JOINT_TOLERANCE_RAD = math.radians(0.01)
#: A tool position within 1 mm of its target counts as reached (the same kind of driver-side criterion).
POSE_TOLERANCE_MM = 1.0
#: How long a blocking move waits for the read-back to agree: below the 120000 ms the catalogue classes
#: cap.motion.joint_position.v1 and cap.motion.cartesian_pose.v1 allow.
MOVE_TIMEOUT_S = 100
#: The pause between two read-backs of a blocking move.
POLL_S = 0.2

JOINT_REASON = "the clone states no joint travel range (it depends on the arm family): the site declares it"
POSITION_REASON = "the clone states no workspace (it depends on the arm and the cell): the site declares it"
ORIENTATION_REASON = "the clone states no orientation range (it depends on the tool): the site declares it"


class DobotV4Arm(Driver):
    device_id = "dobot-arm"
    device_kind = "robot.arm"
    mode = "hardware"
    #: R2, above the card's R1 floor: a six-axis arm is moving machinery (the xArm exemplar is R2 as well), so its
    #: hardware backend stays refused until a human signs reviewed_by.  The independent stop is the controller's
    #: emergency-stop button, which the vendor's safety notes tell the user to keep within reach.
    risk = "R2"
    estop_physical_ref = f"{DOC}:2384"
    native = "dobot_sdk.core.connection:DobotConnection"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeDobotConnection"}
    vendor, model = "Dobot", "V4 series arm (CRA, E6, CRAF, NovaLite families)"
    display_name = "Dobot V4 series arm (TCP/IP Python SDK)"
    tags = ["robot arm", "dobot", "tcp ip", "joint motion", "cartesian motion", "stop"]
    facts = [
        Fact("The SDK is a TCP/IP client: it sends a command string over a socket and reads one text reply per "
             "command", source="upstream_code", ref=f"{CONNECTION}:357-369"),
        Fact("A command line is sent with a newline appended and the reply is decoded as UTF-8 and stripped",
             source="upstream_code", ref=f"{CONNECTION}:248-272"),
        Fact("The dashboard command port is 29999 and the feedback port is 30004",
             source="vendor_doc", ref=f"{DOC}:99-108"),
        Fact("The reply to a command has the form 'ErrorID,{...},Command(...);', for example "
             "'0,{[1537,2048]},GetErrorID();'", source="vendor_doc", ref=f"{DOC}:1206-1218"),
        Fact("The error-code table lists 0 as no error and 1537 as the emergency stop triggered",
             source="vendor_doc", ref=f"{DOC}:2169-2170"),
        Fact("The SDK supports the CRA (CR3A, CR5, CR10, CR16), E6, CRAF and NovaLite families",
             source="vendor_doc", ref=f"{README}:282-290"),
        Fact("The README warns to make sure the robot is in a safe position before running",
             source="vendor_doc", ref=f"{README}:306"),
        Fact("The vendor text requires an easily reachable emergency stop button, a slow speed for the first run and "
             "a working range with no people in it", source="vendor_doc", ref=f"{DOC}:2382-2388"),
        Fact("MovJ takes a six-value pose and a coordinate type; with the joint type the pose is six joint angles in "
             "degrees and with the Cartesian type six values in millimetres and degrees",
             source="vendor_doc", ref=f"{DOC}:253-280"),
        Fact("The SDK formats every coordinate of a pose with six decimal places before sending it",
             source="upstream_code", ref=f"{MOTION}:31-46"),
        Fact("MovJ and MovL are queue commands: they join the motion queue and are executed in order, unlike the "
             "immediate commands such as GetPose and Stop",
             source="vendor_doc", ref=f"{DOC}:2362-2365"),
        Fact("GetAngle answers with 'ErrorID,{j1,j2,j3,j4,j5,j6},GetAngle();' and GetPose with "
             "'ErrorID,{x,y,z,rx,ry,rz},GetPose();'",
             source="vendor_doc", ref=f"{DOC}:1244-1267"),
        Fact("GetErrorID answers with 'ErrorID,{[error1,error2,...]},GetErrorID();' and 0 in the error-code table "
             "means no error", source="vendor_doc", ref=f"{DOC}:1206-1218"),
        Fact("RobotMode reports 1 initialising, 2 manual, 3 automatic, 4 remote and 9 error",
             source="vendor_doc", ref=f"{DOC}:1221-1235"),
        Fact("Stop stops the motion command queue the controller was given and any running script",
             source="upstream_code", ref=f"{CONTROL}:83-85"),
        Fact("EmergencyStop(mode) presses the emergency stop with mode 1 and releases it with mode 0",
             source="vendor_doc", ref=f"{DOC}:893-910"),
        Fact("The upstream connection class exposes the command exchange as send_receive_text and the connection state "
             "as the is_connected property", source="upstream_code", ref=f"{CONNECTION}:357-375"),
        Fact("The upstream SDK requests TCP control mode before it moves: every quick-start example calls "
             "RequestControl first", source="upstream_code", ref=f"{CONTROL}:22-34"),
    ]
    safe_state = ("emergency stop pressed on the controller (EmergencyStop(1)); the arm stops and stays stopped until "
                  "an operator releases it with EmergencyStop(0)")

    # -- reads: each command is an immediate query, answered with one text line (DOC:2362-2365) -----------------
    @read("joint_positions", type="array", items="number", length=JOINT_COUNT, unit="deg",
          description="Angles of joints 1 to 6, in degrees, as GetAngle reports them")
    def get_joint_positions(self):
        return _numbers(self._command("GetAngle()", "GetAngle"), JOINT_COUNT, "GetAngle")

    @read("tcp_pose", type="object", description="Tool pose: position in mm and orientation in degrees (GetPose)",
          properties={
              "position": Field("object", description="Tool position in the base frame, in mm",
                                properties={"x": Field("number", unit="mm", description="X position, mm"),
                                            "y": Field("number", unit="mm", description="Y position, mm"),
                                            "z": Field("number", unit="mm", description="Z position, mm")}),
              "orientation": Field("object", description="Tool orientation as rx, ry, rz, in degrees",
                                   properties={"rx": Field("number", unit="deg", description="Rotation about X, deg"),
                                               "ry": Field("number", unit="deg", description="Rotation about Y, deg"),
                                               "rz": Field("number", unit="deg", description="Rotation about Z, deg")}),
          })
    def get_tcp_pose(self):
        values = _numbers(self._command("GetPose()", "GetPose"), 6, "GetPose")
        return {"position": {"x": values[0], "y": values[1], "z": values[2]},
                "orientation": {"rx": values[3], "ry": values[4], "rz": values[5]}}

    @read("robot_mode", type="integer",
          description="Robot mode as the controller reports it: 1 initialising, 2 manual, 3 automatic, 4 remote, "
                      "9 error")
    def get_robot_mode(self):
        payload = self._command("RobotMode()", "RobotMode").strip()
        try:
            return int(payload)
        except ValueError:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"RobotMode answered {payload!r}, which is not one mode number") from None

    @read("error_ids", type="array", items="integer",
          description="The controller's current error codes, empty when it reports none (GetErrorID)")
    def get_error_ids(self):
        payload = self._command("GetErrorID()", "GetErrorID").strip()
        if payload.startswith("[") and payload.endswith("]"):
            payload = payload[1:-1]
        if not payload.strip():
            return []
        try:
            return [int(value) for value in payload.replace(" ", "").split(",") if value]
        except ValueError:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"GetErrorID answered {payload!r}, which is not a list of error codes") from None

    # -- motion: a queue command, then a read-back that says whether the target was reached ----------------------
    @action(cap="cap.motion.joint_position.v1", long_running=True, cancellable=True,
            description="Move the six joints to the given angles; a blocking move returns when the read-back agrees "
                        "with the target, a non-blocking one reports the state it read once",
            input={
                "joint_positions": Field(
                    unit="rad", description="Target angles of joints 1 to 6, in rad",
                    limit=Limit.operator_required(JOINT_REASON)),
                "block": Field(description="Wait until the joints report the target before returning (default true)"),
            })
    def move_joints(self, joint_positions, block=True):
        if len(joint_positions) != JOINT_COUNT:
            raise DriverFailed("MHS.CAPABILITY.INPUT_INVALID",
                               f"the arm has {JOINT_COUNT} joints; {len(joint_positions)} target angles were given")
        target_deg = [math.degrees(value) for value in joint_positions]
        started = time.monotonic()
        self._command("MovJ(" + _joint_point(target_deg) + ")", "MovJ")
        reached, measured = self._wait_for_joints(target_deg, block)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {"reached": reached, "joint_positions": [math.radians(value) for value in measured],
                "duration_ms": elapsed_ms, "tolerance_rad": JOINT_TOLERANCE_RAD}

    @action(cap="cap.motion.cartesian_pose.v1", long_running=True, cancellable=True,
            description="Move the tool to a Cartesian pose with MovL",
            input={
                "position": Field(description="Tool position in the base frame", properties={
                    "x": Field(limit=Limit.operator_required(POSITION_REASON), description="X position"),
                    "y": Field(limit=Limit.operator_required(POSITION_REASON), description="Y position"),
                    "z": Field(limit=Limit.operator_required(POSITION_REASON), description="Z position"),
                }),
                "orientation": Field(description="Tool orientation (kept when omitted)", properties={
                    "roll": Field(limit=Limit.operator_required(ORIENTATION_REASON), description="Rotation about X"),
                    "pitch": Field(limit=Limit.operator_required(ORIENTATION_REASON), description="Rotation about Y"),
                    "yaw": Field(limit=Limit.operator_required(ORIENTATION_REASON), description="Rotation about Z"),
                }),
            })
    def move_pose(self, position, orientation=None):
        if orientation is None:
            current = self._pose()
            target_deg = [position["x"], position["y"], position["z"], current[3], current[4], current[5]]
        else:
            target_deg = [position["x"], position["y"], position["z"],
                          math.degrees(orientation["roll"]), math.degrees(orientation["pitch"]),
                          math.degrees(orientation["yaw"])]
        self._command("MovL(" + _pose_point(target_deg) + ")", "MovL")
        reached, measured = self._wait_for_pose(target_deg)
        return {"reached": reached,
                "position": {"x": measured[0], "y": measured[1], "z": measured[2]},
                "tolerance_mm": POSE_TOLERANCE_MM}

    @action(cap="cap.motion.stop.v1", description="Stop the motion queue the controller is executing",
            input={"deceleration": Field(
                unit="m/s2", description="Accepted for the class only: the controller's Stop() takes no "
                                         "deceleration argument and stops the queue with its own profile")})
    def stop_motion(self, deceleration=None):
        self._command("Stop()", "Stop")
        return {"stopped": True}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="EmergencyStop")
    def stop(self):
        """Press the controller's emergency stop; the runtime latches first, then this reaches the arm."""
        self._command("EmergencyStop(1)", "EmergencyStop")

    # -- lifecycle ------------------------------------------------------------------------------------------------
    def setup(self):
        """Request TCP control mode, the step every upstream example does before it moves (CONTROL:22-34)."""
        self._command("RequestControl()", "RequestControl")

    def teardown(self):
        self.native.disconnect()

    # -- command/read helpers -------------------------------------------------------------------------------------
    def _command(self, command, what):
        """Send one command string through the native connection and return the reply payload.

        A reply is 'ErrorID,{...},Command(...);' (DOC:1206-1218): a non-zero ErrorID is the controller's refusal and
        becomes ``DriverFailed`` with the id as the native code.
        """
        reply = self.native.send_receive_text(command)
        error_id, payload = _parse_reply(reply, what)
        if error_id != 0:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"the controller answered ErrorID {error_id} to {what}: {reply!r}",
                               native_code=error_id)
        return payload

    def _pose(self):
        return _numbers(self._command("GetPose()", "GetPose"), 6, "GetPose")

    def _joint_angles(self):
        return _numbers(self._command("GetAngle()", "GetAngle"), JOINT_COUNT, "GetAngle")

    def _wait_for_joints(self, target_deg, block):
        deadline = time.monotonic() + MOVE_TIMEOUT_S
        while True:
            self.check_cancelled()
            try:
                measured = self._joint_angles()
            except BaseException as exc:
                if isinstance(exc, (Cancelled, KeyboardInterrupt)):
                    raise
                raise OutcomeUnknown(f"MovJ was accepted, but {exc}: where the arm is now is unknown") from None
            reached = all(abs(value - target) <= math.degrees(JOINT_TOLERANCE_RAD)
                          for value, target in zip(measured, target_deg))
            if reached or not block or time.monotonic() >= deadline:
                return reached, measured
            time.sleep(POLL_S)

    def _wait_for_pose(self, target_deg):
        deadline = time.monotonic() + MOVE_TIMEOUT_S
        angle_tolerance = math.degrees(JOINT_TOLERANCE_RAD)
        while True:
            self.check_cancelled()
            try:
                measured = self._pose()
            except BaseException as exc:
                if isinstance(exc, (Cancelled, KeyboardInterrupt)):
                    raise
                raise OutcomeUnknown(f"MovL was accepted, but {exc}: where the arm is now is unknown") from None
            reached = (all(abs(value - target) <= POSE_TOLERANCE_MM
                           for value, target in zip(measured[:3], target_deg[:3]))
                       and all(abs(value - target) <= angle_tolerance
                               for value, target in zip(measured[3:], target_deg[3:])))
            if reached or time.monotonic() >= deadline:
                return reached, measured
            time.sleep(POLL_S)


# -- reply parsing -------------------------------------------------------------------------------------------------
def _parse_reply(reply, what):
    """``(error id, payload)`` of a 'ErrorID,{payload},Command();' text reply (DOC:1206-1218)."""
    text = reply.strip() if isinstance(reply, str) else ""
    head, separator, rest = text.partition(",")
    try:
        error_id = int(head.strip())
    except ValueError:
        raise DriverFailed("MHS.DEVICE.FAULTED",
                           f"the reply to {what} is not 'ErrorID,{{...}},{what}(...);': {text[:300]!r}") from None
    payload = ""
    if separator and rest.startswith("{"):
        end = rest.find("}")
        payload = rest[1:end] if end >= 0 else rest[1:]
    return error_id, payload


def _numbers(payload, count, what):
    """``count`` floats of a comma separated reply payload."""
    try:
        values = [float(item) for item in payload.replace(" ", "").split(",") if item]
    except ValueError:
        raise DriverFailed("MHS.DEVICE.FAULTED",
                           f"{what} answered {payload!r}, which is not a list of numbers") from None
    if len(values) != count:
        raise DriverFailed("MHS.DEVICE.FAULTED",
                           f"{what} answered {len(values)} numbers, expected {count}: {payload!r}")
    return values


def _joint_point(target_deg):
    """The ``joint={...}`` argument of a MovJ command (motion.py:31-46: six decimals, comma separated)."""
    return "joint={" + ",".join(f"{value:.6f}" for value in target_deg) + "}"


def _pose_point(target_deg):
    """The ``pose={...}`` argument of a MovL command (motion.py:31-46: six decimals, comma separated)."""
    return "pose={" + ",".join(f"{value:.6f}" for value in target_deg) + "}"

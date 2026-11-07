"""OpenMHS driver for gh.strands-labs/robots: a Yahboom ROSMASTER M3 Pro.

A direct Driver over ``strands_robots.drivers.yahboom_m3pro:YahboomM3ProDriver``.  The upstream class speaks the
robot's ROS 2 graph: the arm as ``/arm6_joints`` in integer servo degrees, the mecanum base as ``/cmd_vel`` in SI
units, and odometry and IMU from ``/odom_raw`` and ``/imu/data_raw`` (strands_robots/drivers/yahboom_m3pro.py:3-24).

* reads: the connection flag, the upstream observation map, the last commanded arm pose, and the odometry/IMU sample;
* ``cap.motion.joint_position.v1``: six model joint angles in radians, bounded by the servo travel table and the
  upstream radian/degree map (yahboom_m3pro.py:58-63, yahboom_m3pro_wire.py:61-71);
* ``cap.motion.stop.v1``: a safe-state action that sends the zero Twist; the arm holds its own pose;
* ``x-cap.strands-labs.home.v1``: the vendor grasp-init pose, which the catalogue joint class cannot carry as a
  second binding (one binding per catalogue class and resource);
* ``x-cap.strands-labs.gripper.v1``: open or close the gripper, the only two positions the upstream verb accepts;
* ``x-cap.strands-labs.mobile-base.v1``: the base's three Twist axes in SI units for a bounded duration.  The
  catalogue's mobile-base class requires resource kind ``robot.mobile_base`` and this driver serves a ``robot.arm``,
  so the base subsystem uses an extension;
* the native stop is ``stop_task`` (a zero Twist) and an ``@estop`` method reaches it.

The upstream ``stop_task`` is not exempt from the ``/cmd_vel`` operator gate (yahboom_m3pro.py:966-973): on hardware
the zero Twist needs ``STRANDS_ROS2_COMMAND_ALLOW=/cmd_vel`` or an approving operator.  Without it the firmware
watchdog zeroes the base motors within roughly 0.5 s of the last Twist (yahboom_m3pro_wire.py:99-101).

This package is model-authored and unreviewed: it is checked on the fake backend only, and the loader refuses its
hardware backend (R2) until a human signs ``reviewed_by`` in ``driver.lock.json``.  Nothing here ran on a robot.
"""

import math

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

#: Servo order of /arm6_joints: joint1..joint6, the last one the gripper (yahboom_m3pro.py:15-19).
JOINT_NAMES = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]
#: Model joint angles in radians, from the upstream degree/radian map.  Joints 1-4 span 0-180 degrees, joint 5
#: spans 0-270 and the gripper spans 30 (closed) to 180 (open) (yahboom_m3pro.py:58-63,
#: yahboom_m3pro_wire.py:61-71).
JOINT_MIN = [-math.pi / 2, -math.pi / 2, -math.pi / 2, -math.pi / 2, -math.pi / 2, -1.54]
JOINT_MAX = [math.pi / 2, math.pi / 2, math.pi / 2, math.pi / 2, math.pi, 0.0]

DRIVER_PY = "strands_robots/drivers/yahboom_m3pro.py"
WIRE = "strands_robots/drivers/yahboom_m3pro_wire.py"
#: The upstream sentence that maps the model's q to servo degrees for joints 1-5 and the gripper.
JOINT_MAP_REF = f"{DRIVER_PY}:58-63"
#: The servo travel table.
SERVO_TABLE_REF = f"{WIRE}:61-71"
#: The vendor teleop ceilings and the move-duration ceiling.
BASE_CEILING_REF = f"{WIRE}:92-98"
BASE_DURATION_REF = f"{WIRE}:103-105"

#: Conversion constants of the upstream map: q = (deg - 90) * pi / 180 for joints 1-5, and the gripper crank
#: rlink1 travels -1.54 (closed) to 0 (open) onto servo degrees 30 to 180 (yahboom_m3pro.py:58-63).
ARM_CENTER_DEG = 90.0
GRIPPER_CLOSED_RAD = -1.54
GRIPPER_OPEN_RAD = 0.0
GRIPPER_CLOSED_DEG = 30.0
GRIPPER_OPEN_DEG = 180.0


class YahboomM3Pro(Driver):
    """The ROSMASTER M3 Pro's arm, gripper and mecanum base through the upstream ROS 2 driver."""

    device_id = "yahboom-m3pro"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    native = "strands_robots.drivers.yahboom_m3pro:YahboomM3ProDriver"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeYahboomM3Pro"}
    vendor, model = "Yahboom", "ROSMASTER M3 Pro with the DOFBOT-Pro arm"
    display_name = "Yahboom ROSMASTER M3 Pro"
    tags = ["robot arm", "mobile base", "mecanum", "gripper", "ros2", "yahboom", "m3pro"]
    facts = [
        Fact("The M3 Pro is a mecanum chassis carrying the DOFBOT-Pro arm; its motors sit behind an STM32 "
             "expansion board running micro-ROS firmware, reached through ROS 2 Humble and micro_ros_agent",
             source="upstream_code", ref=f"{DRIVER_PY}:3-8"),
        Fact("The base is /cmd_vel (geometry_msgs/Twist): linear.x forward, linear.y strafe, angular.z yaw, SI "
             "units", source="upstream_code", ref=f"{DRIVER_PY}:10-11"),
        Fact("The firmware zeroes the motors after roughly 200-500 ms without a fresh Twist, so a held move is a "
             "stream at the publish rate followed by an explicit zero", source="upstream_code",
             ref=f"{DRIVER_PY}:12-14"),
        Fact("The arm is /arm6_joints (arm_msgs/ArmJoints): all six servos at once as joint1..joint6 in integer "
             "degrees plus time in milliseconds", source="upstream_code", ref=f"{DRIVER_PY}:15-17"),
        Fact("Joints 1-4 travel 0-180 degrees, joint 5 travels 0-270, and joint 6 is the gripper from 30 (closed) "
             "to 180 (open)", source="upstream_code", ref=f"{DRIVER_PY}:17-19"),
        Fact("The board holds a commanded arm pose, so one /arm6_joints message is enough", source="upstream_code",
             ref=f"{DRIVER_PY}:18-19"),
        Fact("The servo travel table is 1-4: 0-180, 5: 0-270, 6: 30-180 degrees, the vendor limits every Yahboom "
             "teleop node clamps to", source="upstream_code", ref=SERVO_TABLE_REF),
        Fact("The model joint q maps to servo degrees as deg = 90 + degrees(q), so +-pi/2 maps onto 0-180 for "
             "joints 1-4 and -pi/2..pi onto 0-270 for joint 5", source="upstream_code", ref=f"{DRIVER_PY}:58-60"),
        Fact("The gripper crank rlink1 travels -1.54 (closed) to 0 (open), mapped linearly onto 30-180 degrees",
             source="upstream_code", ref=f"{DRIVER_PY}:61-62"),
        Fact("The vendor keyboard-teleop ceilings are a linear speed limit of 1.0 m/s and an angular speed limit "
             "of 5.0 rad/s", source="upstream_code", ref=BASE_CEILING_REF),
        Fact("The longest one move may hold a twist is MAX_MOVE_DURATION_S = 10.0 s; a longer run is repeated "
             "calls", source="upstream_code", ref=BASE_DURATION_REF),
        Fact("The board publishes no arm joint-state topic this driver can verify: get_observation returns {} on "
             "the robot rather than echoing the last command as a reading", source="upstream_code",
             ref=f"{DRIVER_PY}:67-70"),
        Fact("The arm holds its pose on its own; only the base can be moving", source="upstream_code",
             ref=f"{DRIVER_PY}:673-677"),
        Fact("stop_task sends a zero Twist, and it is not exempt from the /cmd_vel operator gate: the halt needs a "
             "pre-approved /cmd_vel or an approving operator", source="upstream_code", ref=f"{DRIVER_PY}:966-973"),
        Fact("set_arm_degrees refuses an angle outside each servo's travel rather than clamping it",
             source="upstream_code", ref=f"{WIRE}:156-180"),
    ]
    safe_state = ("the base receives a zero Twist when the /cmd_vel gate allows it (otherwise the firmware watchdog "
                  "zeroes it within roughly 0.5 s), and the arm holds its last commanded pose")
    #: The native stop.  The safe-state action below also runs during an e-stop; R2 needs one of the two for
    #: SAFE-045, and the upstream documents no independent physical e-stop for this chassis.
    stop_native = "stop_task"

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("connected", type="boolean", description="Whether the upstream driver reached the robot's ROS 2 graph")
    def get_connected(self):
        return bool(self.native.is_connected)

    @read("observation", type="object",
          description="Joint positions by model name from /joint_states when the graph carries it; {} on the robot")
    def get_observation(self):
        value = self.native.get_observation()
        return dict(value) if isinstance(value, dict) else {}

    @read("commanded_arm_pose", type="object",
          description="The last commanded arm pose in model radians; {} before the first command")
    def get_commanded_arm_pose(self):
        value = self.native.last_arm_command()
        return dict(value) if isinstance(value, dict) else {}

    @read("sensors", type="object", description="One odometry and one IMU sample, or null members when silent")
    def get_sensors(self):
        value = self.native.read_state()
        return dict(value) if isinstance(value, dict) else {}

    # -- arm motion ----------------------------------------------------------------------------------------------
    @action(cap="cap.motion.joint_position.v1",
            description="Move the five arm servos and the gripper to model joint angles in radians",
            input={"joint_positions": Field(
                unit="rad", length=6,
                description="Target model angles for arm1..arm5 and the gripper (radians)",
                limit=Limit(min=JOINT_MIN, max=JOINT_MAX, names=JOINT_NAMES, source="upstream_code",
                            ref=JOINT_MAP_REF,
                            reason="the upstream radian/degree map and the servo travel table"))})
    def move_joints(self, joint_positions):
        degrees = [_to_servo_degrees(index, value) for index, value in enumerate(joint_positions, start=1)]
        payload = self._success(self.native.set_arm_degrees(degrees), "set_arm_degrees")
        applied = payload.get("arm_deg") if isinstance(payload.get("arm_deg"), list) else degrees
        return {"reached": True,
                "joint_positions": [_to_model_radians(index, value)
                                    for index, value in enumerate(applied, start=1)]}

    @action(name="x-cap.strands-labs.home.v1", risk="R1",
            description="Move the arm to the vendor grasp-init pose with the gripper open",
            input={}, output={"reached": Field("boolean", description="The arm accepted the home pose")})
    def home(self):
        self._success(self.native.home(), "home")
        return {"reached": True}

    @action(name="x-cap.strands-labs.gripper.v1", risk="R1",
            description="Open or close the gripper and leave the other five servos where they are",
            input={"open": Field("boolean", description="true opens the gripper, false closes it")},
            output={"open": Field("boolean", description="The gripper state that was commanded")})
    def set_gripper(self, open):
        self._success(self.native.set_gripper(bool(open)), "set_gripper")
        return {"open": bool(open)}

    # -- base motion ---------------------------------------------------------------------------------------------
    @action(name="x-cap.strands-labs.mobile-base.v1", risk="R2",
            description="Drive the mecanum base with a Twist in SI units for a bounded duration, then stop",
            input={
                "linear_x": Field("number", unit="m/s", description="Forward velocity",
                                  limit=Limit(min=-1.0, max=1.0, source="upstream_code", ref=BASE_CEILING_REF,
                                              reason="the vendor keyboard-teleop linear speed limit")),
                "linear_y": Field("number", unit="m/s", description="Strafe velocity, positive left",
                                  limit=Limit(min=-1.0, max=1.0, source="upstream_code", ref=BASE_CEILING_REF,
                                              reason="the vendor keyboard-teleop linear speed limit")),
                "angular_z": Field("number", unit="rad/s", description="Yaw rate, positive counter-clockwise",
                                   limit=Limit(min=-5.0, max=5.0, source="upstream_code", ref=BASE_CEILING_REF,
                                               reason="the vendor keyboard-teleop angular speed limit")),
                "duration_s": Field("number", unit="s", description="How long to hold the Twist",
                                    limit=Limit(min=0.0, max=10.0, source="upstream_code", ref=BASE_DURATION_REF,
                                                reason="the longest one move may hold a twist")),
            },
            output={
                "stopped": Field("boolean", description="The trailing zero Twist was sent"),
                "held_s": Field("number", unit="s", description="How long the Twist was held"),
            })
    def drive_base(self, linear_x, linear_y, angular_z, duration_s):
        payload = self._success(
            self.native.move(linear_x=float(linear_x), linear_y=float(linear_y),
                             angular_z=float(angular_z), duration_s=float(duration_s)),
            "move")
        if "stopped" not in payload:
            raise DriverFailed("MHS.ADAPTER.SHIM_FAILED", "move returned no stopped flag")
        return {"stopped": bool(payload["stopped"]), "held_s": float(duration_s)}

    # -- safety --------------------------------------------------------------------------------------------------
    @estop(native=stop_native)
    def stop(self):
        """The native stop: a zero Twist; the arm holds its own pose."""
        self._halt_base()

    @action(cap="cap.motion.stop.v1", safe_state=True,
            description="Stop the base with a zero Twist; the arm holds its last commanded pose",
            input={"deceleration": Field(
                unit="m/s2",
                description="Optional class field; the upstream zero Twist stops immediately and has no profile")})
    def stop_motion(self, deceleration=None):
        if deceleration is not None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the upstream stop_task sends a zero Twist and has no deceleration profile; "
                               "omit deceleration")
        self._halt_base()
        return {"stopped": True}

    # -- lifecycle and helpers -----------------------------------------------------------------------------------
    def setup(self):
        # The upstream returns a reason instead of raising when the graph is unreachable; its reads then return
        # their caches and its writes refuse.  Keep that behaviour rather than failing the endpoint at startup.
        self._connect_error = self.native.connect_eagerly()

    def _halt_base(self):
        self._success(self.native.stop_task(), "stop_task")

    @staticmethod
    def _success(envelope, what):
        """Return the success envelope's json payload, or raise for a refusal or a malformed answer."""
        if not isinstance(envelope, dict) or not isinstance(envelope.get("status"), str):
            raise DriverFailed("MHS.ADAPTER.SHIM_FAILED",
                               f"{what} returned {type(envelope).__name__}, not a status envelope")
        if envelope["status"] == "success":
            for block in envelope.get("content") or []:
                if isinstance(block, dict) and isinstance(block.get("json"), dict):
                    return block["json"]
            return {}
        texts = [str(block["text"]).strip() for block in envelope.get("content") or []
                 if isinstance(block, dict) and block.get("text")]
        detail = " ".join(texts) or "no detail reported"
        code = "MHS.DEVICE.PRECONDITION_UNMET" if "not connected" in detail.lower() else "MHS.DEVICE.FAULTED"
        raise DriverFailed(code, f"{what} was refused: {detail}")


def _to_servo_degrees(index, radians):
    """Model radians -> the integer servo degrees the upstream wire commands."""
    value = float(radians)
    if index <= 5:
        return int(round(ARM_CENTER_DEG + math.degrees(value)))
    fraction_closed = (value - GRIPPER_OPEN_RAD) / (GRIPPER_CLOSED_RAD - GRIPPER_OPEN_RAD)
    return int(round(GRIPPER_OPEN_DEG + fraction_closed * (GRIPPER_CLOSED_DEG - GRIPPER_OPEN_DEG)))


def _to_model_radians(index, degrees):
    """Integer servo degrees -> the model radians the upstream reports (the inverse map)."""
    value = float(degrees)
    if index <= 5:
        return math.radians(value - ARM_CENTER_DEG)
    fraction_closed = (value - GRIPPER_OPEN_DEG) / (GRIPPER_CLOSED_DEG - GRIPPER_OPEN_DEG)
    return GRIPPER_OPEN_RAD + fraction_closed * (GRIPPER_CLOSED_RAD - GRIPPER_OPEN_RAD)

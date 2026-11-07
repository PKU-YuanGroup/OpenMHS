"""OpenMHS driver for the Tetheria (Chestnut Robotics) Aero Hand Open.

The pinned repository carries three surfaces: the Python hardware SDK
(``aero_open_sdk.aero_hand:AeroHand``), a ROS 2 topic node that subscribes to
``right/joint_control``, ``left/joint_control``, ``right/actuator_control`` and
``left/actuator_control`` and publishes ``*/actuator_states``, and MuJoCo/RL
environments.  The card names ``RosDriver`` because of the ROS 2 package, but
the node exposes no service or action and therefore no acknowledged stop or
safe-state path.  This package is a direct Driver over the SDK class, which is
the card's first confirmed entry symbol and the interface that actually owns the
position commands, the per-actuator configuration and the calibration command.

Scope: five feedback reads (actuations, compact joint positions, actuator
speeds, currents and temperatures), two motion actions (16 joint positions in
degrees or 7 direct actuations in degrees), two configuration writes (per
actuator speed and per actuator maximum torque) and the native per-actuator
mid-position calibration.  The input-free ``open_hand`` action writes the
upstream joint lower limits, the same open pose the SDK GUI sends from its
"Set to Open Position" button.  It is an ordinary action, not a safe state:
the firmware has no stop, disable, brake or torque-off opcode, it does not
acknowledge a CTRL_POS frame, and ``set_joint_positions`` swallows a serial
write timeout.  The e-stop sends the same open command and then reports
MHS.SAFETY.SAFE_STATE_UNREACHED with the latch held, so this package is blocked
(NO_HARDWARE_FREE_PATH; model review, 2026-11-05).  No physical e-stop is
claimed and no stopped-state sensing is invented.

Every Fact and Limit cites the pinned clone at
7bb2f23485a7d440960c21046da642de132b7745.  The fake is a ROS-free Python double
of the public SDK surface; no ROS graph, serial port or hardware is used.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The upstream SDK module and class (entry symbol of the task card).
SDK = "sdk/src/aero_open_sdk/aero_hand.py"
CONSTANTS = "sdk/src/aero_open_sdk/aero_hand_constants.py"
GUI = "sdk/src/aero_open_sdk/gui.py"
FIRMWARE = "firmware/main/firmware.ino"
ROS_NODE = "ros2/src/aero_hand_open/aero_hand_open/aero_hand_node.py"

#: The joint and actuation names are the upstream order; the driver never reorders them.
JOINT_NAMES = (
    "thumb_cmc_abd", "thumb_cmc_flex", "thumb_mcp", "thumb_ip",
    "index_mcp_flex", "index_pip", "index_dip",
    "middle_mcp_flex", "middle_pip", "middle_dip",
    "ring_mcp_flex", "ring_pip", "ring_dip",
    "pinky_mcp_flex", "pinky_pip", "pinky_dip",
)
ACTUATION_NAMES = (
    "thumb_cmc_abd_act", "thumb_cmc_flex_act", "thumb_tendon_act",
    "index_tendon_act", "middle_tendon_act", "ring_tendon_act", "pinky_tendon_act",
)

_JOINT_LIMIT_REF = f"{CONSTANTS}:28-42"
_ACTUATION_LIMIT_REF = f"{CONSTANTS}:49-54"
_SPEED_LIMIT_REF = f"{SDK}:267-270"
_TORQUE_LIMIT_REF = f"{SDK}:291-294"
_SERVO_LIMIT_REF = f"{SDK}:339-341"

_JOINT_LIMIT = Limit(
    min=[0.0] * 16,
    max=[100.0, 55.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0,
         90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0, 90.0],
    names=list(JOINT_NAMES),
    source="upstream_code",
    ref=_JOINT_LIMIT_REF,
    reason="AeroHandConstants.joint_lower_limits and joint_upper_limits, in degrees; "
           "set_joint_positions clamps to the same arrays",
)
_ACTUATION_LIMIT = Limit(
    min=[0.0, 0.0, -15.2789, 0.0, 0.0, 0.0, 0.0],
    max=[100.0, 104.125, 247.15, 288.1603, 288.1603, 288.1603, 288.1603],
    names=list(ACTUATION_NAMES),
    source="upstream_code",
    ref=_ACTUATION_LIMIT_REF,
    reason="AeroHandConstants.actuation_lower_limits and actuation_upper_limits, in degrees; "
           "set_actuations clamps to the same arrays",
)
_SPEED_LIMIT = Limit(
    min=[0] * 7,
    max=[32766] * 7,
    names=list(ACTUATION_NAMES),
    source="upstream_code",
    ref=_SPEED_LIMIT_REF,
    reason="set_speed validates each actuator speed as 0..32766",
)
_TORQUE_LIMIT = Limit(
    min=[0] * 7,
    max=[1000] * 7,
    names=list(ACTUATION_NAMES),
    source="upstream_code",
    ref=_TORQUE_LIMIT_REF,
    reason="set_torque validates each actuator torque value as 0..1000",
)
_SERVO_LIMIT = Limit(
    min=0,
    max=6,
    source="upstream_code",
    ref=_SERVO_LIMIT_REF,
    reason="calibrate_mid validates the actuator id as 0..6",
)

_ACTUATION_FIELD = Field("array", items=Field("number", unit="deg"), length=7,
                         description="Seven actuator values in degrees in the upstream actuation order")
_JOINT_FIELD = Field("array", items=Field("number", unit="deg"), length=16,
                     description="Sixteen joint positions in degrees in the upstream joint order")
_COMPACT_JOINT_FIELD = Field("array", items=Field("number", unit="deg"), length=7,
                             description="Seven compact joint positions in degrees")
_SPEED_FIELD = Field("array", items=Field("number", unit="/min"), length=7,
                     description="Signed actuator speeds in revolutions per minute")
_CURRENT_FIELD = Field("array", items=Field("number", unit="mA"), length=7,
                       description="Signed actuator currents in milliamperes")
_TEMPERATURE_FIELD = Field("array", items=Field("number", unit="Cel"), length=7,
                           description="Actuator temperatures in degrees Celsius")


class AeroHandOpen(Driver):
    device_id = "aero-hand-open"
    device_kind = "robot.arm"
    mode = "hardware"
    #: A tendon-driven hand moves fingers and can pinch; it is a manipulator, so
    #: it is at least R2 even though the card's floor is R1.
    risk = "R2"
    native = "aero_open_sdk.aero_hand:AeroHand"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeAeroHand"}
    vendor = "Tetheria (Chestnut Robotics)"
    model = "Aero Hand Open"
    display_name = "Aero Hand Open (aero_open_sdk.AeroHand)"
    tags = ["tetheria", "chestnut-robotics", "aero hand", "dexterous hand", "tendon-driven",
            "serial", "sdk", "joint position", "actuation"]

    facts = [
        Fact("AeroHand is the SDK's hardware class; its constructor opens a serial port with a 0.01 s "
             "read and write timeout and takes the port and baudrate as arguments.",
             source="upstream_code", ref=f"{SDK}:53-64"),
        Fact("AeroHand copies joint_lower_limits, joint_upper_limits, actuation_lower_limits and "
             "actuation_upper_limits from AeroHandConstants onto the instance.",
             source="upstream_code", ref=f"{SDK}:66-75"),
        Fact("set_joint_positions accepts 16 or 7 joint positions in degrees, expands the compact 7-joint "
             "form to 16, clamps each position to the joint limits and sends CTRL_POS after normalizing "
             "the actuations to the uint16 range.",
             source="upstream_code", ref=f"{SDK}:134-164"),
        Fact("set_joint_positions catches a SerialTimeoutException from the CTRL_POS write, prints it and "
             "returns without raising.",
             source="upstream_code", ref=f"{SDK}:163-167"),
        Fact("set_actuations accepts 7 actuations in degrees, clamps each to the actuation limits and sends "
             "the same CTRL_POS frame, printing a SerialTimeoutException instead of raising it; the "
             "docstring warns that the thumb actuations are not independent and an uncoupled command can "
             "derail the thumb tendons.",
             source="upstream_code", ref=f"{SDK}:191-227"),
        Fact("get_actuations sends GET_POS, requires the full 16-byte reply and the GET_POS opcode, and "
             "returns None on a short read or an unexpected opcode.",
             source="upstream_code", ref=f"{SDK}:427-460"),
        Fact("get_joint_positions_compact returns 7 joint positions in degrees and returns None when "
             "get_actuations returns None.",
             source="upstream_code", ref=f"{SDK}:406-425"),
        Fact("get_actuator_speeds sends GET_VEL and converts each signed raw value with the factor "
             "0.732 RPM.",
             source="upstream_code", ref=f"{SDK}:519-545"),
        Fact("get_actuator_currents sends GET_CURR and converts each signed raw value with the factor "
             "6.5 mA.",
             source="upstream_code", ref=f"{SDK}:462-489"),
        Fact("get_actuator_temperatures sends GET_TEMP and returns the unsigned values directly as "
             "degrees Celsius.",
             source="upstream_code", ref=f"{SDK}:491-517"),
        Fact("set_speed takes an actuator id 0..6 and a speed 0..32766, sends SET_SPE and waits for the "
             "matching acknowledgement.",
             source="upstream_code", ref=f"{SDK}:259-281"),
        Fact("set_torque takes an actuator id 0..6 and a torque value 0..1000, sends SET_TOR and waits for "
             "the matching acknowledgement.",
             source="upstream_code", ref=f"{SDK}:283-305"),
        Fact("calibrate_mid takes an actuator id 0..6, sends CALIBRATE_MID and requires firmware protocol "
             "version 1, a non-error status and non-sentinel raw values.",
             source="upstream_code", ref=f"{SDK}:339-374"),
        Fact("AeroHandConstants declares the 16 joint names and the 16 joint lower and upper limits.",
             source="upstream_code", ref=f"{CONSTANTS}:20-41"),
        Fact("AeroHandConstants declares the 7 actuation names and the 7 actuation lower and upper limits.",
             source="upstream_code", ref=f"{CONSTANTS}:44-54"),
        Fact("The SDK GUI's 'Set to Open Position' button calls on_zero_all.",
             source="upstream_code", ref=f"{GUI}:155"),
        Fact("on_zero_all sets the sliders to 0.0 and sends list(self.hand.joint_lower_limits) through "
             "set_joint_positions.",
             source="upstream_code", ref=f"{GUI}:481-491"),
        Fact("The firmware control opcodes include HOMING, SET_ID, TRIM, CALIBRATE_MID, CTRL_POS, CTRL_TOR, "
             "GET_POS, GET_VEL, GET_CURR, GET_TEMP, SET_SPE and SET_TOR; it declares no stop, disable, brake "
             "or torque-off opcode.",
             source="upstream_code", ref=f"{FIRMWARE}:26-37"),
        Fact("The firmware handles CTRL_POS by switching to position mode when needed and calling "
             "SyncWritePosEx with the per-servo speed, acceleration and torque limits; it does not "
             "acknowledge the frame.",
             source="upstream_code", ref=f"{FIRMWARE}:517-546"),
        Fact("The firmware handles CTRL_TOR by raising each torque magnitude to at least HOLD_MAG, signing "
             "it toward the grasp direction and writing it in torque mode.",
             source="upstream_code", ref=f"{FIRMWARE}:548-584"),
        Fact("While homing is busy the firmware loop reads and discards every host byte.",
             source="upstream_code", ref=f"{FIRMWARE}:687-692"),
        Fact("The ROS 2 node creates subscriptions on the right/left joint_control or actuator_control "
             "topics, by control_space, and publishers on the right/left actuator_states topics.",
             source="upstream_code", ref=f"{ROS_NODE}:60-130"),
        Fact("LICENSE.md licenses the firmware and SDK under Apache-2.0 and the hardware design files and "
             "documentation under CC BY-NC-SA 4.0.",
             source="vendor_doc", ref="LICENSE.md:9-10"),
    ]

    safe_state = (
        "No acknowledged stop: the firmware has no stop, disable, brake or torque-off opcode and does not "
        "acknowledge a CTRL_POS frame, and set_joint_positions swallows a serial write timeout. The "
        "e-stop writes the joint lower limits (the GUI's open pose, a finger motion, not a hold) and then "
        "reports SAFE_STATE_UNREACHED with the latch held; nothing senses where the fingers stop."
    )

    @read("actuations", type=_ACTUATION_FIELD,
          description="Actuator positions reported by GET_POS, in degrees")
    def actuations(self):
        return self._array(self.native.get_actuations(), 7, "actuations")

    @read("joint_positions_compact", type=_COMPACT_JOINT_FIELD,
          description="Compact seven-joint positions in degrees, derived from the actuator positions")
    def joint_positions_compact(self):
        value = self.native.get_joint_positions_compact()
        if value is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "the hand did not return a joint-position sample")
        return self._array(value, 7, "compact joint positions")

    @read("actuator_speeds", type=_SPEED_FIELD,
          description="Signed actuator speeds in revolutions per minute")
    def actuator_speeds(self):
        value = self.native.get_actuator_speeds()
        if value is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "the hand did not return a speed sample")
        return self._array(value, 7, "actuator speeds")

    @read("actuator_currents", type=_CURRENT_FIELD,
          description="Signed actuator currents in milliamperes")
    def actuator_currents(self):
        value = self.native.get_actuator_currents()
        if value is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "the hand did not return a current sample")
        return self._array(value, 7, "actuator currents")

    @read("actuator_temperatures", type=_TEMPERATURE_FIELD,
          description="Actuator temperatures in degrees Celsius")
    def actuator_temperatures(self):
        value = self.native.get_actuator_temperatures()
        if value is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "the hand did not return a temperature sample")
        return self._array(value, 7, "actuator temperatures")

    @action(
        name="x-cap.tetheria.joint_position.v1",
        description="Send 16 joint positions in degrees with the native position command and read the "
                    "actuation state back; reaching the target is not acknowledged",
        input={
            "joint_positions": Field(
                "array",
                items=Field("number", unit="deg"),
                length=16,
                description="Sixteen target joint positions in degrees in the upstream joint order",
                limit=_JOINT_LIMIT,
            ),
        },
        output={
            "commanded": Field("boolean", description="True when set_joint_positions returned; the SDK "
                                                      "swallows a write timeout, so not proof of a write"),
            "commanded_joint_positions": Field(
                "array", items=Field("number", unit="deg"), length=16,
                description="The sixteen targets that were sent, in degrees"),
            "actuations": Field(
                "array", items=Field("number", unit="deg"), length=7,
                description="Actuator positions read back after the command, in degrees; not a "
                            "reached check"),
        },
    )
    def move_joints(self, joint_positions):
        self.check_cancelled()
        self.native.set_joint_positions([float(value) for value in joint_positions])
        actuations = self._array(self.native.get_actuations(), 7, "actuations")
        return {
            "commanded": True,
            "commanded_joint_positions": [float(value) for value in joint_positions],
            "actuations": actuations,
        }

    @action(
        name="x-cap.tetheria.actuation.v1",
        description="Send seven actuator positions in degrees with the native direct-actuation command and "
                    "read the actuation state back",
        input={
            "actuations": Field(
                "array",
                items=Field("number", unit="deg"),
                length=7,
                description="Seven actuator positions in degrees in the upstream actuation order",
                limit=_ACTUATION_LIMIT,
            ),
        },
        output={
            "commanded": Field("boolean", description="True when set_actuations returned; the SDK "
                                                      "swallows a write timeout, so not proof of a write"),
            "commanded_actuations": Field(
                "array", items=Field("number", unit="deg"), length=7,
                description="The seven actuation targets that were sent, in degrees"),
            "measured_actuations": Field(
                "array", items=Field("number", unit="deg"), length=7,
                description="Actuator positions read back after the command, in degrees; not a "
                            "reached check"),
        },
    )
    def move_actuations(self, actuations):
        self.check_cancelled()
        self.native.set_actuations([float(value) for value in actuations])
        measured = self._array(self.native.get_actuations(), 7, "actuations")
        return {
            "commanded": True,
            "commanded_actuations": [float(value) for value in actuations],
            "measured_actuations": measured,
        }

    @action(
        name="x-cap.tetheria.calibrate_mid.v1",
        description="Calibrate one actuator's current position as its middle position with the native "
                    "calibrate_mid command",
        input={
            "servo_id": Field("integer", unit="1",
                              description="Actuator index 0..6 in the upstream actuation order",
                              limit=_SERVO_LIMIT),
        },
        output={
            "servo_id": Field("integer", description="Actuator index reported by the acknowledgement"),
            "present_raw": Field("integer", description="Raw present position reported by the firmware"),
            "present_u16": Field("integer", description="Position mapped to the uint16 range"),
        },
    )
    def calibrate_mid(self, servo_id):
        result = self.native.calibrate_mid(int(servo_id))
        return {
            "servo_id": int(result["Servo ID"]),
            "present_raw": int(result["Present Raw"]),
            "present_u16": int(result["Present U16"]),
        }

    @action(
        name="x-cap.tetheria.open_hand.v1",
        description="Write the upstream joint lower limits (the SDK GUI's open-hand position) and return "
                    "the positions read back; an unacknowledged motion command, not a stop",
        output={
            "joint_positions": Field(
                "array", items=Field("number", unit="deg"), length=7,
                description="Compact joint positions read back after the open command, in degrees"),
            "actuations": Field(
                "array", items=Field("number", unit="deg"), length=7,
                description="Actuator positions read back after the open command, in degrees"),
        },
    )
    def open_hand(self):
        self._command_open()
        joint_positions = self.native.get_joint_positions_compact()
        if joint_positions is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "the hand did not return a joint-position sample")
        actuations = self.native.get_actuations()
        if actuations is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "the hand did not return an actuation sample")
        return {
            "joint_positions": self._array(joint_positions, 7, "compact joint positions"),
            "actuations": self._array(actuations, 7, "actuations"),
        }

    @write("speed", type="array", items=Field("integer"), length=7, unit="1",
           description="Per-actuator maximum speed in the native 0..32766 setting, in the upstream "
                       "actuation order", limit=_SPEED_LIMIT)
    def set_speed(self, value):
        applied = []
        for index, item in enumerate(value):
            result = self.native.set_speed(index, int(item))
            applied.append(int(result["Speed"]))
        return applied

    @write("max_torque", type="array", items=Field("integer"), length=7, unit="1",
           description="Per-actuator maximum torque in the native 0..1000 setting, in the upstream "
                       "actuation order", limit=_TORQUE_LIMIT)
    def set_max_torque(self, value):
        applied = []
        for index, item in enumerate(value):
            result = self.native.set_torque(index, int(item))
            applied.append(int(result["Torque"]))
        return applied

    @estop(native="set_joint_positions")
    def stop(self):
        """Send the open-hand joint lower limits, then refuse to certify a safe state.

        The firmware has no stop, disable, brake or torque-off opcode and does not acknowledge
        CTRL_POS; set_joint_positions swallows a write timeout.  The e-stop therefore reports
        SAFE_STATE_UNREACHED and the latch stays held (model review, 2026-11-05).
        """
        self._command_open()
        raise DriverFailed(
            "MHS.SAFETY.SAFE_STATE_UNREACHED",
            "the open-hand position command was written without acknowledgement; the firmware has no "
            "stop opcode and nothing confirms that the fingers stopped",
        )

    def teardown(self):
        self.native.close()

    def _command_open(self):
        lower = self.native.joint_lower_limits
        self.native.set_joint_positions([float(value) for value in lower])

    @staticmethod
    def _array(value, length, what):
        if value is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", f"the hand did not return a {what} sample")
        values = [float(item) for item in value]
        if len(values) != length:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"the hand returned {len(values)} values for {what}, expected {length}")
        return values

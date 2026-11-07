"""OpenMHS driver for gh.idc-milab/openlh: the OpenLH liquid handler built on a uArm Swift Pro.

The clone is a Flask/Blockly application around a modified copy of the uArm Python SDK
(``pyuf/uf/wrapper/swift_with_ultrasonic.py:SwiftWithUltrasonic``, README.md:2).  The card proposes a
``SerialDriver``, but the upstream API assembles every wire line from a command letter and run-time values
(``'G0'`` plus ``X{x} Y{y} Z{z} F{speed}`` at pyuf/uf/wrapper/swift_api.py:220-243; ``'G202'`` plus ``N{id} V{angle}``
at pyuf/uf/wrapper/swift_api.py:331-333), so a command table cannot reproduce the bytes.  This package is therefore a
direct Driver over ``SwiftWithUltrasonic`` with a ``native.py`` factory (DEVIATION FROM THE CARD, recorded in
RESULT.json).

* reads: the arm's Cartesian position, its polar coordinate, the four servo angles, the ultrasonic distance, the
  limit switch, the moving flag, and the last pump and gripper commands (the clone has no query for those two);
* writes: each of the four servo angles, the pump on/off and the gripper on/off;
* actions: ``cap.motion.cartesian_pose.v1`` for an absolute X/Y/Z move and the safe-state action
  ``x-cap.idc-milab.tool_off.v1`` which turns the pump and gripper off; the on/off gripper is writable state
  (``gripper_closed``) because the class ``cap.manipulation.grasp.v1`` asks for a force and a width that the
  upstream on/off gripper does not have;
* the e-stop also turns the pump and gripper off.  The upstream wrapper has no motion stop, abort or halt method:
  ``close_conn`` only closes the serial port (pyuf/uf/wrapper/swift_api.py:117-119), so an arm move already sent to
  the firmware may complete.

The Cartesian workspace and the speed are not stated by any text of the clone; ``set_position`` even comments that the
device answers ``ok`` for an out-of-range command (pyuf/uf/wrapper/swift_api.py:246), so the three workspace leaves are
``Limit.operator_required`` and ``site-limits.example.json`` shows the overlay.  The 0-180 degree servo range is
stated by the upstream code (pyuf/uf/wrapper/swift_api.py:321).

Every Fact and Limit cites a line of the clone at commit 6a7562c61656362bc70ce58b7f685090cceebda4.  This package is
model-authored and unreviewed: the R2 hardware backend is refused by the loader until a human sets ``reviewed_by``,
and the gate runs the fake backend only.  No hardware was attached.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

SWIFT_API = "pyuf/uf/wrapper/swift_api.py"
SWIFT_ULTRASONIC = "pyuf/uf/wrapper/swift_with_ultrasonic.py"


def _axis_reason(axis: str) -> str:
    return (
        f"no text file of the clone states the {axis} travel of the arm: set_position sends G0 without an envelope "
        f"check and returns True even when the device answers out of range ({SWIFT_API}:246); the site supplies the "
        f"{axis} envelope of its cell"
    )


def _angle_limit() -> Limit:
    return Limit(
        min=0,
        max=180,
        unit="deg",
        source="upstream_code",
        ref=f"{SWIFT_API}:321",
        reason="set_servo_angle documents 0 - 180 degrees; the same range is printed in the API page "
               "(pyuf/doc/api/swift_api.md:363)",
    )


class Openlh(Driver):
    device_id = "openlh"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    native = "pyuf.uf.wrapper.swift_with_ultrasonic:SwiftWithUltrasonic"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeSwiftWithUltrasonic"}
    vendor, model = "idc-milab / UFactory", "OpenLH liquid handler on a uArm Swift Pro"
    display_name = "OpenLH liquid handler (uArm Swift Pro)"
    tags = ["openlh", "uarm", "swift pro", "liquid handling", "robot arm", "serial"]
    facts = [
        Fact("The OpenLH is a liquid handling system based on the uArm Swift Pro robotic arm",
             source="vendor_doc", ref="README.md:2"),
        Fact("SwiftWithUltrasonic is the API wrapper of swift and swift_pro; its defaults are dev_port=None, "
             "baud=115200, filters={'hwid': 'USB VID:PID=2341:0042'} and ultrasonic_port='D8'",
             source="upstream_code", ref=f"{SWIFT_ULTRASONIC}:14-19"),
        Fact("get_position calls P2220 and returns an [x, y, z] float array of the arm's current location",
             source="upstream_code", ref=f"{SWIFT_API}:248-261"),
        Fact("get_polar calls P2221 and returns an [rotation, stretch, height] float array",
             source="upstream_code", ref=f"{SWIFT_API}:304-317"),
        Fact("The servo numbers are SERVO_BOTTOM 0, SERVO_LEFT 1, SERVO_RIGHT 2 and SERVO_HAND 3",
             source="upstream_code", ref=f"{SWIFT_API}:15-19"),
        Fact("get_servo_angle returns an array of float, or one float when a servo id is given, and reads "
             "P2200/P2206",
             source="upstream_code", ref=f"{SWIFT_API}:350-378"),
        Fact("set_servo_angle sends G202 N<servo> V<angle> and documents 0 - 180 degrees",
             source="upstream_code", ref=f"{SWIFT_API}:319-335"),
        Fact("set_position sends G0 with X, Y, Z and F values; it documents x, y and z in mm and speed in mm/sec, "
             "and its return comment says the device returns ok even out of range",
             source="upstream_code", ref=f"{SWIFT_API}:203-246"),
        Fact("set_pump writes the pump service value on or off and returns True when the reply starts with 'ok'",
             source="upstream_code", ref=f"{SWIFT_API}:550-566"),
        Fact("set_gripper writes the gripper service value on or off and returns True when the reply starts with "
             "'ok'",
             source="upstream_code", ref=f"{SWIFT_API}:568-584"),
        Fact("get_ultrasonic calls 'get value' on the ultrasonic node and returns an int distance in cm",
             source="upstream_code", ref=f"{SWIFT_ULTRASONIC}:91-103"),
        Fact("get_limit_switch reads P2233 and returns True for 'ok V1' and False for 'ok V0'",
             source="upstream_code", ref=f"{SWIFT_API}:586-599"),
        Fact("get_is_moving reads M2200 and returns True for 'ok V1' and False for 'ok V0'",
             source="upstream_code", ref=f"{SWIFT_API}:176-189"),
        Fact("The SwiftAPI class defines no motion stop, abort or halt method; its only connection-level stop is "
             "close_conn, and reset attaches the servos and moves to the default position",
             source="upstream_code", ref=f"{SWIFT_API}:27-725"),
        Fact("The README says the arm runs a custom Marlin firmware and the OpenLH compiles Swift API calls to "
             "G-code over UART",
             source="vendor_doc", ref="README.md:66-70"),
    ]
    safe_state = ("the pump and the gripper are off (the tool outputs); the upstream API has no motion halt, so a "
                  "move already sent to the firmware may complete")

    # -- reads ------------------------------------------------------------------------------------------------
    @read("position_x", unit="mm", description="Current X position of the tool centre point in millimetres")
    def position_x(self):
        return float(self._position()[0])

    @read("position_y", unit="mm", description="Current Y position of the tool centre point in millimetres")
    def position_y(self):
        return float(self._position()[1])

    @read("position_z", unit="mm", description="Current Z position of the tool centre point in millimetres")
    def position_z(self):
        return float(self._position()[2])

    @read("polar_rotation", unit="deg", description="Polar rotation of the arm in degrees")
    def polar_rotation(self):
        return float(self._polar()[0])

    @read("polar_stretch", unit="mm", description="Polar stretch of the arm in millimetres")
    def polar_stretch(self):
        return float(self._polar()[1])

    @read("polar_height", unit="mm", description="Polar height of the arm in millimetres")
    def polar_height(self):
        return float(self._polar()[2])

    @read("base_angle", unit="deg", description="Angle of servo 0, the base, in degrees")
    def base_angle(self):
        return self._angle(0)

    @read("left_angle", unit="deg", description="Angle of servo 1, the left joint, in degrees")
    def left_angle(self):
        return self._angle(1)

    @read("right_angle", unit="deg", description="Angle of servo 2, the right joint, in degrees")
    def right_angle(self):
        return self._angle(2)

    @read("hand_angle", unit="deg", description="Angle of servo 3, the wrist, in degrees")
    def hand_angle(self):
        return self._angle(3)

    @read("ultrasonic_distance", type="integer", unit="cm",
          description="Distance reported by the Grove ultrasonic sensor in centimetres")
    def ultrasonic_distance(self):
        value = self.native.get_ultrasonic()
        if value is None:
            raise DriverFailed("MHS.DEVICE.FAULTED", "get_ultrasonic returned no distance")
        return int(value)

    @read("limit_switch", type="boolean", description="True when the arm's limit switch reports closed")
    def limit_switch(self):
        value = self.native.get_limit_switch()
        if value is None:
            raise DriverFailed("MHS.DEVICE.FAULTED", "get_limit_switch returned no state")
        return bool(value)

    @read("is_moving", type="boolean", description="True while the arm reports that it is moving")
    def is_moving(self):
        value = self.native.get_is_moving()
        if value is None:
            raise DriverFailed("MHS.DEVICE.FAULTED", "get_is_moving returned no state")
        return bool(value)

    @read("pump_on", type="boolean",
          description="True when this driver last commanded the pump on; the clone has no pump query")
    def pump_on(self):
        return bool(getattr(self, "_pump_on", False))

    @read("gripper_closed", type="boolean",
          description="True when this driver last commanded the gripper closed; the clone has no gripper query")
    def gripper_closed(self):
        return bool(getattr(self, "_gripper_closed", False))

    # -- writes -------------------------------------------------------------------------------------------------
    @write("base_angle", unit="deg", description="Angle of servo 0, the base, in degrees",
           limit=_angle_limit())
    def set_base_angle(self, value):
        return self._set_angle(0, value)

    @write("left_angle", unit="deg", description="Angle of servo 1, the left joint, in degrees",
           limit=_angle_limit())
    def set_left_angle(self, value):
        return self._set_angle(1, value)

    @write("right_angle", unit="deg", description="Angle of servo 2, the right joint, in degrees",
           limit=_angle_limit())
    def set_right_angle(self, value):
        return self._set_angle(2, value)

    @write("hand_angle", unit="deg", description="Angle of servo 3, the wrist, in degrees",
           limit=_angle_limit())
    def set_hand_angle(self, value):
        return self._set_angle(3, value)

    @write("pump_on", type="boolean",
           description="Turn the vacuum pump on or off; set_pump has no rate or pressure argument")
    def set_pump_on(self, value):
        ok = self.native.set_pump(bool(value))
        if not ok:
            raise DriverFailed("MHS.DEVICE.FAULTED", "set_pump returned False")
        self._pump_on = bool(value)
        return self._pump_on

    @write("gripper_closed", type="boolean",
           description="Close or open the gripper; set_gripper has no force or width argument")
    def set_gripper_closed(self, value):
        ok = self.native.set_gripper(bool(value))
        if not ok:
            raise DriverFailed("MHS.DEVICE.FAULTED", "set_gripper returned False")
        self._gripper_closed = bool(value)
        return self._gripper_closed

    # -- catalogue actions ---------------------------------------------------------------------------------------
    @action(cap="cap.motion.cartesian_pose.v1",
            description="Move the tool centre point to an absolute X/Y/Z position in millimetres with "
                        "set_position(wait=True); the API has no orientation command",
            input={"position": Field("object", description="Absolute X/Y/Z target in millimetres")},
            limits={
                "position.x": Limit.operator_required(_axis_reason("X")),
                "position.y": Limit.operator_required(_axis_reason("Y")),
                "position.z": Limit.operator_required(_axis_reason("Z")),
            })
    def move_to_position(self, position):
        try:
            x = float(position["x"])
            y = float(position["y"])
            z = float(position["z"])
        except (KeyError, TypeError, ValueError) as exc:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"position needs numeric x, y and z: {exc}") from exc
        self.check_cancelled()
        if not self.native.set_position(x, y, z, wait=True):
            raise DriverFailed("MHS.DEVICE.FAULTED", "set_position returned False")
        self.check_cancelled()
        moving = self.native.get_is_moving()
        if moving is None:
            raise DriverFailed("MHS.DEVICE.FAULTED", "get_is_moving returned no state")
        actual = self.native.get_position()
        if actual is None or len(actual) < 3:
            raise DriverFailed("MHS.DEVICE.FAULTED", "get_position returned no position")
        return {
            "reached": not bool(moving),
            "position": {"x": float(actual[0]), "y": float(actual[1]), "z": float(actual[2])},
        }

    # -- extension actions ---------------------------------------------------------------------------------------
    @action(name="x-cap.idc-milab.tool_off.v1", safe_state=True,
            description="Turn the pump and the gripper off; this is the declared safe state because the upstream "
                        "API has no motion halt",
            output={"tool_off": Field("boolean",
                                      description="True when the pump and the gripper both confirmed off")})
    def tool_off(self):
        pump_ok = bool(self.native.set_pump(False))
        gripper_ok = bool(self.native.set_gripper(False))
        self._pump_on = False
        self._gripper_closed = False
        if not (pump_ok and gripper_ok):
            raise DriverFailed("MHS.DEVICE.FAULTED", "the pump or the gripper did not confirm off")
        return {"tool_off": True}

    # -- safety --------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """Turn the tool outputs off.  The clone has no native motion halt (facts.md)."""
        pump_ok = bool(self.native.set_pump(False))
        gripper_ok = bool(self.native.set_gripper(False))
        self._pump_on = False
        self._gripper_closed = False
        if not (pump_ok and gripper_ok):
            raise DriverFailed("MHS.DEVICE.FAULTED", "the pump or the gripper did not confirm off")

    # -- helpers --------------------------------------------------------------------------------------------------
    def _position(self):
        values = self.native.get_position()
        if values is None or len(values) < 3:
            raise DriverFailed("MHS.DEVICE.FAULTED", "get_position returned no position")
        return values

    def _polar(self):
        values = self.native.get_polar()
        if values is None or len(values) < 3:
            raise DriverFailed("MHS.DEVICE.FAULTED", "get_polar returned no polar coordinate")
        return values

    def _angle(self, servo_id):
        value = self.native.get_servo_angle(servo_id)
        if value is None:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"get_servo_angle({servo_id}) returned no angle")
        return float(value)

    def _set_angle(self, servo_id, value):
        if not self.native.set_servo_angle(servo_id, float(value), wait=True):
            raise DriverFailed("MHS.DEVICE.FAULTED", f"set_servo_angle({servo_id}) returned False")
        return self._angle(servo_id)

"""OpenMHS driver for gh.accelerationconsortium/opentrons-ot2: the Opentrons OT-2 motion controller.

A direct Driver (decorated methods) over the upstream class
``unitelabs.opentrons_ot2.io.motion:OT2MotionController``.  That class is a thin wrapper around the Opentrons
``SmoothieDriver`` and the OT-2 GPIO character device; it does not reimplement the serial protocol.  Every motion
method takes a mapping of axis letters (X, Y, Z, A, B, C) to absolute machine positions in millimetres and is a
coroutine, which the family method/result tables of ``PythonObjectDriver`` cannot express (driver-authoring.md,
"Choosing the shape").

* reads: the axis position in millimetres, the firmware version, the serial number, the attached pipette models and
  ids, the button and rail lights, the front button, the door switch and the simulator flag;
* writes: the RGB front-button light and the deck rail lights;
* actions: a standard Cartesian pose move of the left pipette mount (``cap.motion.cartesian_pose.v1``), an extension
  that moves all six axes at once, an extension that homes all axes, extension aspirate and dispense primitives, the
  extension halt that is also the declared safe state, and one input-free extension that re-enables the device after
  a halt;
* the native stop is ``OT2MotionController.stop``, which takes the controller's single hardware lock and then calls
  ``SmoothieDriver.hard_halt()`` (Opentrons code outside the clone).  A running move or home holds that lock, so the
  halt goes out once the runtime's cancellation of that action has released it.

Halt and recovery: the clone documents that the robot must be re-homed after an emergency stop, and its comments
show that later Smoothie replies after a halt are raised as errors and that the dependency's alarm path resets and
homes.  After any halt (an e-stop, the halt action, or the halt the runtime runs after a cancelled action) this
driver therefore sends no Smoothie command except the re-enable (M999 and a full home): motion actions are refused
``MHS.DEVICE.PRECONDITION_UNMET`` and the Smoothie-queried reads are left out of the state until the re-enable has
completed.  The flag lives in this process only.

The OT-2 clone publishes no deck envelope, no axis travel range, no pipette conversion factor and no flow-rate range
in a text file: the installed pipette and the robot's configuration decide them.  Every numeric action input is
therefore ``Limit.operator_required`` and is refused ``MHS.SAFETY.LIMITS_UNSET`` until the operator supplies the
values in ``site-limits.json`` (``site-limits.example.json`` is an example only).  The driver calls the controller
directly, so the SiLA feature layer's own software bounds check is not applied; only the operator overlay bounds a
move.  ``cap.fluid.aspirate.v1`` and ``cap.fluid.dispense.v1`` are not bound because they take labware/well names that
this native class cannot resolve; the extensions expose the native primitive and take the caller-owned ``ul_per_mm``
conversion explicitly.

Every Fact cites a line of the clone at the pinned commit 9ba663504dcf8b27eb1b9e777a84c01667202893.  This package is
model-authored and unreviewed: the loader refuses its R2 hardware backend until a human signs ``reviewed_by``, and
the acceptance gate exercises the fake backend only.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, OutcomeUnknown, action, estop, read, write

_AXES = ("X", "Y", "Z", "A", "B", "C")
_REENABLE = "x-cap.accelerationconsortium.reenable.v1"
_POSITION_PROPERTIES = {
    "x": Field("number", unit="mm", required=True, description="X gantry position in millimetres"),
    "y": Field("number", unit="mm", required=True, description="Y gantry position in millimetres"),
    "z": Field("number", unit="mm", required=True, description="Z left-mount position in millimetres"),
    "a": Field("number", unit="mm", required=True, description="A right-mount position in millimetres"),
    "b": Field("number", unit="mm", required=True, description="B left-plunger position in millimetres"),
    "c": Field("number", unit="mm", required=True, description="C right-plunger position in millimetres"),
}
_BUTTON_PROPERTIES = {
    "red": Field("boolean", required=True, description="Red channel of the front-button LED"),
    "green": Field("boolean", required=True, description="Green channel of the front-button LED"),
    "blue": Field("boolean", required=True, description="Blue channel of the front-button LED"),
}
_OPERATOR_X = ("no text file of the clone states the X travel of the configured OT-2; the site supplies the machine "
               "envelope")
_OPERATOR_Y = ("no text file of the clone states the Y travel of the configured OT-2; the site supplies the machine "
               "envelope")
_OPERATOR_Z = ("no text file of the clone states the Z travel of the configured OT-2; the site supplies the axis "
               "envelope")
_OPERATOR_VOLUME = ("no text file of the clone states the usable volume of the installed pipette; the site supplies "
                    "the tip and pipette volume range")
_OPERATOR_UL_PER_MM = ("the volume-to-plunger conversion depends on the attached pipette, which the clone leaves to "
                       "the caller; the site supplies the measured factor, greater than zero")
_OPERATOR_FLOW = ("no text file of the clone states a flow-rate range for the installed pipette; the site supplies "
                  "it")
_AFTER_HALT = ("absent after a halt until the re-enable has completed (no Smoothie query is sent then)")


class OpentronsOT2(Driver):
    device_id = "ot2"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    native = "unitelabs.opentrons_ot2.io.motion:OT2MotionController"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeOT2MotionController"}
    vendor, model = "Opentrons", "OT-2"
    display_name = "Opentrons OT-2 motion controller (OT2MotionController)"
    tags = ["opentrons", "ot-2", "liquid-handler", "gantry", "pipette", "motion", "asyncio"]
    facts = [
        Fact("OT2MotionController is a thin wrapper around the existing Opentrons driver classes; it does not "
             "reimplement the low-level serial communication", source="upstream_code",
             ref="src/unitelabs/opentrons_ot2/io/motion.py:1-11"),
        Fact("The controller serializes hardware calls on one asyncio.Lock, wrapped in a _TimedLock with "
             "lock_timeout_s, because the SmoothieDriver has a single serial connection", source="upstream_code",
             ref="src/unitelabs/opentrons_ot2/io/motion.py:223-226"),
        Fact("stop() is documented as an emergency stop that halts all motion: it acquires that lock and then calls "
             "SmoothieDriver.hard_halt(); the clone does not implement hard_halt itself", source="upstream_code",
             ref="src/unitelabs/opentrons_ot2/io/motion.py:775-778"),
        Fact("move(target, speed=None) awaits SmoothieDriver.move while it holds the lock; target maps axes to "
             "positions and speed is in mm/sec", source="upstream_code",
             ref="src/unitelabs/opentrons_ot2/io/motion.py:450-468"),
        Fact("move_through documents its targets as axis letters mapped to absolute mm and its speeds in mm/sec",
             source="upstream_code", ref="src/unitelabs/opentrons_ot2/io/motion.py:512-514"),
        Fact("home(axes) holds the lock while it homes the gantry and mount axes together and then each plunger axis "
             "B/C on its own at the attached pipette's run current or a safe default, because the bare driver would "
             "home a plunger at the 0.05 A idle current, which lacks the torque to reach the endstop",
             source="upstream_code", ref="src/unitelabs/opentrons_ot2/io/motion.py:387-418"),
        Fact("get_position() calls SmoothieDriver.update_position while it holds the lock and returns the updated "
             "cached position", source="upstream_code",
             ref="src/unitelabs/opentrons_ot2/io/motion.py:647-655"),
        Fact("aspirate moves the plunger axis up from its cached position by volume_ul / ul_per_mm at "
             "flow_rate_ul_s / ul_per_mm mm/s while it holds the lock; the caller must first place the plunger at "
             "its bottom", source="upstream_code", ref="src/unitelabs/opentrons_ot2/io/motion.py:683-695"),
        Fact("dispense moves the plunger axis down from its cached position by volume_ul / ul_per_mm at "
             "flow_rate_ul_s / ul_per_mm mm/s while it holds the lock", source="upstream_code",
             ref="src/unitelabs/opentrons_ot2/io/motion.py:705-716"),
        Fact("reset_from_error() clears the alarm lock with M999 and smoothie_reset() performs a full GPIO reset of "
             "the Smoothie, each while holding the lock", source="upstream_code",
             ref="src/unitelabs/opentrons_ot2/io/motion.py:890-898"),
        Fact("After reset_from_error or smoothie_reset the homed flags are all false and the operator must re-home "
             "before moving; smoothie_reset is the more drastic GPIO pulse and reset_from_error is preferred for "
             "alarm recovery", source="vendor_doc", ref="alarm_reset_plan.md:37-38"),
        Fact("The clone's plan states that no reliable alarm-state signal is available without modifying the driver "
             "and that all-false homed flags cannot be told apart from a robot not homed since boot",
             source="vendor_doc", ref="alarm_reset_plan.md:35-36"),
        Fact("read_pipette_model(mount) and read_pipette_id(mount) read the pipette EEPROM while holding the lock "
             "and return an empty string when nothing is read (no pipette attached, or an unreadable id)",
             source="upstream_code", ref="src/unitelabs/opentrons_ot2/io/motion.py:746-756"),
        Fact("set_button_light sets the RGB front-button LED, set_rail_lights switches the deck rail lights, "
             "get_button_light returns an (r, g, b) tuple, get_rail_lights a bool, and read_button and "
             "read_door_switch return the front-button and door-switch states", source="upstream_code",
             ref="src/unitelabs/opentrons_ot2/io/motion.py:790-849"),
        Fact("get_serial_number reads /var/serial and returns an empty string when it is unavailable",
             source="upstream_code", ref="src/unitelabs/opentrons_ot2/io/motion.py:373-378"),
        Fact("get_firmware_version queries the Smoothie firmware version", source="upstream_code",
             ref="src/unitelabs/opentrons_ot2/io/motion.py:853-856"),
        Fact("is_simulating reports the SmoothieDriver.simulating flag", source="upstream_code",
             ref="src/unitelabs/opentrons_ot2/io/motion.py:348-351"),
        Fact("build(port, simulate=False) sets up the GPIO character device and builds a _RaisingSmoothieDriver on "
             "the serial port; simulate=True builds a simulating GPIO and a SmoothieDriver without a connection",
             source="upstream_code", ref="src/unitelabs/opentrons_ot2/io/motion.py:228-278"),
        Fact("_RaisingSmoothieDriver raises SmoothieAlarm on the first alarm reply while a hard halt is set (and "
             "clears it) and SmoothieError on an error reply then; outside a hard halt it raises SmoothieError on "
             "every alarm or error reply, including the 'alarm lock' and 'after halt you should home' replies that "
             "the upstream driver swallows", source="upstream_code",
             ref="src/unitelabs/opentrons_ot2/io/motion.py:82-103"),
        Fact("A comment in move_through states that after a mid-line alarm the alarm path inside _send_command has "
             "already reset and homed", source="upstream_code",
             ref="src/unitelabs/opentrons_ot2/io/motion.py:537-543"),
        Fact("The OT-2 axes are X, Y, Z, A, B and C: X is the gantry, Y moves toward the front window when "
             "negative, Z/A are the left/right mount vertical axes and B/C the left/right plungers; each axis has "
             "its limit switch at its positive end", source="upstream_code",
             ref="src/unitelabs/opentrons_ot2/features/motion_control.py:180-185"),
        Fact("A feature-layer comment states that Opentrons provides no fixed floor for the Z/A mount axes "
             "(HOMED_POSITION defines only the top) and that a replayed robot-server request executed a machine "
             "position below 0 (-21.44 mm) without error", source="upstream_code",
             ref="src/unitelabs/opentrons_ot2/features/motion_control.py:100-105"),
        Fact("The clone's feature layer states that the physical limit switches are the real safety boundary for "
             "Z/A and that no synthetic software floor is enforced there; the X/Y 0.0 floor is marked untested",
             source="upstream_code", ref="src/unitelabs/opentrons_ot2/features/motion_control.py:519-526"),
        Fact("The feature layer's _check_bounds refuses a position outside the controller's axis_bounds maximum or "
             "the feature's lower limit for the axis", source="upstream_code",
             ref="src/unitelabs/opentrons_ot2/features/motion_control.py:543-549"),
        Fact("The feature layer's emergency_stop is documented to immediately halt all motion; it calls the "
             "controller stop and returns 'Emergency stop executed. Re-home required before resuming.'",
             source="upstream_code", ref="src/unitelabs/opentrons_ot2/features/motion_control.py:486-496"),
        Fact("The upstream simulation tests state that in simulation emergency_stop sets an internal flag only, with "
             "no actual halt, and that pause and resume do nothing", source="upstream_code",
             ref="tests/features/test_motion_simulation.py:16-19"),
        Fact("The module imports opentrons.drivers.smoothie_drivers.driver_3_0.SmoothieDriver; the hard-halt and "
             "serial details are in that dependency and are not shown in the clone", source="upstream_code",
             ref="src/unitelabs/opentrons_ot2/io/motion.py:24"),
        Fact("The clone depends on opentrons 8.8.1 below Python 3.12 and on opentrons 9.0.0 from Python 3.12",
             source="upstream_code", ref="pyproject.toml:27-28"),
    ]
    safe_state = ("OT2MotionController.stop() has returned: it called SmoothieDriver.hard_halt() (Opentrons code "
                  "outside the clone) once the controller lock was free, which a running move or home releases only "
                  "when its cancellation ends it; nothing senses standstill. The driver then sends no Smoothie "
                  "command except the re-enable (M999 and a full home of all six axes): motion actions are refused "
                  "PRECONDITION_UNMET and the position, firmware and pipette reads are absent until it completes")

    #: True after any halt until a re-enable completes; set before the native stop is called.
    _ot2_halted = False
    #: Counts the halts, so that a re-enable or a move overlapped by a halt never reports a clean end.
    _ot2_halt_epoch = 0

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("simulating", type="boolean",
          description="True when the backend drives the Opentrons simulator instead of the Smoothie hardware")
    def simulating(self):
        return bool(self.native.is_simulating)

    @read("position", type="object", properties=_POSITION_PROPERTIES,
          description="Axis machine position in millimetres from get_position(), which queries the Smoothie and "
                      "returns the controller's cached position; " + _AFTER_HALT)
    async def position(self):
        if self._ot2_halted:
            return None
        return _position_document(await self.native.get_position())

    @read("firmware_version", type="string", description="Smoothie firmware version; " + _AFTER_HALT)
    async def firmware_version(self):
        if self._ot2_halted:
            return None
        return await self.native.get_firmware_version()

    @read("serial_number", type="string", description="OT-2 serial number read from /var/serial")
    async def serial_number(self):
        return await self.native.get_serial_number()

    @read("pipette_left_model", type="string",
          description="Model string of the pipette on the left mount; " + _AFTER_HALT)
    async def pipette_left_model(self):
        if self._ot2_halted:
            return None
        return await self.native.read_pipette_model("left")

    @read("pipette_left_id", type="string", description="Unique id of the pipette on the left mount; " + _AFTER_HALT)
    async def pipette_left_id(self):
        if self._ot2_halted:
            return None
        return await self.native.read_pipette_id("left")

    @read("pipette_right_model", type="string",
          description="Model string of the pipette on the right mount; " + _AFTER_HALT)
    async def pipette_right_model(self):
        if self._ot2_halted:
            return None
        return await self.native.read_pipette_model("right")

    @read("pipette_right_id", type="string",
          description="Unique id of the pipette on the right mount; " + _AFTER_HALT)
    async def pipette_right_id(self):
        if self._ot2_halted:
            return None
        return await self.native.read_pipette_id("right")

    @read("button_light", type="object", properties=_BUTTON_PROPERTIES,
          description="Current RGB state of the front-button LED")
    def button_light(self):
        red, green, blue = self.native.get_button_light()
        return {"red": bool(red), "green": bool(green), "blue": bool(blue)}

    @read("rail_lights", type="boolean", description="True while the deck rail lights are on")
    def rail_lights(self):
        return bool(self.native.get_rail_lights())

    @read("button_pressed", type="boolean", description="True while the front button is pressed")
    def button_pressed(self):
        return bool(self.native.read_button())

    @read("door_closed", type="boolean", description="True while the door/window switch reports the door closed")
    def door_closed(self):
        return bool(self.native.read_door_switch())

    # -- writes --------------------------------------------------------------------------------------------------
    @write("button_light", type="object", properties=_BUTTON_PROPERTIES,
           description="Set the RGB front-button LED; all three channels are applied together")
    def set_button_light(self, value):
        red, green, blue = bool(value["red"]), bool(value["green"]), bool(value["blue"])
        self.native.set_button_light(red=red, green=green, blue=blue)
        return {"red": red, "green": green, "blue": blue}

    @write("rail_lights", type="boolean", description="Switch the deck rail lights on or off")
    def set_rail_lights(self, value):
        self.native.set_rail_lights(on=bool(value))
        return bool(value)

    # -- actions -------------------------------------------------------------------------------------------------
    @action(cap="cap.motion.cartesian_pose.v1",
            input={"position": Field("object", description="Absolute machine position of the left pipette mount "
                                                            "(Smoothie axes X, Y and Z) in millimetres; the OT-2 has "
                                                            "no wrist, so no orientation is accepted",
                                     properties={
                                         "x": Field("number", unit="mm", required=True,
                                                    description="Smoothie X (gantry) axis position in millimetres"),
                                         "y": Field("number", unit="mm", required=True,
                                                    description="Smoothie Y (gantry) axis position in millimetres"),
                                         "z": Field("number", unit="mm", required=True,
                                                    description="Smoothie Z (left mount) axis position in "
                                                                "millimetres"),
                                     })},
            limits={"position.x": Limit.operator_required(_OPERATOR_X),
                    "position.y": Limit.operator_required(_OPERATOR_Y),
                    "position.z": Limit.operator_required(_OPERATOR_Z)},
            cancellable=True,
            description="Move the left pipette mount to an absolute X/Y/Z machine position in millimetres with the "
                        "native move(); positions outside the operator envelope are refused before any native call, "
                        "and the move is refused PRECONDITION_UNMET after a halt until the re-enable")
    async def cartesian_pose(self, position):
        epoch = _refuse_after_halt(self, "the Cartesian move")
        target = {"X": float(position["x"]), "Y": float(position["y"]), "Z": float(position["z"])}
        await self.native.move(target=target)
        _unknown_if_halted(self, epoch, "the Cartesian move")
        current = _position_document(await self.native.get_position())
        return {"reached": True, "position": {axis: current[axis] for axis in ("x", "y", "z")}}

    @action(name="x-cap.accelerationconsortium.move_axes.v1",
            long_running=True, max_duration_ms=120000, cancellable=True,
            input={
                "x": Field("number", unit="mm", description="Absolute X gantry machine position in millimetres",
                           limit=Limit.operator_required(_OPERATOR_X)),
                "y": Field("number", unit="mm", description="Absolute Y gantry machine position in millimetres",
                           limit=Limit.operator_required(_OPERATOR_Y)),
                "z": Field("number", unit="mm", description="Absolute Z left-mount machine position in millimetres",
                           limit=Limit.operator_required(_OPERATOR_Z)),
                "a": Field("number", unit="mm", description="Absolute A right-mount machine position in millimetres",
                           limit=Limit.operator_required(
                               "no text file of the clone states the A travel of the configured OT-2; the site "
                               "supplies the axis envelope")),
                "b": Field("number", unit="mm", description="Absolute B left-plunger position in millimetres",
                           limit=Limit.operator_required(
                               "no text file of the clone states the B plunger travel of the configured OT-2; the "
                               "site supplies the axis envelope")),
                "c": Field("number", unit="mm", description="Absolute C right-plunger position in millimetres",
                           limit=Limit.operator_required(
                               "no text file of the clone states the C plunger travel of the configured OT-2; the "
                               "site supplies the axis envelope")),
            },
            output={"reached": Field("boolean", description="True once the native move() returned"),
                    "position": Field("object", description="Axis position in millimetres after the move",
                                      properties=_POSITION_PROPERTIES)},
            description="Move all six OT-2 axes to absolute machine positions in millimetres with the native "
                        "move(); refused PRECONDITION_UNMET after a halt until the re-enable")
    async def move_axes(self, x, y, z, a, b, c):
        epoch = _refuse_after_halt(self, "the six-axis move")
        await self.native.move(target={"X": float(x), "Y": float(y), "Z": float(z),
                                       "A": float(a), "B": float(b), "C": float(c)})
        _unknown_if_halted(self, epoch, "the six-axis move")
        return {"reached": True, "position": _position_document(await self.native.get_position())}

    @action(name="x-cap.accelerationconsortium.home_all.v1",
            long_running=True, max_duration_ms=300000, cancellable=True,
            output={"homed": Field("boolean", description="True once the full native home(axes='XYZABC') returned")},
            description="Home all six OT-2 axes with the native home(); refused PRECONDITION_UNMET after a halt, "
                        "when the re-enable (which clears the alarm lock and then homes) is the way back")
    async def home_all(self):
        _refuse_after_halt(self, "the full home")
        await self.native.home(axes="XYZABC")
        return {"homed": True}

    @action(name="x-cap.accelerationconsortium.aspirate.v1",
            long_running=True, max_duration_ms=60000, cancellable=True,
            input={
                "axis": Field("string", enum=["B", "C"],
                              description="Plunger axis: B is the left mount, C the right mount"),
                "volume_ul": Field("number", unit="uL", description="Volume to draw into the tip",
                                   limit=Limit.operator_required(_OPERATOR_VOLUME)),
                "ul_per_mm": Field("number", unit="uL/mm",
                                   description="Caller-owned pipette conversion factor: microlitres per plunger "
                                               "millimetre",
                                   limit=Limit.operator_required(_OPERATOR_UL_PER_MM)),
                "flow_rate_ul_s": Field("number", unit="uL/s", description="Aspiration flow rate",
                                        limit=Limit.operator_required(_OPERATOR_FLOW)),
            },
            output={"aspirated_volume": Field("number", unit="uL", description="Volume sent to the native aspirate"),
                    "axis": Field("string", description="Plunger axis used"),
                    "position": Field("object", description="Axis position in millimetres after the move",
                                      properties=_POSITION_PROPERTIES)},
            description="Draw liquid with the native aspirate(axis, volume_ul, ul_per_mm, flow_rate_ul_s); the "
                        "caller supplies the pipette conversion and the plunger must already be at its bottom; "
                        "refused PRECONDITION_UNMET after a halt until the re-enable")
    async def aspirate(self, axis, volume_ul, ul_per_mm, flow_rate_ul_s):
        epoch = _refuse_after_halt(self, "the aspirate")
        _check_conversion(ul_per_mm)
        await self.native.aspirate(axis=axis, volume_ul=volume_ul, ul_per_mm=ul_per_mm,
                                   flow_rate_ul_s=flow_rate_ul_s)
        _unknown_if_halted(self, epoch, "the aspirate")
        return {"aspirated_volume": volume_ul, "axis": axis,
                "position": _position_document(await self.native.get_position())}

    @action(name="x-cap.accelerationconsortium.dispense.v1",
            long_running=True, max_duration_ms=60000, cancellable=True,
            input={
                "axis": Field("string", enum=["B", "C"],
                              description="Plunger axis: B is the left mount, C the right mount"),
                "volume_ul": Field("number", unit="uL", description="Volume to expel from the tip",
                                   limit=Limit.operator_required(_OPERATOR_VOLUME)),
                "ul_per_mm": Field("number", unit="uL/mm",
                                   description="Caller-owned pipette conversion factor: microlitres per plunger "
                                               "millimetre",
                                   limit=Limit.operator_required(_OPERATOR_UL_PER_MM)),
                "flow_rate_ul_s": Field("number", unit="uL/s", description="Dispense flow rate",
                                        limit=Limit.operator_required(_OPERATOR_FLOW)),
            },
            output={"dispensed_volume": Field("number", unit="uL", description="Volume sent to the native dispense"),
                    "axis": Field("string", description="Plunger axis used"),
                    "position": Field("object", description="Axis position in millimetres after the move",
                                      properties=_POSITION_PROPERTIES)},
            description="Expel liquid with the native dispense(axis, volume_ul, ul_per_mm, flow_rate_ul_s); the "
                        "caller supplies the pipette conversion; refused PRECONDITION_UNMET after a halt until the "
                        "re-enable")
    async def dispense(self, axis, volume_ul, ul_per_mm, flow_rate_ul_s):
        epoch = _refuse_after_halt(self, "the dispense")
        _check_conversion(ul_per_mm)
        await self.native.dispense(axis=axis, volume_ul=volume_ul, ul_per_mm=ul_per_mm,
                                   flow_rate_ul_s=flow_rate_ul_s)
        _unknown_if_halted(self, epoch, "the dispense")
        return {"dispensed_volume": volume_ul, "axis": axis,
                "position": _position_document(await self.native.get_position())}

    @action(name="x-cap.accelerationconsortium.halt_motion.v1", safe_state=True,
            output={"stopped": Field("boolean", description="True once the native stop() (hard halt) returned")},
            description="Halt all motion with the native stop() (SmoothieDriver.hard_halt, after the controller "
                        "lock is free); it takes no input, is the declared safe state, and leaves the driver "
                        "refusing motion until the re-enable")
    async def halt_motion(self):
        _mark_halted(self)
        await self.native.stop()
        return {"stopped": True}

    @action(name=_REENABLE, reenable=True,
            long_running=True, max_duration_ms=300000, cancellable=True,
            output={"reenabled": Field("boolean", description="True once the alarm lock was cleared"),
                    "homed": Field("boolean", description="True once the full re-home returned")},
            description="Recovery after a halt (an e-stop, the halt action or a cancelled action): clear the "
                        "Smoothie alarm lock with reset_from_error() (M999) and re-home all six axes; it takes no "
                        "input, is refused while latched, and is the only Smoothie command the driver sends after "
                        "a halt")
    async def reenable(self):
        epoch = self._ot2_halt_epoch
        await self.native.reset_from_error()
        await self.native.home(axes="XYZABC")
        _unknown_if_halted(self, epoch, "the re-enable")
        self._ot2_halted = False
        return {"reenabled": True, "homed": True}

    # -- safety --------------------------------------------------------------------------------------------------
    @estop
    async def stop(self):
        """The native stop: the runtime latches first; this marks the driver halted and calls stop(), which takes
        the controller lock and then calls SmoothieDriver.hard_halt (motion.py:775-778)."""
        _mark_halted(self)
        await self.native.stop()

    async def teardown(self):
        await self.native.disconnect()


def _mark_halted(driver):
    """Record a halt before the native stop is called: from now on only the re-enable reaches the Smoothie."""
    driver._ot2_halted = True
    driver._ot2_halt_epoch = driver._ot2_halt_epoch + 1


def _refuse_after_halt(driver, what):
    """Refuse a Smoothie motion command after a halt; return the halt count seen before the native call."""
    if driver._ot2_halted:
        raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                           f"{what} is refused: the OT-2 was halted (e-stop, halt action or a cancelled action) and "
                           f"must be re-homed first; send {_REENABLE} (M999 and a full home)")
    return driver._ot2_halt_epoch


def _unknown_if_halted(driver, epoch, what):
    """A halt landed while the native call ran: its end state is not observed and nothing more is sent."""
    if driver._ot2_halt_epoch != epoch:
        raise OutcomeUnknown(f"the OT-2 was halted while {what} ran; its end state is not observed and nothing "
                             f"more is sent to the Smoothie until {_REENABLE} completes")


def _position_document(position):
    """Convert the native axis-letter mapping to the lowercase state document, without filling missing axes."""
    return {axis.lower(): float(position[axis]) for axis in _AXES}


def _check_conversion(ul_per_mm):
    """Refuse a zero or negative conversion before the native divides by it."""
    if float(ul_per_mm) <= 0:
        raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                           "ul_per_mm must be greater than zero; set the installed pipette's measured factor")

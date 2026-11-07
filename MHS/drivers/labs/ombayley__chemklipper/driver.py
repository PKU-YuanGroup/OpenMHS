"""OpenMHS driver for gh.ombayley/chemklipper: the CoreXY gantry of a Klipper liquid handler.

A direct Driver (decorated methods) over ``chem_klipper.devices.gantry:Gantry``.  The upstream class talks to
Moonraker over a WebSocket and wraps the motion calls of a Klipper printer; every method is a coroutine function,
so every method here is ``async def`` and awaits ``self.native``.

* reads: the live position, the commanded position, the Klipper printer state and the Moonraker connection flag;
* actions: home all axes (``G28``), move to a Cartesian X/Y/Z point in millimetres (``G0``) and stop motion
  (``M18``);
* the native stop is ``disable_motors`` (``M18``); it is the e-stop and, as the
  ``x-cap.ombayley.stop_motion.v1`` action, the safe-state action.  The bring-up guide also tells the operator to
  keep a hand near the power switch or emergency stop (``estop_physical_ref``).

The card also lists ``chem_klipper.devices.pump:Pump``.  Its ``aspirate``, ``dispense``, ``refill`` and ``empty``
methods are empty ``pass`` bodies in the clone (``src/chem_klipper/devices/pump.py:57-67``), so this package does
not pretend to expose liquid handling: only the gantry is driven.

The clone has no standard linear Cartesian motion class for a ``motion.axis`` resource.
``cap.motion.joint_position.v1`` expresses joint positions in radians, while this gantry reports millimetres.  The
standard ``cap.motion.home.v1`` and ``cap.motion.stop.v1`` classes also carry optional numeric fields
(``speed_scale`` and ``deceleration``) that the upstream ``home`` and ``disable_motors`` methods do not implement;
serving those classes would offer inputs that cannot reach the device.  The three motions therefore use extension ids
with inline schemas.  The workspace bounds of a Klipper machine are set by its ``printer.cfg``, not by the class, so
every coordinate is ``Limit.operator_required`` until the site overlay supplies the workspace
(``site-limits.example.json`` shows the shape).

Every Fact cites a line of the clone at the pinned commit (e88503106b481ad12a2469b3dbe991c18186e650).  This
package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read


class ChemKlipperGantry(Driver):
    device_id = "chemklipper-gantry"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R2"
    native = "chem_klipper.devices.gantry:Gantry"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeGantry"}
    display_name = "ChemKlipper CoreXY gantry (chem_klipper.devices.gantry:Gantry)"
    tags = ["gantry", "corexy", "klipper", "motion", "asyncio"]
    facts = [
        Fact("The gantry sends G-code through printer.gcode.script and reads motion state through "
             "printer.objects.query", source="upstream_code",
             ref="src/chem_klipper/devices/gantry.py:34-36"),
        Fact("get_target_position queries gcode_move and returns its position keyed by axis_map",
             source="upstream_code", ref="src/chem_klipper/devices/gantry.py:44-53"),
        Fact("get_current_position queries motion_report and returns live_position indexed X, Y, Z and E",
             source="upstream_code", ref="src/chem_klipper/devices/gantry.py:55-64"),
        Fact("The gantry module sets MIN_STEPPER_CURRENT = 0.10, MAX_STEPPER_CURRENT = 1.00, "
             "DEFAULT_MOVE_TIMEOUT = 180.0, POSITION_TOLERANCE = 0.001 and DEFAULT_MOVE_SPEED = 20.0",
             source="upstream_code", ref="src/chem_klipper/devices/gantry.py:20-24"),
        Fact("wait_for_move polls the live position until every tracked axis is within the tolerance or the "
             "timeout expires", source="upstream_code",
             ref="src/chem_klipper/devices/gantry.py:68-83"),
        Fact("Gantry.move sends the XY move and the Z move as separate G0 commands and waits after each",
             source="upstream_code", ref="src/chem_klipper/devices/gantry.py:111-173"),
        Fact("home() sends G28 (or SET_KINEMATIC_POSITION X=0 Y=0 Z=0 when debug is true) and raises MotionError "
             "when the reply is not 'ok'", source="upstream_code",
             ref="src/chem_klipper/devices/gantry.py:99-109"),
        Fact("enable_motors sends M17 and disable_motors sends M18", source="upstream_code",
             ref="src/chem_klipper/devices/gantry.py:175-182"),
        Fact("get_status reads printer.info and returns its 'state' value", source="upstream_code",
             ref="src/chem_klipper/devices/moonraker_device.py:60-65"),
        Fact("is_connected is true only while the Moonraker WebSocket is open", source="upstream_code",
             ref="src/chem_klipper/moonraker.py:84-87"),
        Fact("The gantry and deck configuration express distances in millimetres (_mm keys) with a default speed "
             "of 100 mm/s", source="upstream_code", ref="config/lh_device.yaml:7-33"),
        Fact("The bring-up guide tells the operator to keep a hand near the power switch or emergency stop before "
             "any motion", source="vendor_doc", ref="docs/user-guide/08-testing.md:15-18"),
        Fact("The example printer configuration wires the x_max and y_max switches to M112, an emergency stop",
             source="vendor_doc", ref="docs/user-guide/05-klipper-config.md:172-180"),
        Fact("The guide says the example travel limits and driver currents must be reviewed against the actual "
             "machine and are a starting point, not a substitute for calibration", source="vendor_doc",
             ref="docs/user-guide/05-klipper-config.md:230-243"),
    ]
    safe_state = "Gantry motors de-energised (M18); no axis is driven while the latch is engaged"
    estop_physical_ref = "docs/user-guide/08-testing.md:18"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("connected", type="boolean", description="True while the Moonraker WebSocket is open")
    def connected(self):
        return bool(self.native.is_connected)

    @read("status", type="string", description="Klipper printer state reported by Moonraker")
    async def status(self):
        return await self.native.get_status()

    @read("position", type="object",
          properties={
              "x": Field("number", unit="mm", description="Live X position"),
              "y": Field("number", unit="mm", description="Live Y position"),
              "z": Field("number", unit="mm", description="Live Z position"),
          },
          description="Live motion-report position of the gantry")
    async def position(self):
        current = await self.native.get_current_position()
        return {"x": current["X"], "y": current["Y"], "z": current["Z"]}

    @read("target_position", type="object",
          properties={
              "x": Field("number", unit="mm", description="Commanded X position"),
              "y": Field("number", unit="mm", description="Commanded Y position"),
              "z": Field("number", unit="mm", description="Commanded Z position"),
          },
          description="Commanded G-code position of the gantry")
    async def target_position(self):
        target = await self.native.get_target_position()
        return {"x": target["X"], "y": target["Y"], "z": target["Z"]}

    # -- actions -----------------------------------------------------------------------------------------------
    @action(name="x-cap.ombayley.home_gantry.v1",
            description="Home all gantry axes with the native G28",
            output={"homed": Field("boolean", description="True once the native home call returned")})
    async def home_gantry(self):
        await self.native.home()
        return {"homed": True}

    @action(
        name="x-cap.ombayley.move_cartesian.v1",
        description="Move the gantry to a Cartesian X/Y/Z point in millimetres",
        input={
            "x": Field("number", unit="mm", description="Target X coordinate",
                       limit=Limit.operator_required(
                           "the X workspace is set by the machine's printer.cfg and deck; no text file states "
                           "the travel of this unit")),
            "y": Field("number", unit="mm", description="Target Y coordinate",
                       limit=Limit.operator_required(
                           "the Y workspace is set by the machine's printer.cfg and deck; no text file states "
                           "the travel of this unit")),
            "z": Field("number", unit="mm", description="Target Z coordinate",
                       limit=Limit.operator_required(
                           "the Z workspace is set by the machine's printer.cfg and probe; no text file states "
                           "the travel of this unit")),
        },
        output={
            "reached": Field("boolean", description="True when the live position is at the commanded position"),
            "position": Field("object",
                              properties={
                                  "x": Field("number", unit="mm", description="Live X position after the move"),
                                  "y": Field("number", unit="mm", description="Live Y position after the move"),
                                  "z": Field("number", unit="mm", description="Live Z position after the move"),
                              },
                              description="Live position after the move"),
        },
    )
    async def move_cartesian(self, x, y, z):
        await self.native.move(x=x, y=y, z=z)
        current = await self.native.get_current_position()
        target = await self.native.get_target_position()
        reached = all(
            abs(current[axis] - target[axis]) <= 0.001 for axis in ("X", "Y", "Z")
        )
        return {"reached": reached,
                "position": {"x": current["X"], "y": current["Y"], "z": current["Z"]}}

    @action(name="x-cap.ombayley.stop_motion.v1", safe_state=True,
            description="De-energise the gantry motors (M18), the native safe state",
            output={
                "stopped": Field("boolean", description="True once the native stop call returned"),
                "stopped_position": Field("object",
                                          properties={
                                              "x": Field("number", unit="mm", description="Live X position at the stop"),
                                              "y": Field("number", unit="mm", description="Live Y position at the stop"),
                                              "z": Field("number", unit="mm", description="Live Z position at the stop"),
                                          },
                                          description="Live position at the stop"),
            })
    async def stop_motion(self):
        await self.native.disable_motors()
        current = await self.native.get_current_position()
        return {"stopped": True,
                "stopped_position": {"x": current["X"], "y": current["Y"], "z": current["Z"]}}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop(native="disable_motors")
    async def stop(self):
        """The native stop: the runtime latches first, then de-energises the motors with M18."""
        await self.native.disable_motors()

    async def teardown(self):
        await self.native.disconnect()

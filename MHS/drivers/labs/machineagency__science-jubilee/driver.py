"""OpenMHS driver for gh.machineagency/science-jubilee: a Jubilee multi-tool motion platform.

A direct Driver (decorated methods) over the upstream device class
``science_jubilee.Machine:Machine``.  The upstream class sends G-code over the Duet HTTP API; it is a
four-axis Cartesian platform (X, Y, Z and the toolchanger U axis) whose travel range comes from the
machine's own ``config.g`` and is read back with ``M409 K"move.axes"``.  The clone states no universal
travel range, so the position and tool-offset bounds are ``Limit.operator_required``: every move is
refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies its working envelope in ``site-limits.json``
(``site-limits.example.json`` shows the overlay).

* reads: the X, Y and Z control-point positions from ``Machine.get_position()`` in mm;
* actions: ``move_to`` (``cap.motion.cartesian_pose.v1``), ``home`` (``cap.motion.home.v1``) and the
  extension ``x-cap.machineagency.set_tool_offset.v1`` for the G10 tool offsets;
* the native stop is the Duet ``M112`` emergency stop.  The clone documents an independent hardware
  e-stop: the tool-ball trigger configured in the Duet as an emergency stop (same effect as ``M112``).

Every Fact cites a line of the clone at the pinned commit
(bb918fa78f300f57cc379a80731cfca7bdb55c66).  This package is model-authored and unreviewed: its
evidence is the fake-backend contract check, never an MHS-Device level, and it was never run on
hardware.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read


def _travel_limit(axis):
    """The operator supplies the travel envelope; the clone only says the range is machine configuration."""
    return Limit.operator_required(
        "the travel range is read from the machine's own config (Machine.py:397-426); the demo config "
        "sets M208 axis limits (docs/gcode/color_mixing_demo_config.g:132-133) and tool offsets shift the "
        f"coordinates (docs/getting_started/primer.md:72), so the site sets the working {axis} range")


class ScienceJubilee(Driver):
    device_id = "science-jubilee"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    native = "science_jubilee.Machine:Machine"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeMachine"}
    vendor, model = "Machine Agency", "Science Jubilee"
    display_name = "Science Jubilee motion platform (science_jubilee.Machine.Machine)"
    tags = ["jubilee", "motion", "gantry", "tool changer", "gcode", "duet"]
    facts = [
        Fact("Machine.gcode() posts each G-code command to http://{address}/machine/code", source="upstream_code",
             ref="src/science_jubilee/Machine.py:491-494"),
        Fact("get_position() asks the Duet for M114 and returns the machine control point in mm keyed by axis",
             source="upstream_code", ref="src/science_jubilee/Machine.py:1042-1070"),
        Fact("move_to() selects absolute positioning and calls _move_xyzev with x, y, z, e, v and the speed s",
             source="upstream_code", ref="src/science_jubilee/Machine.py:801-830"),
        Fact("_move_xyzev formats each coordinate with two decimals and sends a G0 command; wait=True follows "
             "with M400", source="upstream_code", ref="src/science_jubilee/Machine.py:771-799"),
        Fact("set_tool_offset() requires a tool index, formats each offset with two decimals and sends a G10 command",
             source="upstream_code", ref="src/science_jubilee/Machine.py:721-741"),
        Fact("home_all() parks the active tool when one is selected, sends G28 and marks X, Y, Z and U homed",
             source="upstream_code", ref="src/science_jubilee/Machine.py:652-663"),
        Fact("home_z() asks the operator to confirm that the deck is free before sending G28 Z",
             source="upstream_code", ref="src/science_jubilee/Machine.py:697-706"),
        Fact("The axis travel range is read from the Duet object model M409 move.axes as a min/max pair per axis",
             source="upstream_code", ref="src/science_jubilee/Machine.py:397-426"),
        Fact("Jubilee has four axes by default: the X, Y and Z dimensional axes and the toolchanger U axis",
             source="vendor_doc", ref="docs/getting_started/primer.md:24"),
        Fact("By default the machine uses millimetres", source="vendor_doc",
             ref="docs/getting_started/primer.md:12"),
        Fact("The demo machine configuration sets software axis limits M208 X-13.75:313.75 Y-44:341 Z0:300 and "
             "M208 U0:200", source="vendor_doc", ref="docs/gcode/color_mixing_demo_config.g:132-133"),
        Fact("Tool offsets shift the usable coordinate range: a tool with a Z offset of 50 moves from Z-50 to "
             "Z250 while the firmware keeps motion inside the 300x300x300 mm build volume", source="vendor_doc",
             ref="docs/getting_started/primer.md:72"),
        Fact("The clone documents the tool-ball crash trigger as an emergency stop that disables the steppers and "
             "resets the board, the same as the M112 G-code", source="vendor_doc",
             ref="docs/building/tool_crash_detection.md:73"),
    ]
    safe_state = "steppers disabled and the controller reset by the M112 emergency stop"
    estop_physical_ref = "docs/building/tool_crash_detection.md:73"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("x_position", unit="mm", description="Machine control-point X position")
    def x_position(self):
        return float(self.native.get_position()["X"])

    @read("y_position", unit="mm", description="Machine control-point Y position")
    def y_position(self):
        return float(self.native.get_position()["Y"])

    @read("z_position", unit="mm", description="Machine control-point Z position")
    def z_position(self):
        return float(self.native.get_position()["Z"])

    # -- actions ----------------------------------------------------------------------------------------------
    @action(cap="cap.motion.cartesian_pose.v1",
            description="Move the tool centre point to an absolute X/Y/Z position in the machine frame",
            input={"position": Field(
                "object", description="Target position of the machine control point in mm",
                properties={
                    "x": Field("number", unit="mm", description="Target X position", limit=_travel_limit("X")),
                    "y": Field("number", unit="mm", description="Target Y position", limit=_travel_limit("Y")),
                    "z": Field("number", unit="mm", description="Target Z position", limit=_travel_limit("Z")),
                })})
    def move_to(self, position):
        self.native.move_to(x=float(position["x"]), y=float(position["y"]), z=float(position["z"]), wait=True)
        actual = self.native.get_position()
        reached = all(f"{float(actual[axis]):.2f}" == f"{float(position[key]):.2f}"
                      for axis, key in (("X", "x"), ("Y", "y"), ("Z", "z")))
        return {"reached": reached,
                "position": {key: float(actual[axis]) for axis, key in (("X", "x"), ("Y", "y"), ("Z", "z"))}}

    @action(cap="cap.motion.home.v1",
            description="Home the requested axes; without axes the all-axes routine also homes Z",
            input={"axes": Field(
                "array", description="Axes to home individually; omit for the all-axes routine",
                items=Field("string", enum=["x", "y", "u"], description="Axis name"))})
    def home(self, axes=None):
        if not axes:
            self.native.home_all()
            return {"homed": True, "axes": ["x", "y", "z", "u"]}
        for axis in axes:
            {"x": self.native.home_x, "y": self.native.home_y, "u": self.native.home_u}[axis]()
        return {"homed": True, "axes": list(axes)}

    @action(name="x-cap.machineagency.set_tool_offset.v1",
            description="Set the X/Y/Z tool offset of a configured tool with the upstream G10 command",
            input={
                "tool_index": Field("integer", unit="1", description="Configured tool index",
                                    limit=Limit.operator_required(
                                        "the configured tool indices come from the machine's config.g and tools "
                                        "list (Machine.py:284-312); the site sets the permitted indices")),
                "x": Field("number", unit="mm", description="Tool X offset",
                           limit=Limit.operator_required(
                               "tool offsets are calibration values (Machine.py:721-741); the site sets the "
                               "permitted offset range")),
                "y": Field("number", unit="mm", description="Tool Y offset",
                           limit=Limit.operator_required(
                               "tool offsets are calibration values (Machine.py:721-741); the site sets the "
                               "permitted offset range")),
                "z": Field("number", unit="mm", description="Tool Z offset",
                           limit=Limit.operator_required(
                               "tool offsets are calibration values (Machine.py:721-741); the site sets the "
                               "permitted offset range")),
            },
            output={
                "tool_index": Field("integer", unit="1", description="Tool index the offsets were applied to"),
                "x": Field("number", unit="mm", description="Applied X offset"),
                "y": Field("number", unit="mm", description="Applied Y offset"),
                "z": Field("number", unit="mm", description="Applied Z offset"),
            })
    def set_tool_offset(self, tool_index, x, y, z):
        self.native.set_tool_offset(tool_index, x=x, y=y, z=z)
        return {"tool_index": tool_index, "x": x, "y": y, "z": z}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The Duet emergency stop: M112 disables the steppers and resets the controller."""
        self.native.gcode("M112", timeout=2.0)

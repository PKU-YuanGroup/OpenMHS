"""OpenMHS driver for gh.uw-loci/flamingo_control: the stage position controller of a Flamingo microscope.

A direct Driver over ``py2flamingo.controllers.position_controller:PositionController``, the upstream controller
that turns millimetre and degree targets into the microscope's TCP stage commands
(src/py2flamingo/controllers/position_controller.py:33-105).  The upstream class talks to a connection service and
keeps a locally tracked position; this driver publishes that position and exposes the controller's absolute
four-axis move, its HALT-based stop and its home-position settings.

* reads: the tracked X, Y and Z position in millimetres, the rotation R in degrees, and the home position stored in
  the microscope settings;
* writes: the four home-position coordinates.  The controller validates them against the stage limits and writes
  them back to ``microscope_settings/ScopeSettings.txt`` (position_controller.py:793-835); the driver reads the
  stored value back;
* one extension action, ``x-cap.uw-loci.move_stage.v1``: the complete stage target (X, Y, Z, R) handed to the native
  ``move_to_position``.  A catalogue joint class cannot carry this pose: the linear axes are millimetres and the
  rotation axis is degrees, while ``cap.motion.joint_position.v1`` declares radians for every joint.  The action
  first asks the controller's own ``is_position_within_bounds`` because ``move_to_position`` clamps an out-of-range
  target to the soft limits instead of raising (position_controller.py:608-625); a target outside the configured
  stage limits is refused with ``MHS.SAFETY.ENVELOPE_VIOLATION`` instead of being clamped silently;
* ``cap.motion.stop.v1``: the controller's HALT command, followed by a clear of its software latch so the stage can
  be moved again after the stop.  The same HALT is the e-stop.

Every travel target is ``Limit.operator_required``: the stage limits are loaded per microscope from
``{microscope_name}_settings.json`` at run time (src/py2flamingo/services/configuration_service.py:316-327), so this
driver cannot know the envelope of the connected instrument.  Until the operator's ``site-limits.json`` supplies it,
every move and home write is refused ``MHS.SAFETY.LIMITS_UNSET``; ``site-limits.example.json`` is an example, not a
statement about any unit.

Every Fact cites a line of the clone at the pinned commit (0eee5dac8e54edbb02ec0c4a18d3e362ad772310).  This package
is model-authored and unreviewed: it is checked on the fake backend only, and its hardware backend was never run.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, reset, write

#: The stage limits of the connected microscope are deployment data, not a constant of the library.
_LIMIT_SOURCE = ("src/py2flamingo/services/configuration_service.py:316-327 loads the stage limits from the "
                 "per-microscope settings JSON at run time")
_X_REASON = ("no text file of the clone states the X travel of the stage: " + _LIMIT_SOURCE + ", and the stage may "
             "be configured differently; the site supplies the X envelope")
_Y_REASON = ("no text file of the clone states the Y travel of the stage: " + _LIMIT_SOURCE + ", and the stage may "
             "be configured differently; the site supplies the Y envelope")
_Z_REASON = ("no text file of the clone states the Z travel of the stage: " + _LIMIT_SOURCE + ", and the stage may "
             "be configured differently; the site supplies the Z envelope")
_R_REASON = ("no text file of the clone states the rotation range of the stage: " + _LIMIT_SOURCE + ", and the "
             "stage may be configured differently; the site supplies the rotation envelope")
_HOME_X_REASON = ("the home X coordinate must lie inside the configured X travel, which is deployment data: "
                  + _LIMIT_SOURCE + "; the site supplies the allowed home coordinate")
_HOME_Y_REASON = ("the home Y coordinate must lie inside the configured Y travel, which is deployment data: "
                  + _LIMIT_SOURCE + "; the site supplies the allowed home coordinate")
_HOME_Z_REASON = ("the home Z coordinate must lie inside the configured Z travel, which is deployment data: "
                  + _LIMIT_SOURCE + "; the site supplies the allowed home coordinate")
_HOME_R_REASON = ("the home rotation must lie inside the configured rotation range, which is deployment data: "
                  + _LIMIT_SOURCE + "; the site supplies the allowed home coordinate")


class _Target:
    """The four coordinates the upstream ``move_to_position`` and ``set_home_position`` read."""

    __slots__ = ("x", "y", "z", "r")

    def __init__(self, x, y, z, r):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.r = float(r)


class FlamingoStage(Driver):
    device_id = "flamingo-stage"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "py2flamingo.controllers.position_controller:PositionController"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeFlamingoControl"}
    vendor, model = "University of Washington LOCI", "Flamingo light sheet microscope stage"
    display_name = "Flamingo stage position controller (PositionController)"
    tags = ["microscope", "light sheet", "stage", "position", "motion", "flamingo"]
    facts = [
        Fact("A Position carries x, y and z in millimetres and r as a rotation angle in degrees",
             source="upstream_code", ref="src/py2flamingo/models/microscope.py:48-58"),
        Fact("The position controller's axis codes are X=1, Y=2, Z=3 and R=4",
             source="upstream_code", ref="src/py2flamingo/controllers/position_controller.py:24-30"),
        Fact("move_x moves the X axis to a target position in millimetres",
             source="upstream_code", ref="src/py2flamingo/controllers/position_controller.py:290-299"),
        Fact("move_y moves the Y axis to a target position in millimetres",
             source="upstream_code", ref="src/py2flamingo/controllers/position_controller.py:361-370"),
        Fact("move_z moves the Z axis to a target position in millimetres and warns that Z movement needs careful "
             "consideration of focus and collision risks",
             source="upstream_code", ref="src/py2flamingo/controllers/position_controller.py:432-444"),
        Fact("move_rotation moves the rotation axis to an angle in degrees",
             source="upstream_code", ref="src/py2flamingo/controllers/position_controller.py:217-230"),
        Fact("The axis moves send the command and return immediately; motion completion is tracked asynchronously "
             "and the callback fires when motion stops",
             source="upstream_code", ref="src/py2flamingo/controllers/position_controller.py:294-296"),
        Fact("move_to_position moves all four axes and, when validate is true, clamps an out-of-range target to the "
             "configured soft limits instead of raising",
             source="upstream_code", ref="src/py2flamingo/controllers/position_controller.py:585-625"),
        Fact("get_stage_limits delegates to the configuration service and its per-microscope settings",
             source="upstream_code", ref="src/py2flamingo/controllers/position_controller.py:1287-1300"),
        Fact("The configuration service documents that stage limits are loaded from the microscope-specific settings "
             "JSON so each microscope can be configured without code changes",
             source="upstream_code", ref="src/py2flamingo/services/configuration_service.py:316-327"),
        Fact("get_current_position returns the locally tracked position; the microscope hardware does not report the "
             "current position",
             source="upstream_code", ref="src/py2flamingo/controllers/position_controller.py:1338-1348"),
        Fact("get_home_position reads the Home x-axis, y-axis, z-axis and r-axis values from ScopeSettings.txt",
             source="upstream_code", ref="src/py2flamingo/controllers/position_controller.py:764-787"),
        Fact("set_home_position validates the position against the stage limits and writes the four Home values back "
             "to ScopeSettings.txt",
             source="upstream_code", ref="src/py2flamingo/controllers/position_controller.py:793-835"),
        Fact("emergency_stop sends the HALT command (0x6002) to the hardware first, then sets a flag that prevents "
             "new movements until it is cleared",
             source="upstream_code", ref="src/py2flamingo/controllers/position_controller.py:869-910"),
        Fact("clear_emergency_stop clears the emergency-stop flag",
             source="upstream_code", ref="src/py2flamingo/controllers/position_controller.py:920-931"),
        Fact("The clone README describes control software for Flamingo light sheet microscope systems that "
             "communicates with the microscope over TCP/IP",
             source="vendor_doc", ref="README.md:3"),
    ]
    safe_state = ("stage motion halted by the controller's HALT command (0x6002); the controller keeps a locally "
                  "tracked position that may be stale until the stage is homed again")

    # -- reads ------------------------------------------------------------------------------------------------
    @read("position_x", unit="mm", description="Tracked X position of the stage in millimetres")
    def position_x(self):
        return float(self._tracked_position().x)

    @read("position_y", unit="mm", description="Tracked Y position of the stage in millimetres")
    def position_y(self):
        return float(self._tracked_position().y)

    @read("position_z", unit="mm", description="Tracked Z position of the stage in millimetres")
    def position_z(self):
        return float(self._tracked_position().z)

    @read("rotation", unit="deg", description="Tracked rotation of the stage in degrees")
    def rotation(self):
        return float(self._tracked_position().r)

    @read("home_x", unit="mm", description="Home X coordinate stored in the microscope settings")
    def home_x(self):
        return float(self._home_position().x)

    @read("home_y", unit="mm", description="Home Y coordinate stored in the microscope settings")
    def home_y(self):
        return float(self._home_position().y)

    @read("home_z", unit="mm", description="Home Z coordinate stored in the microscope settings")
    def home_z(self):
        return float(self._home_position().z)

    @read("home_rotation", unit="deg", description="Home rotation stored in the microscope settings")
    def home_rotation(self):
        return float(self._home_position().r)

    # -- home-position writes -----------------------------------------------------------------------------------
    @write("home_x", unit="mm", description="Home X coordinate stored in the microscope settings",
           limit=Limit.operator_required(_HOME_X_REASON))
    def set_home_x(self, value):
        return self._set_home_axis("x", value)

    @write("home_y", unit="mm", description="Home Y coordinate stored in the microscope settings",
           limit=Limit.operator_required(_HOME_Y_REASON))
    def set_home_y(self, value):
        return self._set_home_axis("y", value)

    @write("home_z", unit="mm", description="Home Z coordinate stored in the microscope settings",
           limit=Limit.operator_required(_HOME_Z_REASON))
    def set_home_z(self, value):
        return self._set_home_axis("z", value)

    @write("home_rotation", unit="deg", description="Home rotation stored in the microscope settings",
           limit=Limit.operator_required(_HOME_R_REASON))
    def set_home_rotation(self, value):
        return self._set_home_axis("r", value)

    # -- absolute move ------------------------------------------------------------------------------------------
    @action(name="x-cap.uw-loci.move_stage.v1", verb="invoke", risk="R1", exclusive=True,
            description="Move all four stage axes to an absolute position with the controller's move_to_position; "
                        "a target outside the configured stage limits is refused instead of clamped",
            input={
                "x": Field("number", unit="mm", description="Absolute X target in millimetres",
                           limit=Limit.operator_required(_X_REASON)),
                "y": Field("number", unit="mm", description="Absolute Y target in millimetres",
                           limit=Limit.operator_required(_Y_REASON)),
                "z": Field("number", unit="mm", description="Absolute Z target in millimetres",
                           limit=Limit.operator_required(_Z_REASON)),
                "r": Field("number", unit="deg", description="Absolute rotation target in degrees",
                           limit=Limit.operator_required(_R_REASON)),
            },
            output={
                "x": Field("number", unit="mm", description="X target handed to the controller"),
                "y": Field("number", unit="mm", description="Y target handed to the controller"),
                "z": Field("number", unit="mm", description="Z target handed to the controller"),
                "r": Field("number", unit="deg", description="Rotation target handed to the controller"),
            })
    def move_stage(self, x, y, z, r):
        target = _Target(x, y, z, r)
        inside, errors = self.native.is_position_within_bounds(target)
        if not inside:
            raise DriverFailed("MHS.SAFETY.ENVELOPE_VIOLATION",
                               "target is outside the stage limits: " + "; ".join(str(item) for item in errors))
        self.check_cancelled()
        self.native.move_to_position(target, validate=True)
        self.check_cancelled()
        return {"x": target.x, "y": target.y, "z": target.z, "r": target.r}

    # -- stop ---------------------------------------------------------------------------------------------------
    @action(cap="cap.motion.stop.v1",
            description="Halt stage motion with the controller's HALT command and clear its software latch so a "
                        "later move is accepted",
            input={"deceleration": Field(
                unit="m/s2",
                description="Accepted for the class only: the controller's HALT command takes no deceleration "
                            "profile and the driver ignores this value")})
    def stop_motion(self, deceleration=None):
        self.native.emergency_stop()
        self.native.clear_emergency_stop()
        return {"stopped": True}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop(native="emergency_stop")
    def stop(self):
        """The native stop: the controller sends HALT (0x6002) and latches; the runtime latches first."""
        self.native.emergency_stop()

    @reset
    def recover(self):
        """After an operator's reset: clear the controller's emergency-stop flag."""
        self.native.clear_emergency_stop()

    # -- lifecycle ----------------------------------------------------------------------------------------------
    def teardown(self):
        self.native.connection.disconnect()

    # -- helpers ------------------------------------------------------------------------------------------------
    def _tracked_position(self):
        position = self.native.get_current_position()
        if position is None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the position controller has no tracked stage position")
        return position

    def _home_position(self):
        position = self.native.get_home_position()
        if position is None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the microscope settings provide no home position")
        return position

    def _set_home_axis(self, axis, value):
        home = self._home_position()
        target = _Target(
            value if axis == "x" else home.x,
            value if axis == "y" else home.y,
            value if axis == "z" else home.z,
            value if axis == "r" else home.r,
        )
        try:
            self.native.set_home_position(target)
        except ValueError as exc:
            raise DriverFailed("MHS.SAFETY.ENVELOPE_VIOLATION", str(exc)) from exc
        stored = self._home_position()
        return float(getattr(stored, axis))

"""OpenMHS driver for gh.pyepics/newportxps: a Newport XPS motion controller.

A direct Driver (decorated methods) over the upstream controller class
``newportxps.newportxps:NewportXPS``.  The upstream constructor opens a TCP
socket, logs in and calls ``read_systemini``, which fills ``self.groups`` and
``self.stages`` from the controller's ``system.ini`` and reads each stage's
maximum velocity/acceleration and user travel limits from the controller
(newportxps/newportxps.py:53-84, 138-160, 204-256).

The endpoint drives one stage of one group, selected by the backend options
``stage`` and ``group`` (default: the first stage the controller reports, and
the group of that stage).  The driver exposes:

* reads: the bound stage and group, the stage position in the controller's user
  units, the group status, the hardware status and positioner errors of every
  stage, and the PID/feed-forward tuning of the bound stage;
* actions: an absolute move, a relative move, a group home search, group motion
  enable/disable and a group abort, all as ``x-cap.pyepics.*`` extensions (the
  catalogue's ``cap.motion.joint_position.v1`` describes joint positions in
  radians, which does not express a linear stage's controller user units, and
  ``cap.motion.stop.v1`` takes a deceleration in m/s2 that the XPS abort call
  cannot apply);
* safety: ``@estop`` aborts the bound group's move and disables its motion
  (the native ``abort_group``/``disable_group``); the safe state is motion
  disabled on the bound group.

No text file of the clone states the travel range of a stage: the user travel
limits are read from the controller configuration at run time
(newportxps/newportxps.py:250-253), and the physical unit of a position (mm or
deg) depends on the installed stage.  The two move inputs are therefore
``Limit.operator_required``: every move is refused ``MHS.SAFETY.LIMITS_UNSET``
until the operator's site overlay supplies the range in controller user units.

Every Fact cites a line of the clone at the pinned commit
5ee41fced858f2db7edec1f75d2de52f144c51e4.  This package is model-authored and
unreviewed (``driver.lock.json`` ``reviewed_by`` is null): the acceptance gate
runs the fake backend only, and nothing here ran on hardware.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

POSITION_REASON = (
    "no text of the clone states the travel range of a stage: read_systemini reads the user travel limits from the "
    "controller configuration at run time (newportxps/newportxps.py:250-253), and a position is in the controller's "
    "user units, whose physical meaning (mm or deg) depends on the installed stage. The operator supplies the range "
    "of the installed stage in controller user units.")

USER_UNIT = ("controller user units: the physical unit (for example mm or deg) is set by the stage configuration and "
             "is not stated in the clone")


class NewportXPS(Driver):
    device_id = "newportxps"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "newportxps.newportxps:NewportXPS"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeNewportXPS"}
    vendor, model = "Newport", "XPS motion controller"
    display_name = "Newport XPS motion controller (newportxps.NewportXPS)"
    tags = ["motion", "positioner", "stage", "newport", "xps"]
    facts = [
        Fact("The constructor creates the low-level XPS client, calls connect, and keeps the group and stage "
             "dictionaries the controller reports", source="upstream_code",
             ref="newportxps/newportxps.py:53-84"),
        Fact("connect opens a TCP connection with TCP_ConnectToServer, logs in, reads the firmware version and "
             "calls read_systemini", source="upstream_code", ref="newportxps/newportxps.py:138-160"),
        Fact("read_systemini reads the group and stage names from system.ini and then reads each stage's maximum "
             "velocity/acceleration and user travel limits from the controller", source="upstream_code",
             ref="newportxps/newportxps.py:204-256"),
        Fact("get_stage_position calls GroupPositionCurrentGet for one element and returns the value",
             source="upstream_code", ref="newportxps/newportxps.py:752-767"),
        Fact("move_stage sends GroupMoveAbsolute, or GroupMoveRelative when relative is true, with the value in a "
             "one-element list", source="upstream_code", ref="newportxps/newportxps.py:731-750"),
        Fact("get_group_status returns the GroupStatusStringGet text for every group", source="upstream_code",
             ref="newportxps/newportxps.py:612-626"),
        Fact("get_hardware_status returns the PositionerHardwareStatusStringGet text for every stage",
             source="upstream_code", ref="newportxps/newportxps.py:628-643"),
        Fact("get_positioner_errors returns the PositionerErrorStringGet text for every stage, and 'OK' when the "
             "text is empty", source="upstream_code", ref="newportxps/newportxps.py:645-663"),
        Fact("get_tuning returns a dictionary of the twelve PID and feed-forward parameters of a stage",
             source="upstream_code", ref="newportxps/newportxps.py:422-442"),
        Fact("home_group runs GroupHomeSearch, initializing the group first when its status says it is not "
             "initialized", source="upstream_code", ref="newportxps/newportxps.py:570-586"),
        Fact("enable_group calls GroupMotionEnable and disable_group calls GroupMotionDisable", source="upstream_code",
             ref="newportxps/newportxps.py:588-610"),
        Fact("abort_group calls GroupMoveAbort for the given group, or for the trajectory group when no group is "
             "given", source="upstream_code", ref="newportxps/newportxps.py:685-693"),
        Fact("The low-level XPS transport sets a 3600 s socket timeout before each command", source="upstream_code",
             ref="newportxps/XPS_C8_drivers.py:90-94"),
        Fact("The README lists moving stages and groups, homing, setting stage velocity, running trajectories and "
             "reading the gathering file among the supported operations", source="vendor_doc",
             ref="README.md:71-86"),
    ]
    safe_state = ("motion is disabled on the bound group and a running group move is aborted (native abort_group "
                  "and disable_group)")

    def setup(self):
        """Bind this endpoint to one stage and its group (backend options ``stage`` and ``group``)."""
        stages = sorted(str(name) for name in self.native.stages)
        if not stages:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "the XPS reports no configured stages")
        stage = self.options.get("stage") or stages[0]
        if stage not in self.native.stages:
            raise DriverFailed("MHS.DEVICE.NOT_READY", f"stage {stage!r} is not configured on the XPS")
        groups = sorted(str(name) for name in self.native.groups)
        group = self.options.get("group")
        if group is None:
            group = stage.rpartition(".")[0] if "." in stage else (groups[0] if groups else None)
        if group not in self.native.groups:
            raise DriverFailed("MHS.DEVICE.NOT_READY",
                               f"group {group!r} of stage {stage!r} is not configured on the XPS")
        self._stage = stage
        self._group = group

    def teardown(self):
        """Close the controller connection (the upstream disconnect closes the FTP connection and the socket)."""
        self.native.disconnect()

    # -- reads ------------------------------------------------------------------------------------------------
    @read("stage", type="string", description="Stage this endpoint drives, as named in the controller's system.ini")
    def stage(self):
        return self._stage

    @read("group", type="string", description="Group that contains the bound stage")
    def group(self):
        return self._group

    @read("position", unit="1",
          description="Position of the bound stage in controller user units (the physical unit is set by the stage "
                      "configuration)")
    def position(self):
        return float(self.native.get_stage_position(self._stage))

    @read("group_status", type="object",
          description="Group status text of every group, keyed by group name, as the controller reports it")
    def group_status(self):
        return dict(self.native.get_group_status())

    @read("hardware_status", type="object",
          description="Hardware status text of every stage, keyed by stage name, as the controller reports it")
    def hardware_status(self):
        return dict(self.native.get_hardware_status())

    @read("positioner_errors", type="object",
          description="Positioner error text of every stage, keyed by stage name; 'OK' when the controller "
                      "reports no error text")
    def positioner_errors(self):
        return dict(self.native.get_positioner_errors())

    @read("tuning", type="object",
          description="Twelve PID and feed-forward parameters of the bound stage, keyed by their controller names")
    def tuning(self):
        return dict(self.native.get_tuning(self._stage))

    # -- actions ----------------------------------------------------------------------------------------------
    @action(name="x-cap.pyepics.move_stage.v1",
            description="Move the bound stage to an absolute position in controller user units",
            input={"position": Field(
                "number", unit="1",
                description=f"Absolute target in {USER_UNIT}",
                limit=Limit.operator_required(POSITION_REASON))},
            output={"stage": Field("string", description="Stage the move was sent to"),
                    "target": Field("number", unit="1", description="Absolute target the command sent"),
                    "position": Field("number", unit="1",
                                      description="Position read back after the move command was issued"),
                    "relative": Field("boolean", description="False: this was an absolute move")})
    def move_stage(self, position):
        target = float(position)
        self.native.move_stage(self._stage, target)
        return {"stage": self._stage, "target": target,
                "position": float(self.native.get_stage_position(self._stage)), "relative": False}

    @action(name="x-cap.pyepics.move_stage_relative.v1",
            description="Move the bound stage by a relative offset in controller user units",
            input={"offset": Field(
                "number", unit="1",
                description=f"Signed relative offset in {USER_UNIT}",
                limit=Limit.operator_required(POSITION_REASON))},
            output={"stage": Field("string", description="Stage the move was sent to"),
                    "offset": Field("number", unit="1", description="Relative offset the command sent"),
                    "position": Field("number", unit="1",
                                      description="Position read back after the move command was issued"),
                    "relative": Field("boolean", description="True: this was a relative move")})
    def move_stage_relative(self, offset):
        step = float(offset)
        self.native.move_stage(self._stage, step, relative=True)
        return {"stage": self._stage, "offset": step,
                "position": float(self.native.get_stage_position(self._stage)), "relative": True}

    @action(name="x-cap.pyepics.home_group.v1",
            description="Run the native home search of the bound group (the stage moves to its reference)",
            output={"group": Field("string", description="Group the home search was sent to"),
                    "homed": Field("boolean", description="True once the native home search call returned"),
                    "status": Field("string", description="Group status text read after the call")})
    def home_group(self):
        self.native.home_group(self._group)
        return {"group": self._group, "homed": True,
                "status": str(self.native.get_group_status()[self._group])}

    @action(name="x-cap.pyepics.enable_group.v1",
            description="Enable motion on the bound group (the native GroupMotionEnable)",
            output={"group": Field("string", description="Group whose motion was enabled"),
                    "enabled": Field("boolean", description="True once the native enable call returned"),
                    "status": Field("string", description="Group status text read after the call")})
    def enable_group(self):
        self.native.enable_group(self._group)
        return {"group": self._group, "enabled": True,
                "status": str(self.native.get_group_status()[self._group])}

    @action(name="x-cap.pyepics.disable_group.v1",
            description="Disable motion on the bound group (the native GroupMotionDisable)",
            output={"group": Field("string", description="Group whose motion was disabled"),
                    "enabled": Field("boolean", description="False once the native disable call returned"),
                    "status": Field("string", description="Group status text read after the call")})
    def disable_group(self):
        self.native.disable_group(self._group)
        return {"group": self._group, "enabled": False,
                "status": str(self.native.get_group_status()[self._group])}

    @action(name="x-cap.pyepics.abort_group.v1",
            description="Abort the bound group's running move (the native GroupMoveAbort); the controller applies "
                        "its configured deceleration and the call takes no profile",
            output={"group": Field("string", description="Group whose move was aborted"),
                    "aborted": Field("boolean", description="True once the native abort call returned"),
                    "status": Field("string", description="Group status text read after the call")})
    def abort_group(self):
        self.native.abort_group(self._group)
        return {"group": self._group, "aborted": True,
                "status": str(self.native.get_group_status()[self._group])}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop(native="abort_group")
    def stop(self):
        """The native stop: the runtime latches first, then aborts the bound group and disables its motion."""
        self.native.abort_group(self._group)
        self.native.disable_group(self._group)

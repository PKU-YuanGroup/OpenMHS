"""OpenMHS driver for gh.ad-sdl/pal_module: the PAL3 robot service.

A direct Driver (decorated methods) over the card's entry symbol ``PAL3_driver:PALService``.  The upstream class is a
stateful Windows/.NET workcell service: its constructor loads the PalPlusDriver assemblies, creates the DirectFactory
driver, starts routing and connects the remote service (PAL3_driver.py:512-626).  The clone's MADSci node constructs
it and calls ``std_start`` (PAL_module.py:40-42), which locks the left head, creates an execution session and homes
the arm (PAL3_driver.py:664-671).  A config-only PythonObjectDriver cannot express that session/start lifecycle or
the read-back position after a motion, so this package uses a direct Driver (the card's own decision is
``direct-driver``).

Bound interface:

* reads: the tool X/Y/Z position in millimetres and the generic-gripper adapter distance in millimetres;
* ``cap.motion.cartesian_pose.v1``: an absolute X/Y/Z move through ``PALService.move_absolute``;
* ``x-cap.ad-sdl.home_axes.v1``: ``PALService.safe_home`` (the class's only home command);
* ``x-cap.ad-sdl.move_relative.v1``: a relative X/Y/Z move through ``PALService.move_relative``;
* ``x-cap.ad-sdl.transfer_vial.v1``: resolve two PAL addresses with ``set_vial`` and move the vial with
  ``move_gripper``;
* ``x-cap.ad-sdl.clean_wash.v1``: the upstream ``clean_wash`` maintenance routine;
* ``x-cap.ad-sdl.disconnect.v1``: the native ``stop_remote_service`` teardown, an ordinary action (not a stop);
* ``x-cap.ad-sdl.reconnect.v1``: the declared re-enable, ``start_remote_service``.

Safety limits.  No text file of the clone states the travel of the rail or the tool axes, so every numeric position
input is ``Limit.operator_required``: the site supplies its workspace in ``site-limits.example.json`` and every move
is refused ``MHS.SAFETY.LIMITS_UNSET`` until it does.  The example overlay is operator data only, not a device fact.

Stop path.  The upstream class has no motion-stop, abort, halt, cancel or emergency-stop method: a search of
PAL3_driver.py at the pin for those words finds only ``stop_remote_service`` and log strings.  ``stop_remote_service``
(PAL3_driver.py:701-703) only calls ``remote_service.Disconnect``; what a disconnect does to an activity that
``session.Execute`` is running is decided by the Ctc.Palplus .NET library, which is not in the clone.  ``pause`` is
read only at the start of loop iterations (PAL3_driver.py:1098, 1542, 1602, 1667) and interrupts no running call.
No independent hardware e-stop is documented in the clone, so ``estop_physical_ref`` is not set.
``start_remote_service`` is the declared re-enable: the upstream's own lock-retry path calls it after a disconnect
(PAL3_driver.py:719-748), and it runs ``direct_service.Reset`` (and ``sys.exit(0)`` when that Reset raises,
PAL3_driver.py:682-699), whose effect on the instrument is not in the clone; a reset itself changes nothing on the
device.

BLOCKED (model review, 2026-11-05).  The author bound the disconnect as the ``@estop`` and as a ``safe_state=True``
action, so the SDK reported every e-stop completed and the safe state achieved for a remote-session teardown that
proves nothing about the arm.  Under the user's decision of 2026-11-04 (an actuator without a source-backed stop stays
blocked) the reviewer kept the disconnect in the e-stop as a best-effort step, made the e-stop then raise
``MHS.SAFETY.SAFE_STATE_UNREACHED`` (the latch stays engaged), and made the disconnect an ordinary action.  The gate
therefore fails G3 (SAFE-045: an R2 hardware driver without an independent stop); that is the expected blocked state.

Every Fact cites a line of the clone at the pinned commit 31da19a869362cbc1766ffca0508f84ccdb8405e.  The README says
the module is a work in progress that needs testing and validation on the real instrument (README.md:3).  This package
is model-authored and unreviewed: the acceptance gate runs the fake backend only; the hardware path needs Windows,
.NET, the Ctc.Palplus assemblies, the PalPlusDriver DLLs and two script modules from a Dropbox path outside the clone
(PAL3_driver.py:19-22), and was never run.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

#: No text file of the clone states the workspace of a configured PAL3 rail.
NO_TRAVEL = ("no text file of the clone states the travel of the PAL3 rail or the tool axes; the installed rail, "
             "the trays and the workcell layout set the workspace, so the site supplies it")

#: The same reason for a relative move: the clone states no travel envelope.
NO_RELATIVE = ("no text file of the clone states the allowed travel of a relative PAL3 move; the installed rail and "
               "the workcell layout set the envelope, so the site supplies it")

_POSITION_OUT = Field(
    "object", description="Tool X/Y/Z position in millimetres after the move",
    properties={
        "x": Field("number", unit="mm", description="Tool X coordinate in millimetres"),
        "y": Field("number", unit="mm", description="Tool Y coordinate in millimetres"),
        "z": Field("number", unit="mm", description="Tool Z coordinate in millimetres"),
    },
)


class PalService(Driver):
    device_id = "pal"
    device_kind = "robot.arm"
    mode = "hardware"
    #: The PAL3 moves a rail-mounted arm and a gripper and pumps solvent: real mechanical motion is at least R2
    #: (MHS/spec/04-safety.md); the card's floor is R2 as well.
    risk = "R2"
    native = "PAL3_driver:PALService"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePALService"}
    vendor, model = "AD-SDL", "PAL3"
    display_name = "PAL3 robot arm (PAL3_driver.PALService)"
    tags = ["pal3", "robot-arm", "gantry", "gripper", "vial-transfer", "windows", "dotnet"]
    facts = [
        Fact("PALService is the PAL3 robot service: its constructor creates the DirectFactory driver, starts routing,"
             " resolves the configuration and direct services and calls start_remote_service",
             source="upstream_code", ref="PAL3_driver.py:512-626"),
        Fact("When no host is given, the constructor uses the PAL1 address 192.168.99.230",
             source="upstream_code", ref="PAL3_driver.py:514-525"),
        Fact("At import PAL3_driver imports clr and keyboard, adds a reference to System, calls os.getlogin(), "
             "appends a Windows Dropbox path to sys.path and imports CustomTracker and ContainerManager from it",
             source="upstream_code", ref="PAL3_driver.py:1-22"),
        Fact("The upstream MADSci node constructs PALService and calls std_start('test') at startup",
             source="upstream_code", ref="PAL_module.py:40-42"),
        Fact("std_start locks the left head, creates a new execution session, sends a status message and homes the arm",
             source="upstream_code", ref="PAL3_driver.py:664-671"),
        Fact("set_active_modules calls std_PAL1_start only when the host is the PAL1 address and std_nmr_start only "
             "when it is the NMR address; std_PAL1_start looks up the fast wash, wash, waste, centrifuge, vortex, "
             "dilutor, gripper, syringe and dilutor tool modules by name", source="upstream_code",
             ref="PAL3_driver.py:803-824"),
        Fact("get_current_pos calls GetArmPosition and get_xyz converts the returned EuclideanVector from metres to "
             "millimetres", source="upstream_code", ref="PAL3_driver.py:903-917"),
        Fact("move_absolute creates a MoveAbsolute activity, sets DestinationX, DestinationY and DestinationZ with "
             "units.GetMilliMeter, calls session.Execute and then get_current_pos", source="upstream_code",
             ref="PAL3_driver.py:950-963"),
        Fact("move_relative creates a MoveRelative activity, sets MovementX, MovementY and MovementZ with "
             "units.GetMilliMeter for the non-zero components only, sets ForceDirectMovement, calls session.Execute "
             "and then get_current_pos", source="upstream_code", ref="PAL3_driver.py:965-978"),
        Fact("safe_home is defined twice with the same body: safe_getout, which moves relative only when safe.inside "
             "is set, then MoveToHome, then safe.inside is cleared", source="upstream_code",
             ref="PAL3_driver.py:1012-1027"),
        Fact("set_vial resolves the address with set_pos/GetVial and allocates a vial from the current execution "
             "session", source="upstream_code", ref="PAL3_driver.py:856-866"),
        Fact("move_gripper checks the target and then the source with detect_object; when the target is free and the "
             "source is found it executes the grab activity, moves above the target with gripper2object, moves the "
             "adapter to gr.width, grips and returns 0, otherwise it calls LeaveObject and returns 1",
             source="upstream_code", ref="PAL3_driver.py:1829-1860"),
        Fact("gripper_distance reads GenericGripperGetAdapterDistance and converts the reported metres to millimetres",
             source="upstream_code", ref="PAL3_driver.py:1890-1895"),
        Fact("clean_wash rinses the source liner twice and the syringe at 50 percent for two cycles",
             source="upstream_code", ref="PAL3_driver.py:1140-1143"),
        Fact("stop_remote_service calls remote_service.Disconnect when IsConnected is true and does nothing else",
             source="upstream_code", ref="PAL3_driver.py:701-703"),
        Fact("start_remote_service resolves IRemoteService, calls Remote.Connect and then, in a finally block, "
             "direct_service.Reset, calling sys.exit(0) when Reset raises", source="upstream_code",
             ref="PAL3_driver.py:682-699"),
        Fact("do_lock tries the left-head lock five times, calls stop_remote_service and then start_remote_service "
             "after a lock exception, and calls sys.exit(0) when every attempt failed", source="upstream_code",
             ref="PAL3_driver.py:719-748"),
        Fact("tm_sequence checks self.pause or ctrl+q at the start of each iteration of its transfer-map loop and "
             "returns self.transfer when either is set", source="upstream_code", ref="PAL3_driver.py:1096-1099"),
        Fact("centrifuge_sequence checks self.pause or ctrl+q at the start of each iteration of its while loop and "
             "returns self.transfer when either is set", source="upstream_code", ref="PAL3_driver.py:1600-1603"),
        Fact("The constructor imports .NET System and Ctc.Palplus.Integration.Driver",
             source="upstream_code", ref="PAL3_driver.py:595-611"),
        Fact("add_assembly calls sys.exit(0) when the named DLL is not found under self.dir",
             source="upstream_code", ref="PAL3_driver.py:651-658"),
        Fact("The upstream README says the module is a work in progress and needs testing and validation on the "
             "real instrument", source="vendor_doc", ref="README.md:3"),
    ]
    safe_state = ("No acknowledged stop: the e-stop calls stop_remote_service(), which only disconnects the PAL remote "
                  "service, and then reports SAFE_STATE_UNREACHED with the latch held; the clone has no motion-stop, "
                  "abort or halt command and does not show what a disconnect does to a running activity, so an arm "
                  "already moving may keep moving")

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("x_mm", unit="mm", description="Tool X coordinate reported by the PAL arm")
    def x_mm(self):
        self.native.get_current_pos()
        return float(self.native.x)

    @read("y_mm", unit="mm", description="Tool Y coordinate reported by the PAL arm")
    def y_mm(self):
        self.native.get_current_pos()
        return float(self.native.y)

    @read("z_mm", unit="mm", description="Tool Z coordinate reported by the PAL arm")
    def z_mm(self):
        self.native.get_current_pos()
        return float(self.native.z)

    @read("gripper_distance_mm", unit="mm", description="Generic-gripper adapter distance reported by the arm")
    def gripper_distance_mm(self):
        return float(self.native.gripper_distance())

    # -- actions --------------------------------------------------------------------------------------------------
    @action(cap="cap.motion.cartesian_pose.v1",
            input={"position": Field(
                "object", description="Absolute tool X/Y/Z position in millimetres",
                properties={
                    "x": Field("number", unit="mm", description="Absolute tool X coordinate in millimetres",
                               limit=Limit.operator_required(NO_TRAVEL)),
                    "y": Field("number", unit="mm", description="Absolute tool Y coordinate in millimetres",
                               limit=Limit.operator_required(NO_TRAVEL)),
                    "z": Field("number", unit="mm", description="Absolute tool Z coordinate in millimetres",
                               limit=Limit.operator_required(NO_TRAVEL)),
                })},
            description="Move the tool to an absolute X/Y/Z position with the upstream MoveAbsolute activity; the "
                        "upstream call returns after session.Execute, then the position is read back")
    def cartesian_pose(self, position):
        self.native.move_absolute(float(position["x"]), float(position["y"]), float(position["z"]))
        self.native.get_current_pos()
        return {"reached": True, "position": self._position()}

    @action(name="x-cap.ad-sdl.home_axes.v1",
            output={"homed": Field("boolean", description="True once the upstream safe_home routine returned")},
            description="Home all axes with the upstream safe_home(): first move out of a restricted tray, then "
                        "execute MoveToHome.  It takes no input because safe_home has no axes or speed argument")
    def home(self):
        self.native.safe_home()
        return {"homed": True}

    @action(name="x-cap.ad-sdl.move_relative.v1",
            input={
                "dx": Field("number", unit="mm", description="Relative X displacement in millimetres",
                            limit=Limit.operator_required(NO_RELATIVE)),
                "dy": Field("number", unit="mm", description="Relative Y displacement in millimetres",
                            limit=Limit.operator_required(NO_RELATIVE)),
                "dz": Field("number", unit="mm", description="Relative Z displacement in millimetres",
                            limit=Limit.operator_required(NO_RELATIVE)),
            },
            output={"reached": Field("boolean", description="True once the upstream MoveRelative activity returned"),
                    "position": _POSITION_OUT},
            description="Move the tool relative to its current position with the upstream MoveRelative activity; "
                        "the upstream call returns after session.Execute and the position is read back")
    def move_relative(self, dx, dy, dz):
        self.native.move_relative(float(dx), float(dy), float(dz))
        self.native.get_current_pos()
        return {"reached": True, "position": self._position()}

    @action(name="x-cap.ad-sdl.transfer_vial.v1",
            input={
                "source": Field("string", description="PAL vial address of the vial to move, as accepted by "
                                                      "set_vial (for example 'Tray Holder 1:Slot1:1')"),
                "target": Field("string", description="PAL vial address of the destination, in the same form"),
            },
            output={
                "moved": Field("boolean", description="True when move_gripper returned 0 (it ran the grab, the "
                                                      "move above the target, the adapter move and the grip; the "
                                                      "target is not checked again); False when it returned 1"),
                "source": Field("string", description="Source address the driver passed to set_vial"),
                "target": Field("string", description="Target address the driver passed to set_vial"),
            },
            description="Resolve two PAL vial addresses and move the source vial to the target with the upstream "
                        "generic gripper; a target the upstream detects as occupied returns moved=false")
    def transfer_vial(self, source, target):
        source_vial = self.native.set_vial(source)
        target_vial = self.native.set_vial(target)
        status = self.native.move_gripper(source_vial, target_vial)
        return {"moved": status == 0, "source": source, "target": target}

    @action(name="x-cap.ad-sdl.clean_wash.v1",
            output={"washed": Field("boolean", description="True once the upstream clean_wash routine returned")},
            description="Run the upstream clean_wash maintenance routine (two source-liner rinses and two "
                        "half-syringe wash cycles)")
    def clean_wash(self):
        self.native.clean_wash()
        return {"washed": True}

    # -- safety and recovery --------------------------------------------------------------------------------------
    @action(name="x-cap.ad-sdl.disconnect.v1",
            output={"disconnected": Field("boolean", description="True when the remote service reports that it is "
                                                                  "no longer connected")},
            description="Disconnect the PAL remote service with the upstream stop_remote_service().  A teardown, "
                        "not a stop: it does not claim that an arm already moving has stopped")
    def disconnect(self):
        self.native.stop_remote_service()
        if self.native.remote_service.IsConnected:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "the PAL remote service still reports IsConnected after stop_remote_service")
        return {"disconnected": True}

    @action(name="x-cap.ad-sdl.reconnect.v1", reenable=True,
            output={"connected": Field("boolean", description="True when the remote service reports IsConnected "
                                                               "after the upstream start_remote_service")},
            description="Reconnect the PAL remote service with the upstream start_remote_service() (Remote.Connect, "
                        "then direct_service.Reset); the declared re-enable is refused while the e-stop is latched "
                        "and the reset never runs it")
    def reconnect(self):
        self.native.start_remote_service()
        if not self.native.remote_service.IsConnected:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "start_remote_service returned without a connected PAL remote service")
        return {"connected": True}

    @estop(native="stop_remote_service")
    def emergency_stop(self):
        """Disconnect the remote service, then refuse to certify a safe state (model review, 2026-11-05).

        stop_remote_service is the only stop-like member of the class and only disconnects the remote service; the
        clone does not show what that does to a running activity, so nothing confirms that the arm stopped.
        """
        self.native.stop_remote_service()
        raise DriverFailed(
            "MHS.SAFETY.SAFE_STATE_UNREACHED",
            "stop_remote_service disconnected the PAL remote service, but the clone has no motion stop and does not "
            "show what a disconnect does to a running activity; nothing confirms that the arm stopped")

    def teardown(self):
        """Disconnect and dispose the upstream driver on close; no homing is run here."""
        self.native.stop_remote_service()
        self.native.shutdown()

    def _position(self):
        return {"x": float(self.native.x), "y": float(self.native.y), "z": float(self.native.z)}

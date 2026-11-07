"""OpenMHS driver for gh.bsh90/smarpod-ophyd: a SmarAct SmarPod six-axis hexapod.

A direct ``Driver`` over the writable upstream class ``OphydSmarPod:SmarSignal`` (src/OphydSmarPod.py:65), which
wraps the vendor module ``smaract.smarpod``.  The card named the ``OphydDriver`` helper; that helper's proven grammar
accepts only direct classic ``Component(EpicsSignal | EpicsSignalRO | Signal, "literal")`` declarations, while this
repository defines its own ``Signal`` subclasses and reads and writes the vendor API (``GetPose``, ``Move``,
``IsPoseReachable`` and ``Stop``).  The package therefore uses a direct driver with a production adapter
(native.py) over the same entry symbol; this deviation is recorded in RESULT.json.

* ``pose`` is the six-component platform pose in the vendor API's own units: position X, Y, Z and rotation X, Y, Z,
  in the order of ``SmarPod.pose_to_double_list`` (src/SmarPodMain.py:45-53).  The clone states no engineering unit
  for any component.  Gate G8 requires a unit on every numeric input of a hardware driver, so the fields carry the
  UCUM code ``1`` as a placeholder; the descriptions say that it is not a dimensionless claim (positions and
  rotations are different quantities), and one operator envelope bounds all six components.
* The clone states no travel range or workspace bound either.  Reachability is a runtime question answered by
  ``smarpod.IsPoseReachable`` (src/OphydSmarPod.py:96-104).  Every pose input is therefore
  ``Limit.operator_required``: without a site envelope the runtime refuses with ``MHS.SAFETY.LIMITS_UNSET``.
* The stop route is the vendor ``smarpod.Stop(handle)`` used by the upstream setup (src/SmarPodMain.py:109), followed
  by the upstream's fresh ``GetMoveStatus`` check for ``MoveStatus.STOPPED`` (src/SmarPodMain.py:110-121).  It is
  exposed as the safe-state action ``cap.motion.stop.v1`` and reached by the ``@estop`` method.
* Not exposed: automatic calibration and reference-mark search.  The upstream constructor runs ``set_up``
  (src/OphydSmarPod.py:20), which calls ``Calibrate`` and ``FindReferenceMarks`` (src/SmarPodMain.py:87-95).  That is
  uncommanded motion, so the hardware adapter refuses to start on an unreferenced controller and leaves referencing
  to the site's vendor procedure; the primary pose read/write interface is preserved.

Every Fact and every ``source_ref`` cites the clone at the pinned commit a3d50e67618b9a15527d54339a333f199f58681d.
The package is model-authored and unreviewed (``reviewed_by`` is null); it has been checked on the fake backend only
and has never connected to a SmarPod.
"""

import time

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The selected upstream class and the module of the setup class it uses.
SOURCE = "src/OphydSmarPod.py"
API_SOURCE = "src/SmarPodMain.py"

#: The extension capability: no catalogue motion class carries the coupled six-component pose in unknown units.
POSE_CAPABILITY = "x-cap.bsh90.hexapod_pose.v1"

#: The clone states no pose unit.  Gate G8 requires a unit on every numeric input of a hardware driver, so the
#: fields use the UCUM code ``1``; it does not assert a dimensionless quantity (see POSE_DESCRIPTION).
POSE_UNIT = "1"

POSE_DESCRIPTION = (
    "Six-component SmarPod pose in the vendor API's own units: position X, Y, Z then rotation X, Y, Z, the order "
    "of SmarPod.pose_to_double_list (src/SmarPodMain.py:45-53). The clone states no unit; '1' is a placeholder, "
    "not a dimensionless claim, and one site envelope bounds all six components."
)

#: Implementation bound of the wait after a stop request; it is not a device limit or a Fact.
STOP_WAIT_S = 5.0


def _pose_limit() -> Limit:
    """The pose envelope: nothing in the clone states a workspace or travel range."""
    return Limit.operator_required(
        "the clone states no position or rotation travel range and no workspace bound; the controller checks a pose "
        "at run time with smarpod.IsPoseReachable (src/OphydSmarPod.py:96-104), so the site supplies the allowed "
        "pose envelope")


def _pose_field() -> Field:
    return Field("array", items="number", length=6, unit=POSE_UNIT, description=POSE_DESCRIPTION)


class SmarPodHexapod(Driver):
    device_id = "smarpod-hexapod"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    native = "OphydSmarPod:SmarSignal"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeSmarSignal"}
    vendor = "SmarAct"
    model = "SmarPod six-axis hexapod (the upstream class opens model 10052)"
    display_name = "SmarAct SmarPod hexapod (gh.bsh90/smarpod-ophyd SmarSignal)"
    tags = ["ophyd", "smaract", "hexapod", "motion", "pose", "six-axis"]
    safe_state = ("commanded motion stopped with the vendor smarpod.Stop(handle) and confirmed by a fresh "
                  "GetMoveStatus check for MoveStatus.STOPPED")

    facts = [
        Fact("SmarSignalRO derives from ophyd Signal, creates a SmarPod and opens the controller in its constructor",
             source="upstream_code", ref=f"{SOURCE}:10-20"),
        Fact("SmarSignalRO.get reads the current pose with smarpod.GetPose and returns pose_to_double_list(pose)",
             source="upstream_code", ref=f"{SOURCE}:25-27"),
        Fact("pose_to_double_list returns positionX, positionY, positionZ, rotationX, rotationY, rotationZ in that "
             "order", source="upstream_code", ref=f"{API_SOURCE}:45-53"),
        Fact("SmarSignal.set verifies reachability, calls smarpod.Move(handle, pose, 0, True) and then requires the "
             "move status to be stopped", source="upstream_code", ref=f"{SOURCE}:68-79"),
        Fact("SmarSignal.get_status reports stopped when smarpod.GetMoveStatus equals MoveStatus.STOPPED",
             source="upstream_code", ref=f"{SOURCE}:81-88"),
        Fact("SmarSignal.check_pose asks smarpod.IsPoseReachable; verify_reachable_position raises when it is not "
             "reachable", source="upstream_code", ref=f"{SOURCE}:96-104"),
        Fact("SmarSignalDifferentAxis.set constructs a new SmarSignalRO without an optional_handle, reads its pose, "
             "replaces component i and sets the pose through a new SmarSignal on that handle", source="upstream_code",
             ref=f"{SOURCE}:107-114"),
        Fact("SmarSignalRO.trigger reads GetMoveStatus once, before its loop, then sleeps 10 s per iteration while "
             "that single reading is not STOPPED; the loop never reads the status again", source="upstream_code",
             ref=f"{SOURCE}:55-62"),
        Fact("SmarPod.set_speed_and_frequency_and_pivot_point_and_coordinate_system sets speed, maximum frequency, "
             "RELATIVE pivot mode with pivot [10e-3, 0, 0] and a coordinate system", source="upstream_code",
             ref=f"{API_SOURCE}:55-68"),
        Fact("The SmarPod class attributes are model 10052 and locator usb:sn:MCS2-00006657", source="upstream_code",
             ref=f"{API_SOURCE}:8-9"),
        Fact("SmarPod.set_up opens the controller with its model and locator, calibrates, searches reference marks "
             "when the controller is not referenced, enables the sensor, then calls smarpod.Stop and raises when the "
             "move status is not STOPPED", source="upstream_code", ref=f"{API_SOURCE}:70-124"),
        Fact("The except clause of set_up catches smarpod.Error and Exception, logs and prints a message built from "
             "err.func and err.code, and does not re-raise", source="upstream_code", ref=f"{API_SOURCE}:126-133"),
        Fact("The stop path is smarpod.Stop(handle) followed by a fresh GetMoveStatus check for MoveStatus.STOPPED",
             source="upstream_code", ref=f"{API_SOURCE}:109-121"),
        Fact("SmarPod.moving checks every pose with IsPoseReachable and move_sequence sends each pose with "
             "smarpod.Move", source="upstream_code", ref=f"{API_SOURCE}:142-161"),
        Fact("The README describes connecting to a SmarPod through the Ophyd interface or directly to its API and "
             "states no pose unit, travel range or workspace bound", source="vendor_doc", ref="README.md:1-13"),
    ]

    # -- reads ------------------------------------------------------------------------------------------------
    @read("pose", type="array", items="number", length=6, unit=POSE_UNIT,
          description=POSE_DESCRIPTION)
    def pose(self):
        return self.native.get()

    # -- the pose write (cap.device.configure.v1) ---------------------------------------------------------------
    @write("pose", type="array", items="number", length=6, unit=POSE_UNIT, risk="R2",
           description=POSE_DESCRIPTION, limit=_pose_limit())
    def set_pose(self, value):
        target = [float(item) for item in value]
        self.check_cancelled()
        if not self.native.check_pose(target):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the controller reports that the requested pose is not reachable")
        self.native.set(target)
        self.check_cancelled()
        applied = self.native.get()
        self.check_cancelled()
        return applied

    # -- motion ------------------------------------------------------------------------------------------------
    @action(name=POSE_CAPABILITY, risk="R2",
            description="Move the hexapod to a six-component pose and return the pose read after the controller "
                        "reports STOPPED",
            input={"pose": Field("array", items="number", length=6, unit=POSE_UNIT,
                                 description=POSE_DESCRIPTION, limit=_pose_limit())},
            output={"pose": _pose_field()})
    def move_pose(self, pose):
        target = [float(item) for item in pose]
        self.check_cancelled()
        if not self.native.check_pose(target):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the controller reports that the requested pose is not reachable")
        self.native.set(target)
        self.check_cancelled()
        reached = self.native.get()
        self.check_cancelled()
        return {"pose": reached}

    # -- safe state and stop -----------------------------------------------------------------------------------
    @action(cap="cap.motion.stop.v1", safe_state=True,
            description="Stop all platform motion with the vendor smarpod.Stop(handle) and report the stopped pose; "
                        "the optional class field is accepted for schema compatibility and is not passed through",
            input={"deceleration": Field(
                description="Optional requested deceleration; the vendor smarpod.Stop call in the clone takes no "
                            "deceleration argument, so the controller's own stop profile is used and this value is "
                            "not passed through")})
    def stop_motion(self, deceleration=None):
        self.native.stop()
        deadline = time.monotonic() + STOP_WAIT_S
        while not self.native.get_status():
            if time.monotonic() >= deadline:
                raise DriverFailed("MHS.DEVICE.FAULTED",
                                   "the controller did not report MoveStatus.STOPPED after smarpod.Stop")
            time.sleep(0.01)
        return {"stopped": True, "stopped_position": {"pose": self.native.get()}}

    @estop
    def stop(self):
        """The native stop: the runtime latches, then sends smarpod.Stop(handle)."""
        self.native.stop()

    # -- teardown ----------------------------------------------------------------------------------------------
    def teardown(self):
        self.native.tear_down()

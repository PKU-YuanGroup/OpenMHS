"""OpenMHS driver for gh.openuc2/imswitch: the OpenUC2 ESP32 microscope stage.

A direct ``Driver`` (decorated methods) over the upstream positioner manager
``imswitch.imcontrol.model.managers.positioners.ESP32StageManager:ESP32StageManager``.  The card's
``PythonObjectDriver`` helper maps action inputs to one native call; the coordinated XYZ move here needs the fixed
keyword arguments ``axis="XYZ"``, ``is_absolute=True`` and ``is_blocking=True`` together with an ``(x, y, z)`` tuple
(``ESP32StageManager.py:534-541``), which that command table cannot build.  The card's decision is ``direct-driver``,
so this package takes that shape and records the helper deviation in ``RESULT.json``.

* reads: the X, Y and Z stage positions in micrometres.  The positioner controller documents that the target of a
  move and the position after it are in µm (``PositionerController.py:23-26``).  Every position comes from a device
  query of ``getPosition()``: when that query raises, the upstream logs it and returns its cached ``_position``
  object (``ESP32StageManager.py:605-617``, the object the ``position`` property returns,
  ``PositionerManager.py:59-63``), which after a move holds the commanded target (``ESP32StageManager.py:542-544``).
  The driver refuses such a cached value (model review) instead of reporting it as a position.
* action: ``x-cap.openuc2.move_xyz.v1`` drives X, Y and Z to absolute positions in micrometres with the upstream
  coordinated ``move(axis="XYZ", ...)``.  No text file of the clone states the travel of an installed stage: the
  manager reads ``minX``/``maxX``, ``minY``/``maxY`` and ``minZ``/``maxZ`` from the positioner setup and defaults
  them to -inf/inf (``ESP32StageManager.py:62-76``), and the combined XYZ branch applies no soft-limit check at all
  (``ESP32StageManager.py:534-544``).  The three inputs are therefore ``Limit.operator_required``: every move is
  refused ``MHS.SAFETY.LIMITS_UNSET`` until the operator's ``site-limits.json`` supplies the travel of the installed
  stage (``site-limits.example.json`` shows the shape with example-only values).  A move whose native call raises,
  or whose position read-back fails, ends ``unknown``: the stage may have moved.
* stop: ``cap.motion.stop.v1`` is the declared safe-state action.  It calls the native all-axis stop ``stopAll()``
  (``ESP32StageManager.py:647-648``), which the upstream itself uses as its immediate stop of all axes
  (``PositionerController.py:739-746``, ``UC2ConfigController.py:246-266``, ``ESP32StageManager.py:1066-1075``), and
  then confirms a standstill by two device position queries ``STANDSTILL_INTERVAL_S`` apart that must agree on X, Y
  and Z; otherwise it fails ``MHS.SAFETY.SAFE_STATE_UNREACHED`` (model review: ``stopAll()`` returns nothing, so a
  returned call proves nothing).  The ``@estop`` method calls the same native stop, and the runtime then runs the
  safe-state action.  No independent hardware e-stop is documented for this stage, so ``estop_physical_ref`` is not
  set.
* the upstream manager's constructor is not side-effect-free: it switches the motors on, commands a -1 then +1
  relative move on every configured axis and optionally homes on startup (``ESP32StageManager.py:211-214, 306-319``).
  The hardware factory therefore needs the human hardware review that an R2 model-authored package requires.

Every Fact cites a line of the clone at the pinned commit e5db60f1021b0d7b72f171069258768127880ac5.  This package is
model-authored and unreviewed: it is checked on the fake backend only, claims no hardware run and no MHS-Device level.
"""

import time

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, OutcomeUnknown, action, estop, read

STAGE = "imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py"
BASE = "imswitch/imcontrol/model/managers/positioners/PositionerManager.py"
POSITIONER = "imswitch/imcontrol/controller/controllers/PositionerController.py"
CONFIG = "imswitch/imcontrol/controller/controllers/UC2ConfigController.py"
RS232 = "imswitch/imcontrol/model/managers/rs232/ESP32Manager.py"
STANDA = "imswitch/imcontrol/model/interfaces/standamotor.py"
SETUP_DOC = "docs/SETUP_JSON_SCHEMA_REFERENCE.md"
GUIDE = "agents.md"

#: The axes this driver moves and reads (the A axis is not served).
AXES = ("X", "Y", "Z")
#: Wait between the two device position queries that confirm a standstill after the stop.  This is the package's own
#: choice (model review), not a value of the clone, which states no settling time for the ESP32 stop.
STANDSTILL_INTERVAL_S = 0.2

#: The travel of the installed stage is not stated by any text of the clone; it is positioner setup data.
_TRAVEL = Limit.operator_required(
    "no text file of the clone states the travel of an installed stage; the manager reads minX/maxX, "
    "minY/maxY and minZ/maxZ from the positioner setup with -inf/inf defaults (ESP32StageManager.py:62-76), the "
    "combined XYZ move applies no soft-limit check (ESP32StageManager.py:534-544), and the site supplies the travel "
    "of its stage in site-limits.json")


class UC2ESP32Stage(Driver):
    device_id = "uc2-stage"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R2"
    native = "imswitch.imcontrol.model.managers.positioners.ESP32StageManager:ESP32StageManager"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeESP32StageManager"}
    vendor, model = "OpenUC2", "ESP32 stage (ImSwitch ESP32StageManager)"
    display_name = "OpenUC2 ESP32 microscope stage"
    tags = ["openuc2", "uc2", "stage", "positioner", "esp32", "imswitch"]
    facts = [
        Fact("The upstream class is the ImSwitch positioner manager for the UC2 ESP32 stage: it takes the RS232 "
             "manager named by managerProperties['rs232device'] and uses its _esp32.motor and _esp32.home",
             source="upstream_code", ref=f"{STAGE}:33-42"),
        Fact("ESP32Manager imports uc2rest as uc2, with the comment pip install UC2-REST",
             source="upstream_code", ref=f"{RS232}:1"),
        Fact("ESP32Manager builds its ESP32 client as uc2.UC2Client with the configured serial port",
             source="upstream_code", ref=f"{RS232}:51-53"),
        Fact("The stage's per-axis step sizes are calibrated in µm/step, are read from the positioner setup "
             "(stepsizeX, stepsizeY, stepsizeZ, stepsizeA) and default to 1",
             source="upstream_code", ref=f"{STAGE}:55-60"),
        Fact("The setup-file reference's example ESP32StageManager properties set stepsizeX 0.396, stepsizeY 0.396 "
             "and stepsizeZ 0.3125", source="upstream_code", ref=f"{SETUP_DOC}:451-456"),
        Fact("The positioner controller documents the requested per-axis target and the position after the move in "
             "µm", source="upstream_code", ref=f"{POSITIONER}:23-26"),
        Fact("PositionerController._readPosition takes the per-axis µm position from manager.getPosition() and falls "
             "back to the manager's position property when that raises or returns no dict",
             source="upstream_code", ref=f"{POSITIONER}:187-195"),
        Fact("The move() docstring says that with is_blocking=True it blocks until the motor has reached the new "
             "position and that a TimeoutError is raised when the motor has not reached it after timeout; timeout "
             "defaults to gTIMEOUT", source="upstream_code", ref=f"{STAGE}:432-443"),
        Fact("The module constant gTIMEOUT is 100", source="upstream_code", ref=f"{STAGE}:9"),
        Fact("The XYZ branch adds the per-axis stage offset to an absolute target and sends one _motor.move_xyz call "
             "with the speed, acceleration, enable, blocking and timeout arguments, without using its return value",
             source="upstream_code", ref=f"{STAGE}:534-541"),
        Fact("After _motor.move_xyz returns, the XYZ branch writes the commanded absolute target, or the cached "
             "position plus the commanded displacement, into the cached _position",
             source="upstream_code", ref=f"{STAGE}:542-544"),
        Fact("The stage's minimum and maximum positions are positioner setup values: minX/maxX, minY/maxY and "
             "minZ/maxZ come from managerProperties and default to -inf and inf",
             source="upstream_code", ref=f"{STAGE}:62-76"),
        Fact("Soft limits are enabled per axis by limitXenabled, limitYenabled and limitZenabled, which also default "
             "to false", source="upstream_code", ref=f"{STAGE}:189-192"),
        Fact("The single-axis X, Y and Z branches of move() refuse a target below the axis minimum or above its "
             "maximum when that axis's limit is enabled", source="upstream_code", ref=f"{STAGE}:462-509"),
        Fact("The combined XYZ branch applies no soft-limit check", source="upstream_code", ref=f"{STAGE}:534-544"),
        Fact("getPosition() builds a new dict from _motor.get_position() minus the per-axis stage offset; when the "
             "query raises, it logs the error and returns the cached _position object itself",
             source="upstream_code", ref=f"{STAGE}:605-617"),
        Fact("The position property of the positioner manager base class returns the cached _position",
             source="upstream_code", ref=f"{BASE}:59-63"),
        Fact("getDevicePositionAxis documents _motor.get_position() as the live raw device position, read directly "
             "from the ESP32 firmware", source="upstream_code", ref=f"{STAGE}:739-749"),
        Fact("stopAll() calls _motor.stop() with no axis, the all-axis stop",
             source="upstream_code", ref=f"{STAGE}:647-648"),
        Fact("forceStop() dispatches an axis to stop_x/stop_y/stop_z/stop_a and anything else to stopAll()",
             source="upstream_code", ref=f"{STAGE}:620-630"),
        Fact("PositionerController.stopAllAxes, documented as immediately stopping all axes of the positioner, calls "
             "forceStop('all')", source="upstream_code", ref=f"{POSITIONER}:739-746"),
        Fact("cancelZStageSync, documented as stopping an in-progress Z-sync run and halting all motors, sets the "
             "sync's cancel event and calls stopAll()", source="upstream_code", ref=f"{STAGE}:1066-1075"),
        Fact("The collision handler's _stopAllMotors, documented as immediately stopping every positioner, calls "
             "stopAll() on each positioner that has it", source="upstream_code", ref=f"{CONFIG}:246-266"),
        Fact("The clone's agent guide lists stopAxis and stopAllAxes as the emergency stop for a move",
             source="upstream_code", ref=f"{GUIDE}:283"),
        Fact("The clone's agent guide warns that a stage which is moving when its command stream breaks does not "
             "stop cleanly", source="upstream_code", ref=f"{GUIDE}:893-896"),
        Fact("closeEvent() is empty", source="upstream_code", ref=f"{STAGE}:602-603"),
        Fact("The constructor enables the motors with isEnable and enableauto from the setup, both defaulting to "
             "true", source="upstream_code", ref=f"{STAGE}:211-214"),
        Fact("The constructor commands a -1 then +1 relative move on every configured axis and optionally homes on "
             "startup", source="upstream_code", ref=f"{STAGE}:306-319"),
        Fact("With frameHomeOnStart set in the setup, the constructor starts the frame-homing procedure",
             source="upstream_code", ref=f"{STAGE}:350-352"),
        Fact("frameHomingProcedure runs the homing in a new thread unless is_blocking is true",
             source="upstream_code", ref=f"{STAGE}:988-992"),
        Fact("MIN_SAFE_Z_LIFT_HOMING = 3000 is the minimum distance (µm) Z is lifted out of the bottom before XY are "
             "homed, so the stage cannot knock the objective into the sample during the homing sweep",
             source="upstream_code", ref=f"{STAGE}:10-12"),
        Fact("The frame-homing procedure always lifts Z by at least MIN_SAFE_Z_LIFT_HOMING before homing XY so the "
             "stage cannot drive the objective into the sample",
             source="upstream_code", ref=f"{STAGE}:110-112"),
        Fact("The repository also defines the StandaMotor class in its interfaces package",
             source="upstream_code", ref=f"{STANDA}:16"),
    ]
    safe_state = ("stopAll() -> _motor.stop(), the upstream's immediate stop of all axes, was sent, and two device "
                  "position queries 0.2 s apart afterwards returned the same X, Y and Z; a failed query (the "
                  "upstream's cached fallback) or a position that still changes leaves the e-stop "
                  "SAFE_STATE_UNREACHED with the latch held. The A axis gets the same stop but is not confirmed, and "
                  "the clone does not show whether the stop also switches the motor drivers off.")

    # -- positions -------------------------------------------------------------------------------------------------
    def _device_position(self):
        """X, Y and Z (µm, user frame) from a device query of getPosition(), never from its cache.

        getPosition() builds a new dict from _motor.get_position(); when that query raises it logs the error and
        returns the cached _position object itself (ESP32StageManager.py:605-617), the object the position property
        returns (PositionerManager.py:59-63).  After a move that cache holds the commanded target
        (ESP32StageManager.py:542-544), so a returned cache is refused instead of being reported as a position.
        """
        position = self.native.getPosition()
        if position is self.native.position:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "the device position query failed: getPosition() returned its cached position "
                               "(ESP32StageManager.py:615-617), which is not a reading")
        return {axis: float(position[axis]) for axis in AXES}

    @read("x_um", unit="um", description="X position from a device query of getPosition() (the device position "
          "minus the stage offset, user frame); refused, never replaced by the cached value, when the query fails")
    def x_um(self):
        return self._device_position()["X"]

    @read("y_um", unit="um", description="Y position from a device query of getPosition() (the device position "
          "minus the stage offset, user frame); refused, never replaced by the cached value, when the query fails")
    def y_um(self):
        return self._device_position()["Y"]

    @read("z_um", unit="um", description="Z position from a device query of getPosition() (the device position "
          "minus the stage offset, user frame); refused, never replaced by the cached value, when the query fails")
    def z_um(self):
        return self._device_position()["Z"]

    # -- the coordinated move --------------------------------------------------------------------------------------
    @action(
        name="x-cap.openuc2.move_xyz.v1",
        description="Move the X, Y and Z stage axes to absolute positions in micrometres with the coordinated "
                    "upstream XYZ move, and report the position a device query returns afterwards; a move whose "
                    "native call raises or whose position query fails ends unknown",
        input={
            "x_um": Field("number", unit="um", description="Absolute target of the X axis", limit=_TRAVEL),
            "y_um": Field("number", unit="um", description="Absolute target of the Y axis", limit=_TRAVEL),
            "z_um": Field("number", unit="um", description="Absolute target of the Z axis", limit=_TRAVEL),
        },
        output={
            "x_um": Field("number", unit="um",
                          description="X position from a device query of getPosition() after the move"),
            "y_um": Field("number", unit="um",
                          description="Y position from a device query of getPosition() after the move"),
            "z_um": Field("number", unit="um",
                          description="Z position from a device query of getPosition() after the move"),
        },
    )
    def move_xyz(self, x_um, y_um, z_um):
        """The native coordinated XYZ move; it blocks until the native move call returns."""
        self.check_cancelled()
        try:
            self.native.move(
                value=(float(x_um), float(y_um), float(z_um)),
                axis="XYZ",
                is_absolute=True,
                is_blocking=True,
            )
        except Exception as exc:  # noqa: BLE001 - the move may have been sent; the stage may have moved
            raise OutcomeUnknown(f"the XYZ move raised {type(exc).__name__}; it may have been sent, so the stage may "
                                 "have moved or may still be moving") from None
        self.check_cancelled()
        try:
            position = self._device_position()
        except DriverFailed as exc:
            raise OutcomeUnknown(f"the XYZ move returned, but {exc.message}") from None
        return {"x_um": position["X"], "y_um": position["Y"], "z_um": position["Z"]}

    # -- the safe state --------------------------------------------------------------------------------------------
    def _confirm_standstill(self):
        """Two device position queries STANDSTILL_INTERVAL_S apart that agree on X, Y and Z, else SAFE_STATE_UNREACHED.

        stopAll() returns nothing (ESP32StageManager.py:647-648), so a returned stop proves nothing by itself (model
        review).  A query that falls back to the cache, or a position that still changes, is no standstill.
        """
        try:
            first = self._device_position()
            time.sleep(STANDSTILL_INTERVAL_S)
            second = self._device_position()
        except DriverFailed as exc:
            raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                               f"the all-axis stop was sent, but {exc.message}") from None
        moving = [axis for axis in AXES if second[axis] != first[axis]]
        if moving:
            raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                               f"the all-axis stop was sent, but the position of {', '.join(moving)} still changed "
                               f"over {STANDSTILL_INTERVAL_S} s")
        return {"x_um": second["X"], "y_um": second["Y"], "z_um": second["Z"]}

    @action(
        cap="cap.motion.stop.v1",
        safe_state=True,
        description="Stop all stage axes with the native all-axis stop, then confirm a standstill by two device "
                    "position queries 0.2 s apart that agree on X, Y and Z; otherwise SAFE_STATE_UNREACHED. The "
                    "optional class deceleration field is not applied because the native stop takes no deceleration",
        input={
            "deceleration": Field(
                "number", unit="m/s2",
                description="Optional class field; the native all-axis stop takes no deceleration, so this value is "
                            "not applied",
            ),
        },
    )
    def stop_motion(self, deceleration=None):
        self.native.stopAll()
        return {"stopped": True, "stopped_position": self._confirm_standstill()}

    # -- safety ----------------------------------------------------------------------------------------------------
    @estop(native="stopAll")
    def stop(self):
        """The native all-axis stop; the runtime latches first, calls this, then runs the safe-state action, which
        sends the stop again and confirms the standstill."""
        self.native.stopAll()

    def teardown(self):
        """Send the all-axis stop, then run the lifecycle hook (empty upstream; the hardware factory's override also
        closes the ESP32 client): the clone warns that a stage moving when its command stream breaks does not stop
        cleanly (agents.md:893-896)."""
        try:
            self.native.stopAll()
        finally:
            self.native.closeEvent()

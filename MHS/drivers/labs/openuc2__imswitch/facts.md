# Facts, limits and safety for gh.openuc2/imswitch

Every fact cites `upstream_code` at commit `e5db60f1021b0d7b72f171069258768127880ac5`.  The same facts are written
into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.  The model
review (claude-opus-5-5, a model and not a human, 2026-11-05) corrected, narrowed and added facts; the table below is
regenerated from `reference.json`.

Tags: openuc2, uc2, stage, positioner, esp32, imswitch

| fact | source | ref |
|---|---|---|
| The upstream class is the ImSwitch positioner manager for the UC2 ESP32 stage: it takes the RS232 manager named by managerProperties['rs232device'] and uses its _esp32.motor and _esp32.home | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:33-42 |
| ESP32Manager imports uc2rest as uc2, with the comment pip install UC2-REST | upstream_code | imswitch/imcontrol/model/managers/rs232/ESP32Manager.py:1 |
| ESP32Manager builds its ESP32 client as uc2.UC2Client with the configured serial port | upstream_code | imswitch/imcontrol/model/managers/rs232/ESP32Manager.py:51-53 |
| The stage's per-axis step sizes are calibrated in µm/step, are read from the positioner setup (stepsizeX, stepsizeY, stepsizeZ, stepsizeA) and default to 1 | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:55-60 |
| The setup-file reference's example ESP32StageManager properties set stepsizeX 0.396, stepsizeY 0.396 and stepsizeZ 0.3125 | upstream_code | docs/SETUP_JSON_SCHEMA_REFERENCE.md:451-456 |
| The positioner controller documents the requested per-axis target and the position after the move in µm | upstream_code | imswitch/imcontrol/controller/controllers/PositionerController.py:23-26 |
| PositionerController._readPosition takes the per-axis µm position from manager.getPosition() and falls back to the manager's position property when that raises or returns no dict | upstream_code | imswitch/imcontrol/controller/controllers/PositionerController.py:187-195 |
| The move() docstring says that with is_blocking=True it blocks until the motor has reached the new position and that a TimeoutError is raised when the motor has not reached it after timeout; timeout defaults to gTIMEOUT | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:432-443 |
| The module constant gTIMEOUT is 100 | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:9 |
| The XYZ branch adds the per-axis stage offset to an absolute target and sends one _motor.move_xyz call with the speed, acceleration, enable, blocking and timeout arguments, without using its return value | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:534-541 |
| After _motor.move_xyz returns, the XYZ branch writes the commanded absolute target, or the cached position plus the commanded displacement, into the cached _position | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:542-544 |
| The stage's minimum and maximum positions are positioner setup values: minX/maxX, minY/maxY and minZ/maxZ come from managerProperties and default to -inf and inf | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:62-76 |
| Soft limits are enabled per axis by limitXenabled, limitYenabled and limitZenabled, which also default to false | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:189-192 |
| The single-axis X, Y and Z branches of move() refuse a target below the axis minimum or above its maximum when that axis's limit is enabled | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:462-509 |
| The combined XYZ branch applies no soft-limit check | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:534-544 |
| getPosition() builds a new dict from _motor.get_position() minus the per-axis stage offset; when the query raises, it logs the error and returns the cached _position object itself | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:605-617 |
| The position property of the positioner manager base class returns the cached _position | upstream_code | imswitch/imcontrol/model/managers/positioners/PositionerManager.py:59-63 |
| getDevicePositionAxis documents _motor.get_position() as the live raw device position, read directly from the ESP32 firmware | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:739-749 |
| stopAll() calls _motor.stop() with no axis, the all-axis stop | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:647-648 |
| forceStop() dispatches an axis to stop_x/stop_y/stop_z/stop_a and anything else to stopAll() | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:620-630 |
| PositionerController.stopAllAxes, documented as immediately stopping all axes of the positioner, calls forceStop('all') | upstream_code | imswitch/imcontrol/controller/controllers/PositionerController.py:739-746 |
| cancelZStageSync, documented as stopping an in-progress Z-sync run and halting all motors, sets the sync's cancel event and calls stopAll() | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:1066-1075 |
| The collision handler's _stopAllMotors, documented as immediately stopping every positioner, calls stopAll() on each positioner that has it | upstream_code | imswitch/imcontrol/controller/controllers/UC2ConfigController.py:246-266 |
| The clone's agent guide lists stopAxis and stopAllAxes as the emergency stop for a move | upstream_code | agents.md:283 |
| The clone's agent guide warns that a stage which is moving when its command stream breaks does not stop cleanly | upstream_code | agents.md:893-896 |
| closeEvent() is empty | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:602-603 |
| The constructor enables the motors with isEnable and enableauto from the setup, both defaulting to true | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:211-214 |
| The constructor commands a -1 then +1 relative move on every configured axis and optionally homes on startup | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:306-319 |
| With frameHomeOnStart set in the setup, the constructor starts the frame-homing procedure | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:350-352 |
| frameHomingProcedure runs the homing in a new thread unless is_blocking is true | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:988-992 |
| MIN_SAFE_Z_LIFT_HOMING = 3000 is the minimum distance (µm) Z is lifted out of the bottom before XY are homed, so the stage cannot knock the objective into the sample during the homing sweep | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:10-12 |
| The frame-homing procedure always lifts Z by at least MIN_SAFE_Z_LIFT_HOMING before homing XY so the stage cannot drive the objective into the sample | upstream_code | imswitch/imcontrol/model/managers/positioners/ESP32StageManager.py:110-112 |
| The repository also defines the StandaMotor class in its interfaces package | upstream_code | imswitch/imcontrol/model/interfaces/standamotor.py:16 |

## Scope

The package serves one device class, the card's first entry symbol `ESP32StageManager`
(`ESP32StageManager.py:33`), the UC2 ESP32 XYZ stage.  The card's second entry symbol, `StandaMotor`
(`imswitch/imcontrol/model/interfaces/standamotor.py:16`), is another motor controller of the repository and is not
served here (the separate package gh.imswitch/imswitch serves the StandaMotor of the upstream ImSwitch repository).
The repository's other ESP32 devices (LEDs, lasers, galvo scanner, objective turret) and its cameras and detectors are
other devices, not covered.

## Interface

- Reads: `x_um`, `y_um` and `z_um`, each a per-axis position in micrometres in the user frame.  Each read calls the
  upstream `getPosition()`, which queries `_motor.get_position()` and subtracts the configured stage offset.  When that
  query raises, the upstream logs it and returns its cached `_position` object itself (lines 605-617), the object the
  `position` property returns (`PositionerManager.py:59-63`); after a move that cache holds the commanded target
  (lines 542-544).  The driver refuses such a cached value with `MHS.DEVICE.FAULTED` instead of reporting it as a
  position (model review; the author's version returned it).
- Action: `x-cap.openuc2.move_xyz.v1` calls `move(value=(x, y, z), axis="XYZ", is_absolute=True, is_blocking=True)`.
  The upstream XYZ branch applies no soft-limit check (lines 534-544); the MHS envelope is the only bound.  The output
  is a fresh device query after the move.  A native move that raises (its docstring names a TimeoutError, lines
  432-443) or a failed read-back ends `unknown` (`MHS.OUTCOME.UNKNOWN`): the stage may have moved.
- Units: the µm of every position and limit hold only when the positioner setup gives the calibrated step sizes
  (`stepsizeX`, `stepsizeY`, `stepsizeZ` in µm/step, lines 55-60); the upstream defaults them to 1, so the hardware
  factory refuses to start without them (the setup reference's example uses 0.396, 0.396 and 0.3125).
- Not covered: the A (objective turret) axis, relative moves, homing (`home_x`/`home_y`/`home_z`/`home_a` and the
  frame-homing procedure), continuous moves (`moveForever`), strobed stage scans, TMC settings, joystick settings, Z
  synchronisation, `measure()` and `setupPIDcontroller()`.

## Limits

The three move inputs are `Limit.operator_required`.  The clone states no travel range of an installed stage: the
manager reads `minX`/`maxX`, `minY`/`maxY` and `minZ`/`maxZ` from the positioner setup and defaults them to
`-inf`/`inf` (lines 62-76), and the combined XYZ branch checks no soft limit (lines 534-544).  The card's limit hints
`SetupInfo.py:317-326` (500 and 3500) are `GalvoScannerInfo` positions in DAC units 0-4095, not stage travel.  Every
move is refused `MHS.SAFETY.LIMITS_UNSET` until the operator's `site-limits.json` supplies the travel.
`site-limits.example.json` holds example-only values (0 to 1000 µm on each axis) and is not a statement about any
installed stage.

## Safety

The device is an `R2` hardware driver: a motorised XYZ stage can drive the objective or the sample into a collision,
and the clone itself treats that crash as a hazard by requiring a safe Z lift before XY homing (lines 10-12 and
110-112).  No independent hardware e-stop is documented for this stage, so `estop_physical_ref` is not set and this
package claims no hardware stop outside MHS; the safe-state action is the SAFE-045 route.

The stop is the upstream's own: `stopAll()` sends `_motor.stop()` with no axis (lines 647-648).  The upstream uses it as
its immediate stop of all axes: the REST endpoint `stopAllAxes` (`PositionerController.py:739-746`, through
`forceStop`, lines 620-630), the collision handler (`UC2ConfigController.py:246-266`) and the cancellation of a running
Z-sync (lines 1066-1075), and the clone's agent guide lists it as the emergency stop for a move (`agents.md:283`).
What the command does on the wire and in the firmware is in uc2rest (`ESP32Manager.py:1, 51-53`), outside the clone,
and `stopAll()` returns nothing.  So the safe-state action `cap.motion.stop.v1` confirms the stop by state (model
review): after `stopAll()` it makes two device position queries 0.2 s apart (the package's own interval; the clone
states no settling time) and reports `stopped` only when both are fresh device reads, not the cached fallback, and
agree on X, Y and Z.  Otherwise it fails `MHS.SAFETY.SAFE_STATE_UNREACHED`; the e-stop, which runs the native stop and
then this action, is then reported unreached with the latch held and retried in the background.  The A axis receives
the same stop but is not confirmed, and the clone does not show whether the stop also switches the motor drivers off.
The author's version reported `stopped: true` and a completed e-stop whenever `stopAll()` returned, also for a stage
that kept moving or a position query that failed.

Limits of that confirmation: the reads come from `_motor.get_position()`, which the upstream documents as the live
device position read from the firmware (lines 739-749) but implements in uc2rest, outside the clone; an exact match
of the two reads is required, so a stage whose reported position jitters at rest is never confirmed (the e-stop stays
unreached, the safe direction); and a stage moving slower than its position resolution over 0.2 s would pass.
Whether uc2rest delivers `stop()` while another thread waits in a blocking `move_xyz` is not shown in the clone; the
upstream's own cancellations call `stopAll()` from another thread while their blocking moves run (lines 866-875 and
1066-1075).  If the stop or the reads wait behind the move, the e-stop is reported unreached when its budget ends.

The e-stop sends `stopAll()` twice (the `@estop` method and the safe-state action), as the runtime does for every
direct driver whose stop is bound both ways; a repeated stop is harmless.  The teardown sends `stopAll()` before the
hardware factory's `closeEvent` closes the ESP32 client, because the clone warns that a stage moving when its command
stream breaks does not stop cleanly (`agents.md:893-896`).  The package has no `@reset` hook and no re-enable: a reset
only releases the latch, and the next move command is the new start (SAFE-042).

Constructing the upstream manager is not side-effect-free: its constructor switches the motors on (lines 211-214),
commands a -1 then +1 relative move on every configured axis and homes on startup when `homeOnStart<axis>` is set
(lines 306-319), and it pushes TMC, hard-limit and joystick settings to the controller.  The hardware factory refuses
`frameHomeOnStart`: the upstream would then start frame homing in a background thread during construction (lines
350-352 and 988-992), whose steps check only the procedure's own cancel event (lines 921-927) and would start motion
again after an MHS stop.  An operator must review the start-up writes and moves together with the hardware backend.

## Mock

The clone has no simulator or mock of `ESP32StageManager`.  `MockPositionerManager` is a tiny positioner with a
different surface (`move(dist, axis)` and `get_position()`, `MockPositionerManager.py:22-30`), and
`VirtualStageManager` is a separate simulated stage that needs a `VirtualMicroscope` and drives its own `_positioner`
(`VirtualStageManager.py:6-38` and 48-66); neither is a drop-in stand-in for the ESP32 manager's
`move`/`getPosition`/`stopAll`/`closeEvent` surface.  The card's `mock_strategy` hint points at
`SetupInfo.py:348 MockXXInfo`, which is an empty setup-info dataclass, not a stage simulator.  The package therefore
ships an in-memory fake at the level of the manager's public members.  It keeps the upstream semantics the driver
relies on: a device query returns a new dict, a failed query returns the cached `_position` object, the `position`
property returns that cache, and an XYZ move writes the commanded target into the cache.  It completes a move at once
and models no motor time, acceleration, step loss, backlash, uc2rest client, serial protocol or firmware reply.  Two
switches give the negative paths of the tests: `keeps_moving` (a stage that does not stop) and `query_fails` (a
failed position query); they are placeholders, not behaviour the clone shows.  The position values are placeholders,
marked in `fake.py`; no value from the fake is a Fact, a Limit or a reference.  The only actuating action has three
`operator_required` inputs, so the gate's e-stop-during-an-action check has no input it may start without an overlay
and is not exercised; the fake completes a move at once, so it cannot show that a moving stage stops.

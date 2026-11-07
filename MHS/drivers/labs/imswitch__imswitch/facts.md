# Facts and tags for gh.imswitch/imswitch

This package implements one device of the ImSwitch repository: the Standa motor controller for a motorized rotation
mount.  Every fact cites the clone at commit `37bf1df6de0ee4746b05bef9684c782e4995b2e8`; the same facts are written
into `driver.py` (`facts = [...]`), and `reference.json` is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| StandaRotatorManager drives a Standa-branded motor controller, for example an 8SMC5 for a motorized rotation mount | upstream_code | imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:5-8 |
| The rotator's absolute position is in degrees | upstream_code | imswitch/imcontrol/controller/controllers/RotatorController.py:57-63 |
| A relative rotator step is in degrees | upstream_code | imswitch/imcontrol/controller/controllers/RotatorController.py:52 |
| The rotator widget displays the position in deg and the speed in mrpm | upstream_code | imswitch/imcontrol/view/widgets/RotatorWidget.py:27-34 |
| The speed the rotator widget passes on is in mrpm | upstream_code | imswitch/imcontrol/view/widgets/RotatorWidget.py:93-95 |
| StandaMotor is constructed with the controller device id, the libximc directory, steps_per_turn and microsteps_per_step | upstream_code | imswitch/imcontrol/model/interfaces/standamotor.py:18-24 |
| The upstream manager reads motorListIndex, ximcLibLocation, stepsPerTurn and microstepsPerStep from the setup and passes them to StandaMotor | upstream_code | imswitch/imcontrol/model/managers/rotators/StandaRotatorManager.py:15-20 |
| The upstream class opens the controller through libximc and sets the default sync-in and sync-out settings after opening it | upstream_code | imswitch/imcontrol/model/interfaces/standamotor.py:25-50 |
| close closes the libximc device | upstream_code | imswitch/imcontrol/model/interfaces/standamotor.py:52-54 |
| get_pos waits for the motor to stop and returns the angle in degrees from the controller's step and microstep position | upstream_code | imswitch/imcontrol/model/interfaces/standamotor.py:85-90 |
| dist_translate_inv converts steps and microsteps to degrees with steps_per_turn and microsteps_per_step | upstream_code | imswitch/imcontrol/model/interfaces/standamotor.py:120-122 |
| moveabs and moverel convert an angle in degrees to steps and microsteps and send command_move or command_movr | upstream_code | imswitch/imcontrol/model/interfaces/standamotor.py:92-100 |
| wait_for_stop sends command_wait_for_stop with an interval | upstream_code | imswitch/imcontrol/model/interfaces/standamotor.py:102-103 |
| stop_cont_rot sends command_sstp and start_cont_rot sends command_right | upstream_code | imswitch/imcontrol/model/interfaces/standamotor.py:146-150 |

## The other entry symbols of the card

The card lists several entry symbols for the application.  This package implements the first confirmed device class,
`imswitch.imcontrol.model.interfaces.standamotor:StandaMotor`, as the playbook asks for one device class per
repository.  The others are not part of this package:

* `imswitch.imcontrol.view.guitools.ViewSetupInfo:ViewSetupInfo` is the dataclass that represents the hardware
  configuration JSON (imswitch/imcontrol/view/guitools/ViewSetupInfo.py:34).
* `imswitch.imcontrol.controller.controllers.HyphaController:HyphaController` is the application controller that
  publishes the whole microscope over Hypha (imswitch/imcontrol/controller/controllers/HyphaController.py:138).
* `imswitch.imcontrol.model.interfaces.pyicic.IC_Camera:IC_Camera` is one camera interface
  (imswitch/imcontrol/model/interfaces/pyicic/IC_Camera.py:32); its main output is an image array.
* `imswitch.imcontrol.model.managers.positioners.SmarACTPositionerManager:SmarACTPositionerManager` is another
  multi-axis positioner manager (imswitch/imcontrol/model/managers/positioners/SmarACTPositionerManager.py:25).

## Units and ranges

* The position read and the native move are in degrees (`RotatorController.py:57-63`, `standamotor.py:92-100`); the
  capability input is the catalogue's rad, converted once at the driver boundary.
* The speed is in mrpm (`RotatorWidget.py:93-95`, `standamotor.py:138-139`); this package does not expose a speed
  write, because the clone states no speed range.
* The clone states no travel range of the rotation mount.  `dist_translate` maps any angle to steps and microsteps
  (`standamotor.py:108-122`), and the range depends on the mounted stage.  The joint input is therefore
  `Limit.operator_required`: without an operator overlay every move is refused `MHS.SAFETY.LIMITS_UNSET`.
  `site-limits.example.json` supplies an example envelope of one turn in either direction; it is an example, not a
  statement about a unit.

## Safety

The e-stop and the `cap.motion.stop.v1` action both call the native stop `stop_cont_rot` (command_sstp,
`standamotor.py:149-150`).  No line of the clone documents an independent hardware e-stop; the package is R1, so
SAFE-045 does not apply and `estop_physical_ref` is not set.  `safe_state` is "rotation stopped (the controller's stop
command, command_sstp)".

This package is model-authored and unreviewed (`driver.lock.json` `authored_by` kind `model`, `reviewed_by` null).
Nothing here was tested on hardware; the acceptance gate runs the fake backend.

## The fake

The card's mock strategy prefers an upstream simulator or mock.  The upstream `MockStandaMotor`
(`standamotor.py:178-201`) implements only `get_pos`, `moverel`, `moveabs`, `test_info` and `close` (and
`startmove`/`stopmove`, which `StandaMotor` does not define); it lacks `wait_for_stop` and `stop_cont_rot`, and it
lives in the module of the real driver.  This package therefore uses its own `fake.py`: an in-memory
`FakeStandaMotor` with only members that exist on `StandaMotor`, keeping the position in degrees and recording the
calls it received.  The starting position and flags in it are placeholder test data, not facts.

## Deviations from the card

The card's `decision` is `direct-driver`; its `helper` field names `PythonObjectDriver`.  The package is a direct
`Driver` with a `native.py` factory, because the upstream constructor needs the libximc directory, the controller
index and the two step counts (`standamotor.py:18-24`), and the device has a native stop command.  This is the
"DEVIATION FROM THE CARD" recorded in `RESULT.json`.

Tags: rotation mount, standa, libximc, motion, imswitch

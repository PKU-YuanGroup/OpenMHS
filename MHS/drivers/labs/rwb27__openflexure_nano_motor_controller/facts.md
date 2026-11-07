# Facts and tags for gh.rwb27/openflexure_nano_motor_controller

Every fact cites its source at commit `18a19977dde0cd78f14154c41073a857e2332e54`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.rst) or `upstream_code` (`path/in/clone.py:LINE`).  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The board reports its position as three integers with the p? query | upstream_code | openflexure_stage/stage.py:45-46 |
| step_time is read with dt? and written with dt <int>, in microseconds | upstream_code | openflexure_stage/stage.py:47-50 |
| ramp_time is read with ramp_time? and written with ramp_time <int>, in microseconds | upstream_code | openflexure_stage/stage.py:51-57 |
| move_rel sends mr <dx> <dy> <dz> for a three-axis relative move, or mr<axis> <n> for one axis | upstream_code | openflexure_stage/stage.py:186-196 |
| move_abs queries position and then calls move_rel with the difference, because the stage only accepts relative moves | upstream_code | openflexure_stage/stage.py:202-211 |
| focus_rel moves the stage in Z by the given number of micro steps | upstream_code | openflexure_stage/stage.py:213-215 |
| release_motors sends release, which de-energises the stepper motor coils | upstream_code | openflexure_stage/stage.py:198-200 |
| Endstops.status reads endstops? as -1, 0 or 1 per axis; maxima reads max_p? and writes max <d> <d> <d> | upstream_code | openflexure_stage/stage.py:395-399 |
| Endstops.home sends home_min or home_max with the axis bitmap built from the axes list and the direction min, max or both | upstream_code | openflexure_stage/stage.py:401-424 |
| The default serial port settings are 115200 baud, 8 data bits, no parity and one stop bit | upstream_code | openflexure_stage/stage.py:41 |
| The Python module reads the version string at construction and requires firmware v0.4 | upstream_code | openflexure_stage/stage.py:77-87 |
| The firmware defines three stepper motors for X, Y and Z | upstream_code | arduino_code/openflexure_nano_motor_controller/openflexure_nano_motor_controller.ino:77-78 |
| The firmware's release command de-energises every motor coil | upstream_code | arduino_code/openflexure_nano_motor_controller/openflexure_nano_motor_controller.ino:680-683 |
| The maximum endstop positions are stored on the board and set with max <d> <d> <d> | upstream_code | arduino_code/openflexure_nano_motor_controller/openflexure_nano_motor_controller.ino:771-784 |

Limits: no text file of the clone states a travel range, a minimum step delay range or a ramp time range.  The
firmware's homing search distances (`3500`, `-100000`, `-2000`, `150000` at
`arduino_code/openflexure_nano_motor_controller/openflexure_nano_motor_controller.ino:258-259,317-318`) are internal
search moves, not the travel envelope, and the uninitialised defaults of `min_step_delay` and `ramp_time`
(`arduino_code/openflexure_nano_motor_controller/openflexure_nano_motor_controller.ino:130-137`) are not device
limits.  Every relative, absolute and focus input is therefore
`Limit.operator_required`: the site supplies the envelope in `site-limits.json` (the example overlay shows the shape),
and until then every motion call is refused `MHS.SAFETY.LIMITS_UNSET`.  The maximum positions the firmware enforces
for soft endstops are themselves operator-set with `max <d> <d> <d>` (stage.py:397-399).

Safety: the firmware and the Python class expose no separate stop command.  The `@estop` method and the safe-state
action `x-cap.rwb27.release_motors.v1` both call the native `release_motors()` (`release`), which de-energises every
stepper coil (stage.py:198-200, firmware:680-683).  No text of the clone documents an independent hardware emergency
stop, so `estop_physical_ref` is not set.  The card's declared floor and the device are R1 (small stepper motion of a
microscope stage, reversible and bounded by the operator envelope); SAFE-045's independent stop is therefore not
required, and the safe-state action is declared anyway.  The stage has no independent position limit source in the
clone: the endstop maxima are stored on the board and set by the operator.

Entry symbols: `openflexure_stage.stage:OpenFlexureStage` is the implemented device class and `native`.
`openflexure_stage.basic_serial_instrument:BasicSerialInstrument` is its serial transport base, reached only through
`OpenFlexureStage`.  `openflexure_stage.stage:Endstops` is the optional module object at `stage.endstops`, used by the
two endstop reads and the home action.  `openflexure_stage.stage:LightSensor` is another optional module (intensity,
integration time and gain, stage.py:317-377); this package does not expose it because the intensity is an arbitrary
unit and the module is compile-time optional.  No other device class of the repository is claimed.

Fake: `fake.py` is an in-memory stand-in with the upstream names only.  Its start position (0, 0, 0), step delay
(1000 us), ramp time (0 us), endstop maxima (1000 steps per axis), endstop status (0, 0, 0) and version string
("OpenFlexure Motor Board v0.4") are test data marked `# placeholder`; they are not facts and must not be copied into
a Fact, a Limit or the reference.  The optional endstop state and maxima reads return null when the fake or the real
board has no endstop module.

Tags: microscope, stage, stepper, serial, openflexure

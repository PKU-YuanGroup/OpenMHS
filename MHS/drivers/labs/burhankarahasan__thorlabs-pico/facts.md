# Facts and tags for gh.burhankarahasan/thorlabs-pico

Every fact cites its source at commit `91898e3a55a925ca36ce24d53997351c1b947779`: `upstream_code` (a Python or
Arduino file of the clone) or `vendor_doc` (the README text). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The controller speaks a text protocol: commands end with a newline and replies start with OK:, ERROR: or STATUS: | upstream_code | stepper_controller.py:10-12 |
| A command is written as `<command>\n` and one reply line is read | upstream_code | stepper_controller.py:56-68 |
| SPEED_RPS sets the target speed in revolutions per second and accepts negative values for reverse | upstream_code | stepper_controller.py:70-81 |
| RAMP sets the acceleration/deceleration rate in steps/sec^2 | upstream_code | stepper_controller.py:126-137 |
| STOP ramps the motor down to zero speed | upstream_code | stepper_controller.py:96-104 |
| ENABLE enables the stepper driver and DISABLE disables it (the docstring says it cuts power) | upstream_code | stepper_controller.py:106-124 |
| STATUS returns `(current_rps, target_rps, position in steps)`, or None when the reply cannot be parsed | upstream_code | stepper_controller.py:139-154 |
| The example firmware defines 200 steps per revolution | upstream_code | accel_stepper_serial.ino:7 |
| The example firmware sets the AccelStepper maximum speed to 10000 steps/s | upstream_code | accel_stepper_serial.ino:27 |
| The example firmware starts with a ramp rate of 10 steps/sec^2 | upstream_code | accel_stepper_serial.ino:13 |
| The README says to match the microstepping, baudrate and library configuration to the user's stepper/driver hardware | vendor_doc | README.md:29 |
| The README presents the GUI rotation speed range as the user's own limits ("Change to your limits") | vendor_doc | README.md:408-411 |
| The README says the emergency procedure is to click the GUI EMERGENCY STOP ALL button and, if needed, to turn the power off physically | vendor_doc | README.md:435-439 |

## Units

- `current_rps` and `target_rps`: revolutions per second (`Hz` in UCUM, a frequency of 1/s). Positive is clockwise
  and negative is counter-clockwise (README.md:145-147).
- `position_steps`: motor steps (`1`), the value the firmware prints as `stepper.currentPosition()`
  (accel_stepper_serial.ino:128-135).
- `ramp_rate`: steps/second^2 (`Hz/s`); the upstream docstring names steps/sec^2 (stepper_controller.py:131).

## Limits

All numeric inputs are `Limit.operator_required`, and every write or invoke is refused
`MHS.SAFETY.LIMITS_UNSET` until the site supplies a range:

| parameter | limit | why |
|---|---|---|
| `target_rps` (the one writable state field) | operator_required | No text file states a safe speed range for the installed stepper/driver. README.md:29 says the example firmware and library settings are matched to the hardware, and README.md:408-411 calls the GUI range the user's own limits. The example firmware's 10000 steps/s (accel_stepper_serial.ino:27) belongs to the example configuration, not to a bound. |
| `ramp_rate` (`x-cap.burhankarahasan.set_ramp_rate.v1` input) | operator_required | The example firmware starts at 10 steps/sec^2 (accel_stepper_serial.ino:13), but README.md:29 says that configuration is an example to adapt, so it is not a device bound. |

`site-limits.example.json` shows the overlay: it fills both operator bounds for the example bench and may only
narrow them. It is an example, not a statement about any installed stepper.

## Safety

- The e-stop is the upstream `stop()`: it sends `STOP` (stepper_controller.py:96-104), which sets the example
  firmware's target speed to zero (accel_stepper_serial.ino:79-81); the firmware then ramps the current speed down
  in 10 steps/s increments (accel_stepper_serial.ino:39-48). It is a software stop, not an independent hardware
  stop.
- The safe-state action `cap.motion.stop.v1` calls the same native `stop()` and reports `stopped: true` with the
  position read back from STATUS.
- The README's emergency procedure adds a physical power-off after the GUI emergency stop (README.md:435-439); the
  driver does not claim to control that power path.
- Risk class: R1 (a small motorized rotation axis; the card's floor and the motion class floor are R1). No
  independent hardware e-stop is declared, and none is required at R1.
- This package is model-authored and unreviewed. No hardware run was made; the acceptance gate checks the fake
  backend only. At R1 the loader's unreviewed-model refusal of the hardware backend does not apply, so this is a
  claim about this package only: the hardware path was not exercised.

## Not covered

- `lts_controller:ThorlabsLTSController`, the second entry symbol of the card, is a separate Thorlabs LTS linear
  stage (a Windows Kinesis or pylablib device, lts_controller.py:1-31); it is not exposed by this package.
- `PicoStepperController.set_speed_steps` is not exposed: the driver uses one speed unit (RPS) so that the write and
  the read of the target are the same physical quantity.
- The serial protocol's own `ERROR:` replies are reduced to the upstream boolean return; the driver raises
  `MHS.DEVICE.FAULTED` when a command is not acknowledged.

Tags: stepper, rotation, pico, serial, motion

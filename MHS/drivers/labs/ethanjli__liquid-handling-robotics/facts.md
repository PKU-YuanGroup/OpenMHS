# Facts and tags for gh.ethanjli/liquid-handling-robotics

Every fact cites its source at commit `fc7043558072e77981206ae123dfd3a24ef89029`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The x-axis reports its physical position in centimetres | upstream_code | lhrhost/robot/x_axis.py:100 |
| The x-axis constructs a linear-actuator protocol named XAxis on channel x | upstream_code | lhrhost/robot/x_axis.py:86 |
| A physical position is converted from the sensor position with the slope and intercept of a linear calibration | upstream_code | lhrhost/robot/axes.py:344-356 |
| Reading the physical position requests the Position channel and converts the last sensor position | upstream_code | lhrhost/robot/axes.py:202-211 |
| move_by_physical_delta reads the current physical position, adds the delta and returns the final physical displacement | upstream_code | lhrhost/robot/axes.py:158-166 |
| The feedback controller clamps its target position to the position limits Low and High | vendor_doc | docs/source/messages/linearactuator.rst:240 |
| Actuator effort, roughly the signed motor duty cycle, must be between -255 and 255 inclusive | vendor_doc | docs/source/messages/linearactuator.rst:174 |
| An actuator effort of 0 puts the motor in brake mode | vendor_doc | docs/source/messages/linearactuator.rst:540 |
| A forwards actuator effort below the Low limit is set to 0 to brake the motor | vendor_doc | docs/source/messages/linearactuator.rst:300 |
| The robot's Arduino exposes a USB serial command interface for positioning commands | vendor_doc | README.rst:20 |

Limits: the relative move input is `Limit.operator_required`. No text file of the clone states a travel range for the
x-axis: the position limits are parameters of the assembled robot (the calibration and the preset trees under
`calibrations/`), so the site supplies the allowed relative travel (`site-limits.example.json` shows the overlay).
The motor duty limits are not a driver input here: they are only written as zero by the safe-state action and the
e-stop, where the value 0 is the brake mode the manual describes (`docs/source/messages/linearactuator.rst:174`).

Safety: the e-stop and the safe-state action `x-cap.ethanjli.axis_stop.v1` both call the native
`set_motor_limits` with all four limits zero, so the feedback controller brakes instead of driving the axis.
`cap.motion.stop.v1` does not fit: its schema carries a deceleration in m/s2, the upstream high-level Axis has no
deceleration control, and a safe-state action takes no input. No line of the clone documents an independent hardware
e-stop, so `estop_physical_ref` is not set; the safe-state action satisfies SAFE-045 for this R2 hardware driver.

Tags: liquid handling, robot, linear actuator, x-axis, arduino, asyncio

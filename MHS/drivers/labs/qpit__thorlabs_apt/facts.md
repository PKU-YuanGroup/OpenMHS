# Facts and tags for gh.qpit/thorlabs_apt

Every fact cites its source at commit `7b5c84607c22684cc896e3c337045b9358ee7c47`.  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The package wraps Thorlabs' APT.dll shared library | vendor_doc | README.md:3 |
| The package only works on Windows because it is based on APT.dll | vendor_doc | README.md:7 |
| The README lists K10CR1, LTS150 and other motors as reported working devices and says the package should work with all motors supported by APT | vendor_doc | README.md:18-29 |
| Motor(serial_number) stores the serial number and calls InitHWDevice(serial_number) in its constructor | upstream_code | thorlabs_apt/core.py:144-151 |
| move_to(value, blocking=False) sends MOT_MoveAbsoluteEx and move_by(value, blocking=False) sends MOT_MoveRelativeEx | upstream_code | thorlabs_apt/core.py:763-796 |
| move_home(blocking=False) sends MOT_MoveHome | upstream_code | thorlabs_apt/core.py:817-830 |
| move_velocity(direction) sends MOT_MoveVelocity | upstream_code | thorlabs_apt/core.py:832-843 |
| MOVE_FWD is 1 and MOVE_REV is 2 | upstream_code | thorlabs_apt/core.py:43-47 |
| stop_profiled() sends MOT_StopProfiled | upstream_code | thorlabs_apt/core.py:845-852 |
| position reads MOT_GetPosition | upstream_code | thorlabs_apt/core.py:799-812 |
| get_stage_axis_info returns (minimum position, maximum position, stage units, pitch); the stage units are STAGE_UNITS_MM = 1 and STAGE_UNITS_DEG = 2 | upstream_code | thorlabs_apt/core.py:574-597 |
| get_hardware_limit_switches returns reverse and forward modes; HWLIMSWITCH_IGNORE = 1, HWLIMSWITCH_MAKES = 2, HWLIMSWITCH_BREAKS = 3, HWLIMSWITCH_MAKES_HOMEONLY = 4 and HWLIMSWITCH_BREAKS_HOMEONLY = 5 | upstream_code | thorlabs_apt/core.py:636-664 |
| set_hardware_limit_switches(rev, fwd) sends MOT_SetHWLimSwitches | upstream_code | thorlabs_apt/core.py:670-706 |
| get_move_home_parameters returns (direction, limiting switch, velocity, zero offset) | upstream_code | thorlabs_apt/core.py:444-466 |
| HOME_FWD is 1, HOME_REV is 2, HOMELIMSW_FWD is 4 and HOMELIMSW_REV is 1 | upstream_code | thorlabs_apt/core.py:9-20 |
| get_velocity_parameters returns (minimum velocity, acceleration, maximum velocity) | upstream_code | thorlabs_apt/core.py:344-363 |
| set_velocity_parameters(min_vel, accn, max_vel) sends MOT_SetVelParams; the docstring says the minimum velocity is always 0 and is ignored | upstream_code | thorlabs_apt/core.py:365-393 |
| get_velocity_parameter_limits returns the maximum acceleration and the maximum velocity of the motor | upstream_code | thorlabs_apt/core.py:395-418 |
| is_in_motion is derived from status bits 0x00000010, 0x00000020, 0x00000040, 0x00000080 and 0x00000200 | upstream_code | thorlabs_apt/core.py:232-239 |
| is_channel_enabled uses status bit 0x80000000; enable() and disable() send MOT_EnableHWChannel and MOT_DisableHWChannel | upstream_code | thorlabs_apt/core.py:286-333 |
| has_homing_been_completed uses status bit 0x00000400, is_settled uses 0x00002000 and motion_error uses 0x00004000 | upstream_code | thorlabs_apt/core.py:241-284 |
| active_channel is 0 for channel 1 and 1 for channel 2 | upstream_code | thorlabs_apt/core.py:299-307 |

Limits: `velocity_maximum` and `acceleration` are `Limit.operator_required`.  The clone returns the real bounds from
the controller at run time (`get_velocity_parameter_limits`, thorlabs_apt/core.py:395-418) and states no fixed
number.  `position` and `distance` on the move actions are also `Limit.operator_required` because
`get_stage_axis_info` reads the travel range of the installed stage at run time (thorlabs_apt/core.py:574-597).
`site-limits.example.json` shows one possible operator overlay; its numbers are examples, not device data.

The hardware limit-switch modes, the homing direction and the homing limit switch are closed sets taken from the
module constants (thorlabs_apt/core.py:9-41), not from an operator.

Safety: the e-stop and the safe-state action `x-cap.qpit.stop.v1` both call `stop_profiled()` (`MOT_StopProfiled`,
thorlabs_apt/core.py:845-852).  No line of the clone documents an independent hardware e-stop, so
`estop_physical_ref` is not set; this package is R1, and the loader does not refuse an unreviewed R1 hardware backend.
The physical e-stop of the bench stays authoritative.

Tags: thorlabs, apt, motor, stage, motion, windows

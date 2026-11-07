# Facts and tags for gh.accelerationconsortium/opentrons-ot2

Every fact cites its source at commit `9ba663504dcf8b27eb1b9e777a84c01667202893`: `upstream_code` for the clone's
code or comments and `vendor_doc` for its documentation text. The driver repeats each fact; the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| OT2MotionController is a thin wrapper around the existing Opentrons driver classes; it does not reimplement the low-level serial communication | upstream_code | src/unitelabs/opentrons_ot2/io/motion.py:1-11 |
| The controller serializes hardware calls on one asyncio.Lock, wrapped in a _TimedLock with lock_timeout_s, because the SmoothieDriver has a single serial connection | upstream_code | src/unitelabs/opentrons_ot2/io/motion.py:223-226 |
| stop() is documented as an emergency stop that halts all motion: it acquires that lock and then calls SmoothieDriver.hard_halt(); the clone does not implement hard_halt itself | upstream_code | src/unitelabs/opentrons_ot2/io/motion.py:775-778 |
| move(target, speed=None) awaits SmoothieDriver.move while it holds the lock; target maps axes to positions and speed is in mm/sec | upstream_code | src/unitelabs/opentrons_ot2/io/motion.py:450-468 |
| move_through documents its targets as axis letters mapped to absolute mm and its speeds in mm/sec | upstream_code | src/unitelabs/opentrons_ot2/io/motion.py:512-514 |
| home(axes) holds the lock while it homes the gantry and mount axes together and then each plunger axis B/C on its own at the attached pipette's run current or a safe default, because the bare driver would home a plunger at the 0.05 A idle current, which lacks the torque to reach the endstop | upstream_code | src/unitelabs/opentrons_ot2/io/motion.py:387-418 |
| get_position() calls SmoothieDriver.update_position while it holds the lock and returns the updated cached position | upstream_code | src/unitelabs/opentrons_ot2/io/motion.py:647-655 |
| aspirate moves the plunger axis up from its cached position by volume_ul / ul_per_mm at flow_rate_ul_s / ul_per_mm mm/s while it holds the lock; the caller must first place the plunger at its bottom | upstream_code | src/unitelabs/opentrons_ot2/io/motion.py:683-695 |
| dispense moves the plunger axis down from its cached position by volume_ul / ul_per_mm at flow_rate_ul_s / ul_per_mm mm/s while it holds the lock | upstream_code | src/unitelabs/opentrons_ot2/io/motion.py:705-716 |
| reset_from_error() clears the alarm lock with M999 and smoothie_reset() performs a full GPIO reset of the Smoothie, each while holding the lock | upstream_code | src/unitelabs/opentrons_ot2/io/motion.py:890-898 |
| After reset_from_error or smoothie_reset the homed flags are all false and the operator must re-home before moving; smoothie_reset is the more drastic GPIO pulse and reset_from_error is preferred for alarm recovery | vendor_doc | alarm_reset_plan.md:37-38 |
| The clone's plan states that no reliable alarm-state signal is available without modifying the driver and that all-false homed flags cannot be told apart from a robot not homed since boot | vendor_doc | alarm_reset_plan.md:35-36 |
| read_pipette_model(mount) and read_pipette_id(mount) read the pipette EEPROM while holding the lock and return an empty string when nothing is read (no pipette attached, or an unreadable id) | upstream_code | src/unitelabs/opentrons_ot2/io/motion.py:746-756 |
| set_button_light sets the RGB front-button LED, set_rail_lights switches the deck rail lights, get_button_light returns an (r, g, b) tuple, get_rail_lights a bool, and read_button and read_door_switch return the front-button and door-switch states | upstream_code | src/unitelabs/opentrons_ot2/io/motion.py:790-849 |
| get_serial_number reads /var/serial and returns an empty string when it is unavailable | upstream_code | src/unitelabs/opentrons_ot2/io/motion.py:373-378 |
| get_firmware_version queries the Smoothie firmware version | upstream_code | src/unitelabs/opentrons_ot2/io/motion.py:853-856 |
| is_simulating reports the SmoothieDriver.simulating flag | upstream_code | src/unitelabs/opentrons_ot2/io/motion.py:348-351 |
| build(port, simulate=False) sets up the GPIO character device and builds a _RaisingSmoothieDriver on the serial port; simulate=True builds a simulating GPIO and a SmoothieDriver without a connection | upstream_code | src/unitelabs/opentrons_ot2/io/motion.py:228-278 |
| _RaisingSmoothieDriver raises SmoothieAlarm on the first alarm reply while a hard halt is set (and clears it) and SmoothieError on an error reply then; outside a hard halt it raises SmoothieError on every alarm or error reply, including the 'alarm lock' and 'after halt you should home' replies that the upstream driver swallows | upstream_code | src/unitelabs/opentrons_ot2/io/motion.py:82-103 |
| A comment in move_through states that after a mid-line alarm the alarm path inside _send_command has already reset and homed | upstream_code | src/unitelabs/opentrons_ot2/io/motion.py:537-543 |
| The OT-2 axes are X, Y, Z, A, B and C: X is the gantry, Y moves toward the front window when negative, Z/A are the left/right mount vertical axes and B/C the left/right plungers; each axis has its limit switch at its positive end | upstream_code | src/unitelabs/opentrons_ot2/features/motion_control.py:180-185 |
| A feature-layer comment states that Opentrons provides no fixed floor for the Z/A mount axes (HOMED_POSITION defines only the top) and that a replayed robot-server request executed a machine position below 0 (-21.44 mm) without error | upstream_code | src/unitelabs/opentrons_ot2/features/motion_control.py:100-105 |
| The clone's feature layer states that the physical limit switches are the real safety boundary for Z/A and that no synthetic software floor is enforced there; the X/Y 0.0 floor is marked untested | upstream_code | src/unitelabs/opentrons_ot2/features/motion_control.py:519-526 |
| The feature layer's _check_bounds refuses a position outside the controller's axis_bounds maximum or the feature's lower limit for the axis | upstream_code | src/unitelabs/opentrons_ot2/features/motion_control.py:543-549 |
| The feature layer's emergency_stop is documented to immediately halt all motion; it calls the controller stop and returns 'Emergency stop executed. Re-home required before resuming.' | upstream_code | src/unitelabs/opentrons_ot2/features/motion_control.py:486-496 |
| The upstream simulation tests state that in simulation emergency_stop sets an internal flag only, with no actual halt, and that pause and resume do nothing | upstream_code | tests/features/test_motion_simulation.py:16-19 |
| The module imports opentrons.drivers.smoothie_drivers.driver_3_0.SmoothieDriver; the hard-halt and serial details are in that dependency and are not shown in the clone | upstream_code | src/unitelabs/opentrons_ot2/io/motion.py:24 |
| The clone depends on opentrons 8.8.1 below Python 3.12 and on opentrons 9.0.0 from Python 3.12 | upstream_code | pyproject.toml:27-28 |

## Limits

The clone states no machine or axis travel range, no usable pipette volume, no volume-to-plunger conversion and no
flow-rate range in a text file; those values depend on the installed pipette and the robot's configuration. The
driver therefore declares every numeric action input as `Limit.operator_required`. A call is refused
`MHS.SAFETY.LIMITS_UNSET` before any native call until the operator supplies the values in `site-limits.json`.
`site-limits.example.json` is example operator data, not a statement about any robot, and the conformance fixture
values are placeholders. The positions are Smoothie machine positions passed unchanged to `OT2MotionController.move`
(motion.py:450-468; the feature layer calls such a value a machine position, motion_control.py:100-105). The SiLA
feature layer refuses a position outside the controller's runtime `axis_bounds` maximum or its own lower limit
(motion_control.py:543-549); this driver calls the controller directly, so that check is not applied and only the
operator overlay bounds a move. Z/A have no software floor in the clone (motion_control.py:100-109, 519-526).

The feature layer's `set_active_currents` docstring states a hardware limit of 0.0-2.0 A per axis
(`src/unitelabs/opentrons_ot2/features/motion_control.py:711`), but this package does not bind the current setters:
the current values are a service setting, not part of the motion or pipetting interface exercised here, and the
installed pipette's run currents are owned by the upstream hardware layer.

## Safety

The native stop is `OT2MotionController.stop`, documented as an emergency stop that halts all motion: it acquires the
controller's single hardware lock and then calls `SmoothieDriver.hard_halt()`
(`src/unitelabs/opentrons_ot2/io/motion.py:775-778`). The clone does not show the `hard_halt` implementation; it is in
the Opentrons dependency imported at line 24, so this package does not claim sensed quiescence, a stopped queue or a
safety-rated halt, and the clone offers no state read that would confirm the halt (alarm_reset_plan.md:35-36).

`move`, `home`, `aspirate` and `dispense` hold the same lock for the whole SmoothieDriver call, so the stop can go out
only once a running move or home has released it. The runtime cancels every running action of the device before it
starts the stop path; with a dependency whose wait ends on that cancellation the halt goes out within milliseconds
(package test, fake knob `_move_s`). A dependency that keeps the lock through the cancellation keeps the halt waiting
until its own reply arrives: the e-stop then ends `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held and the
background retry sends the halt later (package test, knob `_hold_lock_on_cancel`). The clone does not show which of
the two the Opentrons stack does. The upstream's own SiLA `emergency_stop` only awaits the controller's stop
(motion_control.py:495), so a move running through the same controller keeps it waiting until the move releases
the lock (motion.py:467-468).

The e-stop is the `@estop` method; the input-free `x-cap.accelerationconsortium.halt_motion.v1` action is the declared
safe state and calls the same native stop. The runtime also runs that action after every cancelled action, and the
re-enable declaration makes it run the stop path again once in-flight commands have settled, so one e-stop during a
move sends `hard_halt` up to five times (estop method and halt action twice each, plus the cancelled action's safe
state); each call takes the lock again.

After a halt the clone requires a re-home (motion_control.py:486-496; alarm_reset_plan.md:37-38), and its comments
show that later Smoothie replies after a halt are raised as `SmoothieAlarm` or `SmoothieError` (motion.py:82-103) and
that the alarm path inside `_send_command` resets and homes (motion.py:537-543). The driver therefore marks itself
halted before every native stop (the e-stop and the halt action) and then sends no Smoothie command except the
re-enable: the Cartesian, six-axis, home, aspirate and dispense actions are refused `MHS.DEVICE.PRECONDITION_UNMET`,
and the position, firmware and pipette reads are left out of the state. A read or action already past that check
when the halt lands can still send one query, and an action that sees a halt land during its native call ends
`MHS.OUTCOME.UNKNOWN` without querying the position. The flag lives in the driver object of this process: a restarted
endpoint does not know of an earlier halt.

The input-free `x-cap.accelerationconsortium.reenable.v1` action is declared with `reenable=True`: it clears the
alarm lock with `reset_from_error()` (M999) and homes all six axes, and only after both returned without a new halt
does the driver accept motion again. There is no `@reset` hook, so the runtime's reset only releases the MHS latch and
never clears the fault or moves anything. The re-enable is refused while latched; the first Smoothie command after a
halt may meet the halt alarm, so it can fail once and must then be sent again. A cancellation between
`reset_from_error()` and `home()` clears the alarm lock but leaves the axes un-homed and the driver halted, so the
operator retries the re-enable. No `estop_terminal` is declared: the clone's recovery uses `reset_from_error` and a
re-home, not a new native session.

## Tags

`opentrons`, `ot-2`, `liquid-handler`, `gantry`, `pipette`, `motion`, `asyncio`

## Coverage and gaps

- Bound: the Smoothie position, firmware, serial number, pipette models/ids, button and rail lights, button and door
  switches, the simulator flag; writes to the button LED and rail lights; the Cartesian pose action, the six-axis
  extension move, the full-home extension, the aspirate and dispense primitives, the halt (safe state) and the
  re-enable action.
- NOT COVERED: `move_relative`, `move_through`, `probe_axis`, `pause`/`resume` (the native pause is a software flag
  with no sensed state, so it is not reported as quiescence), `smoothie_reset` (the more drastic GPIO reset),
  `update_steps_per_mm`, `update_pipette_config`, `play_tone`, current setters, `disengage_axes`, the Heater-Shaker,
  Thermocycler, Temperature and Magnetic Module controllers, the embedded robot-server HTTP API, and the SiLA2
  feature layer. The card lists three entry symbols; this package binds the first,
  `unitelabs.opentrons_ot2.io.motion:OT2MotionController` (motion.py:182). The other two are module controllers and
  are separate devices.
- The upstream simulator is `OT2MotionController.build(simulate=True)`: it constructs an Opentrons `SmoothieDriver`
  with `connection=None` and needs the uninstalled Opentrons stack (opentrons 8.8.1 below Python 3.12, 9.0.0 from
  3.12; pyproject.toml:27-28); its emergency stop does not halt (tests/features/test_motion_simulation.py:16-19). The
  package fake is an in-memory, stationary stand-in (F0), not the upstream simulator and not a recording. It keeps
  the upstream's one hardware lock; its initial values are placeholders, and a full home books the homed position the
  upstream simulation test records (tests/features/test_motion_simulation.py:36-37), also a placeholder. It models no
  Smoothie alarm state.
- The clone states no licence (no LICENSE file, no licence field in pyproject.toml); the card says NOASSERTION and
  requires a publication review.
- DEVIATION FROM THE CARD: the card's helper is `PythonObjectDriver`, but the native controller's methods are
  coroutines and take axis-mapping and caller-owned pipette conversions; a direct Driver with `native.py` is used
  instead, matching the card's own `decision` value `direct-driver`.

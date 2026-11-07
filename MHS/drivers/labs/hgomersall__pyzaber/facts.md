# Facts and tags for gh.hgomersall/pyzaber

Every fact cites its source at commit `1a3f1e712f3d5bb3dab8512cdfeda9d21244b374`: `vendor_doc` (a text file of the
clone) or `upstream_code` (a path of the clone and a line). The clone has no README, docs directory or manual, so
every fact below is upstream code. The same facts are written into `driver.py` (`facts = [...]`); the reference file
is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The clone's linear units are all with respect to 1 mm: mm = 1, um = 1e-3 and inches = 25.4 | upstream_code | pyzaber/linear_slides.py:4-10 |
| multiaxis_linear_slides is the module's multiaxis linear-slide class | upstream_code | pyzaber/linear_slides.py:53 |
| The class takes a connection and a devices mapping and gives zaber_multidevice units_per_step = mm_per_rev / steps_per_rev with move_units = the units argument | upstream_code | pyzaber/linear_slides.py:73-92 |
| The clone's multiaxis example names the axes x, y and z on device numbers 1, 2 and 3 | upstream_code | pyzaber/linear_slides.py:121-125 |
| Commands are looked up by name in the base_commands and move_commands tables: home is 1, return_current_position is 60, absolute is 20 and stop is 23 | upstream_code | pyzaber/zaber_device.py:10-29 |
| The class exposes commands dynamically through __getattr__: a base command name calls enqueue_base_command, move_<name> calls move() and get_<setting> calls get() | upstream_code | pyzaber/zaber_device.py:163-196 |
| get_current_position returns each device's current position divided by its microsteps_per_unit | upstream_code | pyzaber/zaber_multidevice.py:199-210 |
| A blocking move converts each axis position to microsteps with microsteps_per_unit and calls that device's move() with blocking=True | upstream_code | pyzaber/zaber_multidevice.py:169-178 |
| emergency_stop broadcasts the stop command to every device immediately | upstream_code | pyzaber/zaber_device.py:389-405 |
| The emergency branch of do_now sends (0, command, data) through the connection without waiting for a reply | upstream_code | pyzaber/zaber_device.py:932-935 |
| A command is a (device_id, command, data) frame written through serial_connection.send_command | upstream_code | pyzaber/serial_connection.py:144-150 |
| The clone's dummy simulator implements get_current_position and move_absolute but no home or emergency_stop, so it cannot serve this driver's stop path | upstream_code | pyzaber/dummy_linear_slides.py:9-29 |

Limits: the clone states no axis travel, end stop or workspace bound. The three inputs of
`cap.motion.cartesian_pose.v1` (`position.x`, `position.y`, `position.z`) are therefore
`Limit.operator_required`: without an operator overlay every move is refused `MHS.SAFETY.LIMITS_UNSET`, and
`site-limits.example.json` shows the overlay shape. The constructor defaults `steps_per_rev=200` and `mm_per_rev=6.35`
(`pyzaber/linear_slides.py:77-78`) are mechanical configuration, not limits of the device, and are not used as one.

Units: the clone's linear units are expressed relative to 1 mm (`pyzaber/linear_slides.py:4-10`), and the class
uses the `units` argument as its move unit (`pyzaber/linear_slides.py:79, 91-92`). The driver publishes millimetres and
expects a stage configured with `units='mm'`; the hardware factory is not part of this package.

Safety: the e-stop calls the upstream `emergency_stop`, which broadcasts command 23 to device 0 immediately
(`pyzaber/zaber_device.py:389-405`, `932-935`). The clone documents no independent hardware e-stop, so the package
declares none and claims no physical protection. The device moves a three-axis gantry; the driver is R2, above the
card's R1 floor. The safe-state action `cap.motion.stop.v1` calls the same native stop and is listed in
`safe_state.achieved_by`, which is the independent stop SAFE-045 accepts for a model-written R2 package. This package
is model-authored and unreviewed (`reviewed_by` null) and ships no hardware backend; the upstream modules are Python 2
(`pyzaber/zaber_device.py:3` imports `Queue`, `pyzaber/zaber_multidevice.py:64` is a Python 2 print statement), so
they cannot be imported by the Python 3 runtime.

Tags: zaber, linear slide, gantry, multiaxis, serial, motion, positioner.

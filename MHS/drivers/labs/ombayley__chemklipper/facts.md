# Facts and tags for gh.ombayley/chemklipper

Every fact cites its source at commit `e88503106b481ad12a2469b3dbe991c18186e650`: `vendor_doc` (a text file of the
clone) or `upstream_code` (`path/in/clone.py:LINE` or `FIRST-LAST`). The same table is written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The gantry sends G-code through printer.gcode.script and reads motion state through printer.objects.query | upstream_code | src/chem_klipper/devices/gantry.py:34-36 |
| get_target_position queries gcode_move and returns its position keyed by axis_map | upstream_code | src/chem_klipper/devices/gantry.py:44-53 |
| get_current_position queries motion_report and returns live_position indexed X, Y, Z and E | upstream_code | src/chem_klipper/devices/gantry.py:55-64 |
| The gantry module sets MIN_STEPPER_CURRENT = 0.10, MAX_STEPPER_CURRENT = 1.00, DEFAULT_MOVE_TIMEOUT = 180.0, POSITION_TOLERANCE = 0.001 and DEFAULT_MOVE_SPEED = 20.0 | upstream_code | src/chem_klipper/devices/gantry.py:20-24 |
| wait_for_move polls the live position until every tracked axis is within the tolerance or the timeout expires | upstream_code | src/chem_klipper/devices/gantry.py:68-83 |
| Gantry.move sends the XY move and the Z move as separate G0 commands and waits after each | upstream_code | src/chem_klipper/devices/gantry.py:111-173 |
| home() sends G28 (or SET_KINEMATIC_POSITION X=0 Y=0 Z=0 when debug is true) and raises MotionError when the reply is not 'ok' | upstream_code | src/chem_klipper/devices/gantry.py:99-109 |
| enable_motors sends M17 and disable_motors sends M18 | upstream_code | src/chem_klipper/devices/gantry.py:175-182 |
| get_status reads printer.info and returns its 'state' value | upstream_code | src/chem_klipper/devices/moonraker_device.py:60-65 |
| is_connected is true only while the Moonraker WebSocket is open | upstream_code | src/chem_klipper/moonraker.py:84-87 |
| The gantry and deck configuration express distances in millimetres (_mm keys) with a default speed of 100 mm/s | upstream_code | config/lh_device.yaml:7-33 |
| The bring-up guide tells the operator to keep a hand near the power switch or emergency stop before any motion | vendor_doc | docs/user-guide/08-testing.md:15-18 |
| The example printer configuration wires the x_max and y_max switches to M112, an emergency stop | vendor_doc | docs/user-guide/05-klipper-config.md:172-180 |
| The guide says the example travel limits and driver currents must be reviewed against the actual machine and are a starting point, not a substitute for calibration | vendor_doc | docs/user-guide/05-klipper-config.md:230-243 |

Limits: the extension action `x-cap.ombayley.move_cartesian.v1` bounds X, Y and Z with
`Limit.operator_required`. The workspace of a Klipper machine is set by its `printer.cfg` and the deck, not by the
class; the example printer configuration in the guide is explicitly a starting point that must be checked against
the machine (`docs/user-guide/05-klipper-config.md:230-243`). `site-limits.example.json` is an example overlay, not
a statement about any unit.

Safety: the e-stop and the safe-state action `x-cap.ombayley.stop_motion.v1` both call the native `disable_motors` (`M18`,
`src/chem_klipper/devices/gantry.py:180-182`). The bring-up guide tells the operator to keep a hand near the power
switch or emergency stop (`docs/user-guide/08-testing.md:15-18`), which is the cited `estop_physical_ref`; the
M112 max-travel switches (`docs/user-guide/05-klipper-config.md:172-180`) are a second independent stop path in the
example configuration.

Not covered: liquid handling. `Pump.aspirate`, `dispense`, `refill` and `empty` are empty `pass` bodies
(`src/chem_klipper/devices/pump.py:57-67`), so the driver does not expose `cap.fluid.*` capabilities.

Tags: gantry, corexy, klipper, motion, asyncio

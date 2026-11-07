# Facts, limits and tags for gh.uw-loci/flamingo_control

The card's entry symbol `py2flamingo.controllers.position_controller:PositionController` exists in the clone at
line 33 and is the `native` class of this package. The package is a direct Driver over that controller: its methods
are called directly, so the card's `PythonObjectDriver` helper is not used (the controller keeps state, owns a
connection and has a HALT stop; a plain family description would lose that shape).

Every fact cites its source at commit `0eee5dac8e54edbb02ec0c4a18d3e362ad772310`: `upstream_code` is a code or
docstring line of the clone, `vendor_doc` a text file of it. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| A Position carries x, y and z in millimetres and r as a rotation angle in degrees | upstream_code | src/py2flamingo/models/microscope.py:48-58 |
| The position controller's axis codes are X=1, Y=2, Z=3 and R=4 | upstream_code | src/py2flamingo/controllers/position_controller.py:24-30 |
| move_x moves the X axis to a target position in millimetres | upstream_code | src/py2flamingo/controllers/position_controller.py:290-299 |
| move_y moves the Y axis to a target position in millimetres | upstream_code | src/py2flamingo/controllers/position_controller.py:361-370 |
| move_z moves the Z axis to a target position in millimetres and warns that Z movement needs careful consideration of focus and collision risks | upstream_code | src/py2flamingo/controllers/position_controller.py:432-444 |
| move_rotation moves the rotation axis to an angle in degrees | upstream_code | src/py2flamingo/controllers/position_controller.py:217-230 |
| The axis moves send the command and return immediately; motion completion is tracked asynchronously and the callback fires when motion stops | upstream_code | src/py2flamingo/controllers/position_controller.py:294-296 |
| move_to_position moves all four axes and, when validate is true, clamps an out-of-range target to the configured soft limits instead of raising | upstream_code | src/py2flamingo/controllers/position_controller.py:585-625 |
| get_stage_limits delegates to the configuration service and its per-microscope settings | upstream_code | src/py2flamingo/controllers/position_controller.py:1287-1300 |
| The configuration service documents that stage limits are loaded from the microscope-specific settings JSON so each microscope can be configured without code changes | upstream_code | src/py2flamingo/services/configuration_service.py:316-327 |
| get_current_position returns the locally tracked position; the microscope hardware does not report the current position | upstream_code | src/py2flamingo/controllers/position_controller.py:1338-1348 |
| get_home_position reads the Home x-axis, y-axis, z-axis and r-axis values from ScopeSettings.txt | upstream_code | src/py2flamingo/controllers/position_controller.py:764-787 |
| set_home_position validates the position against the stage limits and writes the four Home values back to ScopeSettings.txt | upstream_code | src/py2flamingo/controllers/position_controller.py:793-835 |
| emergency_stop sends the HALT command (0x6002) to the hardware first, then sets a flag that prevents new movements until it is cleared | upstream_code | src/py2flamingo/controllers/position_controller.py:869-910 |
| clear_emergency_stop clears the emergency-stop flag | upstream_code | src/py2flamingo/controllers/position_controller.py:920-931 |
| The clone README describes control software for Flamingo light sheet microscope systems that communicates with the microscope over TCP/IP | vendor_doc | README.md:3 |

## Limits

| parameter | unit | limit | source |
|---|---|---|---|
| position_x / position_y / position_z / rotation (reads) | mm / mm / mm / deg | none declared (reads) | - |
| home_x / home_y / home_z / home_rotation (writes and reads) | mm / mm / mm / deg | operator_required: the home coordinate must lie inside the stage's configured travel, which is loaded per microscope from settings (configuration_service.py:316-327) | operator |
| x / y / z / r of `x-cap.uw-loci.move_stage.v1` | mm / mm / mm / deg | operator_required: no text file of the clone states the travel; the limits are loaded per microscope from settings (configuration_service.py:316-327) | operator |
| `cap.motion.stop.v1` input | - | the driver declares no deceleration input; the native HALT takes no profile | - |

The `StageLimits` dataclass under `src/py2flamingo/models/microscope.py:117-124` holds constructor defaults (0 to
26 mm, -720 to 720 degrees). Those are defaults of a model class, not the limits of the connected stage: the
controller reads the real limits from the per-microscope settings file at run time (configuration_service.py:
316-327). They are therefore not used as bounds here. The operator overlay in `site-limits.example.json` is an
example for one bench, not a statement about any unit.

The driver refuses a target outside the controller's own `is_position_within_bounds` because `move_to_position`
clamps an out-of-range target silently (position_controller.py:608-625). The runtime envelope is checked first; this
second check keeps a configured stage with narrower soft limits from moving somewhere other than the requested
target.

## Safety

- The e-stop is the native `emergency_stop()`: it sends HALT (0x6002) and sets the controller's flag
  (position_controller.py:869-910). The reset hook calls `clear_emergency_stop()` after an accepted operator reset
  (position_controller.py:920-931).
- The `cap.motion.stop.v1` action sends the same HALT and then clears the controller's software latch, so a normal
  stop does not leave the controller refusing all later moves.
- No line of the clone documents an independent hardware e-stop; the HALT is a software command sent over the
  microscope connection. The package is R1, so SAFE-045 (an independent stop for R2/R3) does not apply, but no
  hardware protection is claimed.
- Hardware is never attached in the acceptance run; the package's hardware backend (`native.py`) was never imported
  or executed, and no hardware run is claimed.

## Tags

microscope, light sheet, stage, position, motion, flamingo

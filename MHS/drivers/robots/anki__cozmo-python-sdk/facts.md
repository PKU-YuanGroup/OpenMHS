# Facts and tags for gh.anki/cozmo-python-sdk

Every fact cites its source at commit `dd29edef18748fcd816550469195323842a7872e`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or
`upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The head can be set from MIN_HEAD_ANGLE (util.degrees(-25)) to MAX_HEAD_ANGLE (util.degrees(44.5)) | upstream_code | src/cozmo/robot.py:98-102 |
| SetHeadAngle clamps a head target to MIN_HEAD_ANGLE..MAX_HEAD_ANGLE and logs a warning | upstream_code | src/cozmo/robot.py:456-463 |
| The head angle is received from the robot in radians and stored as a util.Angle | upstream_code | src/cozmo/robot.py:1160 |
| set_head_angle returns a SetHeadAngle action object that can be queried to see when it is complete | upstream_code | src/cozmo/robot.py:1515-1546 |
| set_lift_height takes a ratio from 0.0 (bottom) to 1.0 (top) and clamps it to that range | upstream_code | src/cozmo/robot.py:494-501 |
| SetLiftHeight converts the ratio to millimetres between MIN_LIFT_HEIGHT_MM and MAX_LIFT_HEIGHT_MM | upstream_code | src/cozmo/robot.py:501 |
| The lift height is reported in millimetres and the lift ratio from 0.0 to 1.0 | upstream_code | src/cozmo/robot.py:1033-1044 |
| stop_all_motors tells the robot to stop all motors | upstream_code | src/cozmo/robot.py:1371-1374 |
| An action can be polled with is_completed and awaited with wait_for_completed(timeout) | upstream_code | src/cozmo/action.py:337-345 |

Limits: the head joint is bounded by `MIN_HEAD_ANGLE`/`MAX_HEAD_ANGLE` (robot.py:99, 102). The SDK writes those
bounds as `util.degrees(-25)` and `util.degrees(44.5)`; the `Limit` holds the radian values, so gate G4 reports
`REF_VALUE` for them (it evaluates `math.radians(...)` expressions but not `util.degrees(...)`). The lift ratio is
bounded by the 0.0 to 1.0 the method documents and its action clamps to (robot.py:494-501).

Safety: the e-stop is the native `stop_all_motors` (robot.py:1371-1374), which tells the robot to stop every
motor; the same call is the `cap.motion.stop.v1` action. No line of the clone documents an independent hardware
e-stop, and this is an R1 driver, so `estop_physical_ref` is not set and no safe-state action is declared.

Scope: the clone is the Cozmo Python SDK; the card lists five entry symbols. This package implements only the
first one, `cozmo.robot:Robot`. The others (`cozmo.camera:Camera`, `cozmo.world:World`,
`cozmo.nav_memory_map:NavMemoryMapGrid`, `cozmo.annotate:ImageAnnotator`) are not covered. The robot's wheels
are not driven either: the package moves the head joint and the lift and reads five states.

Tags: robot, cozmo, anki, head, lift, mobile robot

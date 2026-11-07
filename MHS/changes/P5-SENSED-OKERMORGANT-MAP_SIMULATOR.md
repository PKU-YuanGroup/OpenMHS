# P5 sensed confirmation for okermorgant/map_simulator

Repair of `MHS/drivers/robots/okermorgant__map_simulator` only. The package keeps its
`authored_by` (`deepseek-v4.1-flash:1017`, run `ros-wave-c-091`). `reviewed_by` stays
null. Written by Grok (grok-4.7, a model and not a human) on 2026-11-05.
No hardware, ROS graph, map_simulator process, rosbridge connection or human review
is claimed. The evidence is `contract_checked` on the ROS-free fake.

## Why

The package was blocked on `HELPER_MISSING`. The pinned simulator registers no stop,
pause or removal service. User decision 2 allows a request plus sensed confirmation
for simulators only. This unit of p5-sensed assigns `okermorgant/map_simulator`.
SAFE-049 and CORE-088 are the stop. The Sonnet verifier's safer predicate is the one
implemented: pose x and y, orientation z and w, and the twist axes the callback stores.

## What changed

- `safety_bindings` is `sensed_stop` only. There is no `estop` binding, no `safe_state`
  binding, no safe-state action, no reset binding and no unpause.
- The request publishes one all-zero `geometry_msgs/Twist` on `/robot1/cmd_vel`
  (`src/robot.cpp:219-226`). The publication is transmission only. The callback copies
  `linear.x`, `linear.y` and `angular.z` into `odom.twist.twist` (`src/robot.cpp:223-225`).
  Repeating the zero Twist writes zero again.
- Confirmation reads `/robot1/odom`. Three fresh samples must span at least 100 ms
  within 1500 ms. `max_gap_ms` is 500. `estop_latency_ms` is 3500, which is
  `RosDriver.timeout_s` (2.0 s) plus `confirm_within_ms` (1500).
- Pose terms are operator `span_max` on `pose.pose.position.x`, `position.y`,
  `orientation.z` and `orientation.w`. The fill ref is `Pose2D::writeTo`
  (`include/map_simulator/robot.h:62-67`). `src/robot.cpp:80` reads that pose into a
  transform and is not the fill ref. `Robot::move` writes the pose with
  `rel_pose.writeTo(odom.pose.pose)` (`src/robot.cpp:313-315`).
- Twist terms are operator `abs_max` on `twist.twist.linear.x`, `linear.y` and
  `angular.z` (`src/robot.cpp:223-225`). `withNoise` returns
  `val * (1 + std * unit_noise(random_engine))` (`src/robot.cpp:54-58`), so a zero
  command stays zero. Pose span alone would miss `linear.y` or a pure yaw command.
- Every term uses unit `1`. The clone states no metre. Thresholds are
  `Limit.operator_required`. Placeholders for the fake are in
  `fixtures/estop-confirmation.json` and are not facts.
- History is `{"durability": "volatile", "ref": "src/robot.cpp:214"}`. That line is
  `create_publisher<nav_msgs::msg::Odometry>(robot_namespace + "odom", 10)`, closed on
  the line, with the literal depth 10 and no transient_local. The line does not say
  volatile. The fixture has no history key.
- `Robot::publish` assigns `odom.header.stamp` from `now` (`src/robot.cpp:74`).
- Device risk and `publish_twist` are R2 because `cmd_vel` is a topic a physical
  mobile robot also consumes (REVIEW.md item 12). `device_kind` stays `world.sim`.
  Spawn stays R1. No `estop_physical_ref`.
- An empty `robot_namespace` is refused by pattern `.+` before `/simulator/spawn`.
  `addRobot` reads `robot_namespace.back()` with no empty check
  (`src/simulator.cpp:55-57`). The spawn conformance fixture supplies `/robot1`.
- Duplicate spawn still calls `resetTo` (`src/simulator.cpp:53-65`,
  `include/map_simulator/robot.h:135-143`). It is an ordinary command. It teleports
  the robot and is not a stop and not a reset binding (SAFE-042).

## Fake

The fake is still a canned `RecordingRosTransport`. It does not run map_simulator.
An `/robot1/odom` subscription returns eight stamped samples. The first is the stored
twist, which the confirmation discards. Later samples snap to the last `cmd_vel`.
A non-zero command steps the stored pose by a placeholder `dt` of 0.1 so the gate can
see an effect, and does not replace the stored twist, so two reads with no new command
agree. A zero command, with the fail-closed switches clear, stores a still pose and a
zero twist. `silent_odom`, `frozen_stamps`, `null_pose` and `competing_publisher`
withhold confirmation (`sensed_missing`, `sensed_stale`, `sensed_invalid`,
`not_confirmed`). A reset while `competing_publisher` is set is `RESET_REFUSED`.

## Disclosures

The stop covers `/robot1` only, and only inside the confirmation window.
`slider_publisher` (`example/turtlebot3/turtlebot3_world_launch.py:8-36`,
`example/multirobot/multi_launch.py:21-46`) and `kinematics.py` when `pub_cmd` is true
(`src/kinematics.py:101-103`, `121-122`) are other `cmd_vel` publishers. If one keeps
publishing, confirmation fails closed. Removing a robot is a GUI double click
(`src/simulator.cpp:28-36`). `/robot1/odom` exists only after `robot_description`
(`src/robot.cpp:113-126`); until then the confirmation fails closed. The client bounds
are not source facts. A live deployment sets them in
`simulation_deployment["estop_confirmation"]`.

## Stopped attempts

`development/p5-sensed/project` and `development/ext-p5-sensed.fast-stopped/project`
were compared with this package before the edit. Neither differed. Nothing was taken
from them.

## Tests

`python3 -m unittest MHS/drivers/robots/okermorgant__map_simulator/test_driver.py`
passed (19 tests), including `check_driver` on the fake. A separate
`python3 -m mhs.driver check ... --backend fake` passed with stable digest
`sha256:3dda71cc11eeb850618b55116426ae323d83c3f329e93890fffa5760583f16a0`.
The digest before this repair, from the previous RESULT.json, was
`sha256:5c60596621b06460b0e08e1e770041bb59c6005cec6ca17a4afbb3ad51d36595`.
No SDK file changed, so there is no SDK mutant. The package tests cover confirmation,
reset, a competing publisher, silence, a repeated stamp, a null pose, the empty
namespace, and the existing spawn, twist, odom and scan cases.

RESULT.json notes were already 7993 characters. The author's text before the first
`MODEL REVIEW` paragraph was shortened at a paragraph boundary, ending with ` [...]`.
The earlier claude-opus-5-5 review paragraph was not edited. The new notes are 7917
characters.

## Open questions

- A live stream at the default `rate` of 20 (`src/simulator.cpp:17`) may need the
  operator to set `min_span_ms` from the stamps it actually sees. These client bounds
  can only withhold confirmation.
- The stop does not watch `/robot1` after the window, and it does not stop any other
  robot.
- `slider_publisher` and `kinematics.py` are not started by this package. A deployment
  that runs them in `/robot1` fails closed.
- The history line is this robot's odom `create_publisher`. The gate checks that the
  line shows a publisher and no transient_local. Reading that it is this topic is the
  reviewer's job; `show_refs.py` prints the line.
- The empty-namespace guard is the pattern `.+`. It refuses `""`. It does not invent
  a numeric limit.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/robots/okermorgant__map_simulator/RESULT.json`
- `MHS/drivers/robots/okermorgant__map_simulator/driver.py`
- `MHS/drivers/robots/okermorgant__map_simulator/facts.md`
- `MHS/drivers/robots/okermorgant__map_simulator/fake.py`
- `MHS/drivers/robots/okermorgant__map_simulator/fixtures/conformance.json`
- `MHS/drivers/robots/okermorgant__map_simulator/test_driver.py`
- `MHS/drivers/robots/okermorgant__map_simulator/fixtures/estop-confirmation.json`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.

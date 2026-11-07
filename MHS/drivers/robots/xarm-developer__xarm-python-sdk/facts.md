# Facts and tags for gh.xarm-developer/xarm-python-sdk

Every fact cites its source at commit `d911319cebc45142613e18086aabb8067b18ab7f`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The README warns to keep away from the robot arm to avoid personal injury or equipment damage and to make a safety assessment before moving to prevent collisions | vendor_doc | README.md:8-11 |
| Robot type XARM7_X4 has the number 7 | upstream_code | xarm/core/config/x_config.py:41 |
| The SDK parses the axis count, the robot type and the firmware version out of the controller's version string (axis, device_type, version_number) | upstream_code | xarm/x3/base.py:473-485 |
| The SDK picks the joint range table of an arm by its axis count and robot type, and the table numbered <axis>1305 (71305 for 7 axes) when characters 3 to 6 of the serial number are from 1305 to below 8500 | upstream_code | xarm/x3/xarm.py:71-72 |
| The 1305 table of the 7-axis type XARM7_X4 narrows joint 2 to -2.042035..2.024581 rad and joint 4 to -0.10472..3.92699 rad | upstream_code | xarm/core/config/x_config.py:138-146 |
| The SDK's own joint range check is on by default (check_joint_limit) and covers set_servo_angle and set_servo_angle_j | upstream_code | xarm/wrapper/xarm_api.py:77-78 |
| The SDK's own TCP range check is off by default (check_tcp_limit) and documented to check only roll, pitch and yaw, so the position ranges of TCP_LIMITS are not checked by it | upstream_code | xarm/wrapper/xarm_api.py:75-76 |
| Every API call returns a code: 0 is success, a negative code is an SDK-side failure and a positive code comes from the controller or the protocol | upstream_code | doc/api/xarm_api_code.md:15-58 |
| The controller reports error 1 when its Emergency Stop Button is pushed, 2 when the Emergency IO of the Control Box is triggered and 3 when the Emergency Stop Button of the Three-state Switch is pressed | upstream_code | doc/api/xarm_api_code.md:68-70 |
| emergency_stop() sets state 4 (stop) and repeats it every 0.1 s for up to 3 s until the controller reports state 4 | upstream_code | xarm/x3/xarm.py:1109-1118 |
| The wrapper documents emergency_stop as set_state(4), motion_enable(True), set_state(0) and says it does not clear an error | upstream_code | xarm/wrapper/xarm_api.py:1897-1899 |
| set_state selects the motion state (0), pause (3), stop (4) or deceleration stop (6) | upstream_code | xarm/wrapper/xarm_api.py:1530-1534 |
| clean_error is documented to need motion enabled (motion_enable(True)) and state 0 set (set_state(state=0)) by hand after it | upstream_code | xarm/wrapper/xarm_api.py:1588-1595 |
| clean_warn cleans the warnings and returns an API code | upstream_code | xarm/wrapper/xarm_api.py:1597-1604 |
| motion_enable takes enable True or False and a servo_id of 1 to the number of axes, or None | upstream_code | xarm/wrapper/xarm_api.py:1606-1615 |
| The upstream xArm 7 move example enables motion, then sets mode 0 and state 0, before it moves | upstream_code | example/wrapper/xarm7/2001-move_joint.py:44-46 |
| Joint velocity control needs joint velocity control mode (set_mode(4)) and, in the upstream example, set_state(0) after it | upstream_code | example/wrapper/common/2000-joint_velocity_control.py:50-53 |
| Watchdog of a velocity command: over its duration (seconds) the arm sets the speed to 0 by itself (firmware 1.8.0 or newer); a duration of 0 or less never stops it | upstream_code | xarm/wrapper/xarm_api.py:3298-3302 |
| An arm with firmware older than 1.8.0 is sent -1 instead of the duration, and -1 is equivalent to 0, which never stops | upstream_code | xarm/x3/xarm.py:1704 |
| The SDK's speed ranges for position moves are 0.1 to 1000 mm/s for the tool and 0.0001 to 4.0 rad/s for the joints | upstream_code | xarm/x3/base.py:105-111 |
| A move that names no speed runs at the last used speed: 100 mm/s (tool) and 20 deg/s (joints) after start | upstream_code | xarm/x3/base.py:128-131 |

Limits (each `Limit` in `driver.py` cites its lines; the bounds are those of the 7-axis robot type XARM7_X4):

| capability | path | bound | source | ref |
|---|---|---|---|---|
| cap.motion.joint_position.v1 | joint_positions (per joint, rad) | min [-2pi, -2.059488, -2pi, -0.191986, -2pi, -1.692969, -2pi], max [2pi, 2.094395, 2pi, 3.92699, 2pi, pi, 2pi] | upstream_code | xarm/core/config/x_config.py:129-137 |
| cap.motion.cartesian_pose.v1 | position.x (mm) | -750 .. 750 | upstream_code | xarm/core/config/x_config.py:229 |
| cap.motion.cartesian_pose.v1 | position.y (mm) | -750 .. 750 | upstream_code | xarm/core/config/x_config.py:230 |
| cap.motion.cartesian_pose.v1 | position.z (mm) | -400 .. 1000 | upstream_code | xarm/core/config/x_config.py:231 |
| cap.motion.cartesian_pose.v1 | orientation.roll, .pitch, .yaw (rad) | operator_required: the SDK table states only the full circle (x_config.py:232-234) | | |
| cap.motion.joint_velocity.v1 | joint_velocities (rad/s) | operator_required: the SDK states no range for velocity mode | | |
| cap.motion.joint_velocity.v1 | duration_s (s) | operator_required: the SDK states no maximum for the duration | | |

Safety: the native stop is `emergency_stop` (state 4). The documented physical stop is the controller's Emergency Stop
Button, the Control Box's emergency IO and the Three-state Switch (`estop_physical_ref`, doc/api/xarm_api_code.md:68-70),
which satisfies SAFE-045 for this R2 hardware driver; no safe-state action is declared. `watchdog_ms` is 60000, the longest
`duration_s` of the catalogue class `cap.motion.joint_velocity.v1`; the arm itself ends a velocity command after its
`duration` (firmware 1.8.0 or newer).

A safety reset only releases the latch (SAFE-042): the driver has no `@reset` hook, so the reset sends the arm
nothing and the arm stays in stop state 4 with its error. The declared re-enable `x-cap.xarm-developer.enable_motion.v1`
(`reenable=True`, CORE-086) runs the recovery the SDK documents: `clean_error` and `clean_warn`
(xarm_api.py:1588-1604), then `motion_enable(True)`, `set_mode(0)` and `set_state(0)`, which `clean_error` says must
follow it by hand (xarm_api.py:1590) and which the upstream examples start with
(example/wrapper/xarm7/2001-move_joint.py:44-46). The first non-zero API code stops it. The runtime refuses it while the
e-stop is latched, a reset receipt names it, and it takes no input. Until 2026-11-05 the `@reset` hook ran the whole
sequence itself, which SAFE-042 forbids; the SDK now refuses an `@reset` hook on a driver that declares a re-enable.
The driver's `setup` still runs the start sequence once, when the backend is first opened.

Tags: robot arm, 7-axis, ufactory, xarm, joint control, cartesian control, velocity control

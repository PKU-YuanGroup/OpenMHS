# Facts and tags for gh.maskor/webots_ros2_spot

Every fact cites the pinned clone at commit `1245900385c5f0a8f7d153a047886b06010c0524`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the statement
spans adjacent lines. The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The URDF selects the webots_spot.spot_driver.SpotDriver plug-in for the Spot robot. | upstream_code | resource/spot_control.urdf:4 |
| The launch file creates a WebotsController for robot_name Spot and starts the Webots world. | upstream_code | launch/spot_launch.py:91-109 |
| The plug-in imports geometry_msgs Twist, sensor_msgs JointState, nav_msgs Odometry, std_srvs SetBool and the webots_spot_msgs SpotMotion and SpotHeight service types. | upstream_code | webots_spot/spot_driver.py:4-12 |
| The plug-in creates a geometry_msgs/Twist subscription on the absolute /cmd_vel topic. | upstream_code | webots_spot/spot_driver.py:197 |
| The plug-in publishes sensor_msgs/JointState on /joint_states. | upstream_code | webots_spot/spot_driver.py:198-200 |
| The plug-in creates a nav_msgs/Odometry publisher on /Spot/odometry with integer history depth 1. | upstream_code | webots_spot/spot_driver.py:201 |
| The plug-in registers SpotMotion services /Spot/stand_up, /Spot/sit_down and /Spot/lie_down. | upstream_code | webots_spot/spot_driver.py:204-206 |
| The plug-in registers the SpotHeight service /Spot/set_height. | upstream_code | webots_spot/spot_driver.py:210-212 |
| The /cmd_vel callback stores the message as previous_cmd_vel, clears fixed_motion and, when no /Spot/inverse_gait_input publisher exists, converts linear.x, linear.y and angular.z into persistent gait state; it returns no acknowledgement and starts no stale-command timer. | upstream_code | webots_spot/spot_driver.py:361-388 |
| The stand callback sets fixed_motion=True, checks previous_cmd against request.override, starts a one-second movement_decomposition to the stand targets and returns the answer string immediately. | upstream_code | webots_spot/spot_driver.py:638-648 |
| The lie callback sets fixed_motion=True before checking previous_cmd/override; with override=true it starts the one-second lie transition and returns 'lying down'. | upstream_code | webots_spot/spot_driver.py:662-672 |
| The set_height callback refuses request heights outside [-0.2, 0.2] and otherwise stores zd as the negated height. | upstream_code | webots_spot/spot_driver.py:756-761 |
| The step loop runs float_motion whenever float_mode is set, before it checks fixed_motion; otherwise it runs defined_motions while fixed_motion is set and spot_inverse_control when it is not. | upstream_code | webots_spot/spot_driver.py:935-948 |
| defined_motions moves each leg motor by step_difference toward the target and decrements n_steps_to_achieve_target once per call; when the count is spent it clears previous_cmd unless a paw motion is pending. | upstream_code | webots_spot/spot_driver.py:701-727 |
| The odometry publisher fills pose.pose.position, pose.pose.orientation and twist.twist from the Webots pose and finite differences. | upstream_code | webots_spot/spot_driver.py:562-593 |
| The plug-in sets the Webots robot timestep to 32. | upstream_code | webots_spot/spot_driver.py:161 |
| handle_transforms_and_odometry builds a builtin_interfaces Time from Webots getTime(), with sec and nanosec. | upstream_code | webots_spot/spot_driver.py:478-481 |
| handle_transforms_and_odometry stores previous_rotation and previous_translation when they are not yet set. | upstream_code | webots_spot/spot_driver.py:558-560 |
| The odometry message sets header.stamp and pose.pose.position.x, pose.pose.position.y and pose.pose.position.z. | upstream_code | webots_spot/spot_driver.py:575-581 |
| defined_motions calls handle_transforms_and_odometry. | upstream_code | webots_spot/spot_driver.py:701-702 |
| step calls handle_transforms_and_odometry after the float_mode, fixed_motion or inverse branch. | upstream_code | webots_spot/spot_driver.py:943-950 |
| nav_launch.py includes nav2_bringup bringup_launch.py and passes params/nav2_params.yaml. | upstream_code | launch/nav_launch.py:37-50 |
| The joint-state publisher writes the motor sensor positions (motors_pos) followed by zero positions for four unactuated piston joints. | upstream_code | webots_spot/spot_driver.py:595-613 |
| The plug-in declares NUMBER_OF_JOINTS = 12 for the actuated leg joints. | upstream_code | webots_spot/spot_driver.py:22 |
| SpotDriver.init sets float_mode to False, stores an empty Twist as previous_cmd_vel and registers the std_srvs SetBool service /Spot/float_mode. | upstream_code | webots_spot/spot_driver.py:218-220 |
| float_mode_cb assigns request.data to float_mode and returns success=True for every request. | upstream_code | webots_spot/spot_driver.py:763-767 |
| The float_motion path sets every leg motor position to zero, moves and yaws the base by previous_cmd_vel and resets the physics of the base and its children; it reads neither fixed_motion nor n_steps_to_achieve_target and does not zero previous_cmd_vel. | upstream_code | webots_spot/spot_driver.py:769-933 |
| The GaitInput callback __gait_cb sets fixed_motion to False and copies the message fields into the gait state. | upstream_code | webots_spot/spot_driver.py:403-420 |
| The blocksworld_pose callback moves the Spot node to a hardcoded translation and rotation, sets fixed_motion and starts the lie transition. | upstream_code | webots_spot/spot_driver.py:625-636 |
| get_ros2_nodes creates the SpotArm WebotsController, controller_manager spawners for the arm trajectory, joint-state broadcaster and gripper controllers, and the retract_manipulator node. | upstream_code | launch/spot_launch.py:20-88 |

## Scope

The ROS 2 surface exposed here is the plug-in's `/cmd_vel` subscription, the
`/joint_states` and `/Spot/odometry` publications, and the `SpotMotion` and `SpotHeight`
posture services.  The `/cmd_vel` publication is transmission-only: the callback has no
response path, no acknowledgement and no stale-command timer, and the persistent gait
state remains in force until another message or a posture service changes it.  The
`/Spot/inverse_gait_input` subscription is not exposed: it is a second, direct gait
input whose message definition lives in the external `webots_spot_msgs` package, and
this package covers the primary base-velocity path plus posture services.

The posture callbacks start a one-second `movement_decomposition` and return the
`answer` string immediately.  The fixed target path (`defined_motions`) decrements
`n_steps_to_achieve_target` once per Webots step, so the service answer is not
completion.  `/Spot/lie_down` with `override=true` is an ordinary posture command and the second
request step of the sensed-confirmation stop. By itself it sets `fixed_motion` and starts
the fixed lie targets; it neither measures quiescence nor stops unrelated ROS publishers
or the Webots process (see Safety).

`/Spot/float_mode` is deliberately not exposed.  Its callback only stores a flag; the
selected `float_motion` path sets motor positions to zero but still applies the last
`previous_cmd_vel` to the base translation and yaw before freezing physics, and it ignores
`fixed_motion`.  `/Spot/blocksworld_pose` is not exposed as a world reset; it teleports
the robot to one hardcoded pose and starts the lie transition.  The SpotArm that
`spot_launch.py` also starts (ros2_control arm and gripper trajectory controllers) is
outside this package.

The `set_height` input uses the source-stated `[-0.2, 0.2]` check at
`webots_spot/spot_driver.py:757`.  The three `/cmd_vel` components have no source-stated
numeric range, so their limits are `operator_required`; `site-limits.example.json` is an
operational example only and must be replaced with the deployment's envelope.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS-free recording fake (no
Webots physics)`, level F0, determinism `none`, `timestep_ms: 0` (event-driven canned
replies with no physics step), `realtime_factor: 0` (not paced), reset `none`, and no
snapshot/restore.  The fake returns placeholder joint and odometry samples, records
`/cmd_vel` publications and echoes the received components into its placeholder odometry
twist. A sensed subscribe of `/Spot/odometry` gets a placeholder burst. When
`throttle_rate` is set, copies that share an arrival time collapse in a queue of
length 1, and a copy that arrives after the first was published is forwarded; the
equal stamp then fails closed. With the throttle ignored, both copies are delivered
and the stop stays stale. This is test data, not measured motion, and
the fake does not step the robot or run rosbridge. The one-second posture transitions,
Webots physics, contacts, sensors, namespacing and QoS are not simulated. No captured
traffic is replayed; the fake is an analytic stand-in.

## Safety

The device is simulated and carries R2 because it is a mobile base. The e-stop is a
sensed-confirmation stop (SAFE-049), not an acknowledged binding and not a safe-state
action. It calls `/Spot/float_mode` with `data` false
(`webots_spot/spot_driver.py:763-767`) and then `/Spot/lie_down` with `override` true
(`webots_spot/spot_driver.py:662-672`). The stop is achieved only when `/Spot/odometry`
shows the base still in x, y and orientation and inside the operator's lying height
band for three consecutive fresh samples. The quaternion span is the rotation check.
The second publish in one step can carry a zero finite-difference twist, because
`previous_rotation` is stored before that publish (`webots_spot/spot_driver.py:571-573`),
so twist is not the check. The SetBool `success` flag and the `lying down` answer are
not that stop.

While `fixed_motion` is set, `defined_motions` calls `handle_transforms_and_odometry`
(`webots_spot/spot_driver.py:702`) and `step` calls it again
(`webots_spot/spot_driver.py:950`). There is no `robot.step` between those calls.
The first call after start stores `previous_rotation` and `previous_translation` and
does not publish odometry (`webots_spot/spot_driver.py:558-560`); it still publishes
`/joint_states` (`webots_spot/spot_driver.py:613`). Once `previous_rotation` exists,
both calls publish `/Spot/odometry` and assign `header.stamp` from `getTime()`
(`webots_spot/spot_driver.py:478-481`, assigned at 577). This package reads that pair
as one stamp. The clone has no line that says `getTime()` stays fixed inside one
controller step. `throttle_ms` 100 is sent as rosbridge `throttle_rate` with
`queue_length` 1. That queue overwrites a copy that is still waiting. A copy that
arrives after the first was forwarded is delivered when the throttle elapses, with
the same stamp, and the sensed window then fails closed. The fake models that
timing. It does not run rosbridge.

`/Spot/float_mode` true still applies the stored `previous_cmd_vel` and ignores
`fixed_motion` (`webots_spot/spot_driver.py:769-781`, `943-944`). Any `/cmd_vel` or
gait input clears `fixed_motion` (`webots_spot/spot_driver.py:361-363`, `403-404`).
The stop does not clear `previous_cmd_vel` and does not re-enable anything. Reset
re-confirms the sensed state and sends no request. `nav_launch.py` includes
nav2_bringup (`launch/nav_launch.py:37-50`). Any publisher of `/cmd_vel` competes,
including a navigation stack started by that launch if it writes `/cmd_vel`. This
clone's `params/nav2_params.yaml` has no `cmd_vel` string, so this page does not state
that nav2 publishes `/cmd_vel`. SpotArm (`launch/spot_launch.py:20-88`) is not
stopped. Webots is not paused. The lying band and the at-rest bounds are
`operator_required`; `fixtures/estop-confirmation.json` is fake-only. Its quaternion
spans (`still_qx`, `still_qy`, `still_qz`, `still_qw`, each 0.05) are placeholders,
not a yaw tolerance. `min_span_ms` 200 matches the fake's 100 ms producer ticks.
A 32 ms producer (`webots_spot/spot_driver.py:161`) puts three one-step samples 64 ms
apart and needs a lower `min_span_ms` in `simulation_deployment['estop_confirmation']`.
A live step slower than `max_gap_ms`, or a one-second lie that outlasts
`confirm_within_ms`, fails closed until the operator raises those two bounds.
`throttle_ms` stays on the declaration. No hardware stop is claimed.
`driver.lock.json` keeps `reviewed_by` null.

## Tags

`ros`, `ros2`, `webots`, `simulation`, `spot`, `quadruped`, `mobile-base`, `cmd-vel`

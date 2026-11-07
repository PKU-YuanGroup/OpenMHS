# Facts and tags for gh.harunteper/auna

Every fact cites the pinned clone at commit `1d8bb13d574deca84c42e0bc9a0ff04d470d371f`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The control configuration declares four multiplexer inputs (wallfollowing AckermannDriveStamped on cmd_vel/wallfollowing, teleop TwistStamped on cmd_vel/teleop, cacc Twist on cmd_vel/cacc, nav2 Twist on cmd_vel/nav2) and three outputs (cmd_vel_twist Twist, cmd_vel_twist_stamped TwistStamped, cmd_vel_ackermann AckermannDriveStamped). | upstream_code | auna_common/config/control/topics.yaml:1-24 |
| The multiplexer node starts with current_source_ set to OFF unless initial_source names a configured source, and initializes estop_active_ to false. | upstream_code | packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:91-118 |
| The constructor registers the relative toggle_cmd_vel_source (auna_msgs/SetString), get_source_status, get_input_sources and debug_state (std_srvs/Trigger) services, plus the absolute /trigger_emergency_stop (std_srvs/SetBool) and /get_estop_status (std_srvs/Trigger) services, on the multiplexer node. | upstream_code | packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:128-161 |
| toggleSourceCallback sets current_source_ to OFF for the literal OFF, accepts a configured input name, and returns success=false with a message for an unknown source. | upstream_code | packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:308-337 |
| getSourceStatusCallback sets success=true and returns 'Current source: ' followed by the stored source name. | upstream_code | packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:429-436 |
| The publish timer uses the last received message of the selected source, or createZeroAckermann when the source is OFF or has no message, and publishes it on every configured output. | upstream_code | packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:359-417 |
| The multiplexer declares publish_rate with a default of 20.0 Hz. | upstream_code | packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:62 |
| createZeroAckermann sets drive.speed and drive.steering_angle to 0.0. | upstream_code | packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:503-508 |
| twist_to_ackermann copies TwistStamped.linear.x to drive.speed and TwistStamped.angular.z to drive.steering_angle. | upstream_code | packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:511-518 |
| setupSubscribers creates a TwistStamped subscription for each configured source whose declared type is TwistStamped. | upstream_code | packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:218-228 |
| twist_callback stores twist_to_ackermann(msg) in last_received_msgs_ under the source name. | upstream_code | packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:278-293 |
| The shipped control parameters set publish_rate 20.0, wheelbase 0.32 and convert_yaw_to_steering_angle false for every cmd_vel_multiplexer_node. | upstream_code | auna_common/config/control/params.yaml:1-5 |
| The timer converts the steering angle from a yaw rate with the wheelbase only when convert_yaw_to_steering_angle is true. | upstream_code | packages/src/auna_control/src/cmd_vel_multiplexer/cmd_vel_multiplexer_node.cpp:392-401 |
| The launch reads ROBOT_INDEX (default '0') and INITIAL_SOURCE (default 'OFF') from the environment and builds the namespace robot{ROBOT_INDEX}. | upstream_code | packages/src/auna_control/launch/cmd_vel_multiplexer.launch.py:32-36 |
| The launch builds param_file from auna_common/config/control/params.yaml and topic_file from auna_common/config/control/topics.yaml, and starts the multiplexer node with that namespace, those files and initial_source. | upstream_code | packages/src/auna_control/launch/cmd_vel_multiplexer.launch.py:39-69 |
| docker-compose.yml runs cmd_multiplexer_robot1 with ROBOT_INDEX=1 and INITIAL_SOURCE=OFF. | upstream_code | docker-compose.yml:307-314 |
| docker-compose.yml's teleop service, in the teleop and manual_control profiles, runs auna_teleoperation keyboard_teleop_hold. | upstream_code | docker-compose.yml:594-609 |
| The teleop node declares publish_rate 10.0 and base_namespace robot, creates its first publisher for the namespace robot0 and calls _publish from a timer at publish_rate. | upstream_code | packages/src/auna_teleoperation/auna_teleoperation/teleop.py:38-72 |
| The teleop node publishes on /{namespace}/cmd_vel/teleop as TwistStamped or Twist. | upstream_code | packages/src/auna_teleoperation/auna_teleoperation/teleop.py:124-136 |
| The control panel creates clients for the absolute /trigger_emergency_stop and /get_estop_status and for the namespaced get_source_status, get_input_sources and toggle_cmd_vel_source services. | upstream_code | packages/src/auna_control/src/control_panel/control_panel_ros_interface.cpp:83-92 |
| The F1TENTH vesc.launch.py defines vesc_driver_node (vesc_driver), vesc_to_odom_node and ackermann_to_vesc_node (vesc_ackermann) with its namespace launch configuration. | upstream_code | packages/src/auna_f110/launch/vesc.launch.py:41-67 |
| The race-car Gazebo model loads libgazebo_ros_ackermann_drive.so, declares max_steer 0.6458 rad with the comment that a greater cmd_vel angular z is capped, and declares max_speed 10.0 m/s as the maximum absolute linear speed. | upstream_code | packages/src/auna_gazebo/models/race_car/model.urdf:395-417 |
| The race-car plugin remaps cmd_vel to cmd_vel_twist and odom to odom. | upstream_code | packages/src/auna_gazebo/models/race_car/model.urdf:435-440 |
| The shipped race_car model-parameter file records drive max_steer 0.6458 and max_speed 1.5 under robot.plugins.drive. | upstream_code | auna_common/config/model_params/race_car.yaml:7-11 |

## Scope

The driver covers one robot namespace of the `auna_control` command multiplexer. It binds the namespaced
`toggle_cmd_vel_source` service (`auna_msgs/srv/SetString`), the namespaced `get_source_status` service
(`std_srvs/srv/Trigger`) and the `cmd_vel/teleop` input (`geometry_msgs/msg/TwistStamped`). The service names
are relative in the clone (`"toggle_cmd_vel_source"`, `"get_source_status"`), so they resolve under the
launch namespace `robot{ROBOT_INDEX}`; the driver records the upstream tokens as `source_name` and configures the
resolved `/robot1` endpoints of the first robot of the shipped docker-compose services (`ROBOT_INDEX=1`,
`INITIAL_SOURCE=OFF`). Without that variable the launch file's own default is `robot0`, which needs other
endpoints. The teleop topic is also relative in `topics.yaml` and resolves under the same
namespace.

The multiplexer's timer caches the last message per source and republishes it at `publish_rate` (20.0 Hz in the
shipped parameters) while that source is selected. A single publication is therefore a continuous command
until another message replaces it or the source becomes `OFF`. The source `OFF` branch calls
`createZeroAckermann()`. The Gazebo plugin's `max_speed` (10.0 m/s) and `max_steer` (0.6458 rad) are absolute
clamps the simulator applies to commands, not a command envelope stated by the clone, and the cited lines state
no negative bound, so both teleop inputs are `Limit.operator_required`. The shipped `race_car.yaml`
model-parameter file records a tighter `max_speed: 1.5`, but no launch or node in the clone reads that file; the
example site overlay uses 1.5 m/s and 0.6458 rad as example site ranges.

The absolute `/trigger_emergency_stop` and `/get_estop_status` services are not bound. Every namespaced
multiplexer creates those same absolute names, so a call is not robot-scoped; this package uses the
namespaced source selection as the per-robot stop instead. It does not use the upstream e-stop latch at all.

## Safety

The device is simulated at R2. The input-free `x-cap.harunteper.stop.v1` action calls the namespaced
`toggle_cmd_vel_source` service with the literal `OFF` and is declared `safe_state=True`; it is also the
`estop` binding. The multiplexer timer then publishes zero speed and steering commands on its outputs. This is
a software source change, not an independent hardware emergency stop, and its acknowledgement is not sensed
quiescence. The timer's only branch before the source check is the absolute e-stop flag, which also publishes
zero, and incoming messages update only the per-source cache, so no motion input clears `OFF`. The multiplexer
retains the cached last command for each source: re-selecting a non-OFF source re-publishes that cached command
immediately, so the operator must publish the intended command before selecting the source after a stop. The MHS
latch fences effectful commands, but it cannot stop unrelated ROS clients from changing the multiplexer source:
the RViz control panel is a `toggle_cmd_vel_source` client, and the shipped keyboard teleop (docker-compose
`teleop` and `manual_control` profiles) publishes the same `cmd_vel/teleop` input at 10 Hz. The clone also ships
an F1TENTH platform launch with a VESC motor driver; nothing in the clone connects the multiplexer output to it,
but a deployment that remaps it would drive a real car through this package.

The driver assumes the shipped `convert_yaw_to_steering_angle: false` setting. With that setting the input
`twist.angular.z` is copied directly to `drive.steering_angle`; with the parameter true, the node treats
`angular.z` as a yaw rate and converts it with the wheelbase, which would change the meaning of the
`steering_angle` input and its limit.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS-free multiplexer contract stand-in (no physics)`,
level F0, determinism `none`, `timestep_ms: 0` (event-driven state transitions with no physics step),
`realtime_factor: 0` (not paced), reset `none`, and no snapshot/restore. The fake answers the declared
services and records the last teleop publication; it does not run the multiplexer timer, Gazebo, the drive
plugin, physics or a vehicle. The plugin bounds remain source facts, not claims about the fake.

## Tags

`ros`, `ros2`, `gazebo`, `simulation`, `mobile-base`, `cmd-vel`, `ackermann`

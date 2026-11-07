# Facts and tags for gh.ros-simulation/gazebo_ros_demos

Every fact cites the pinned clone at commit
`bc1f5a5bc6c2355bb4f175cab86d3c9eabeb09f1`. `vendor_doc` refs name a text file of
the clone; `upstream_code` refs name `path/in/clone:LINE` (a bounded range is
used where the statement spans adjacent lines). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver,
not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The README identifies the repository as example robots and code for interfacing Gazebo with ROS and states GPL-3.0 licensing. | vendor_doc | README.md:1-6 |
| The README's ROS Control quick start runs rrbot_control.launch and shows the position command rostopic pub /rrbot/joint2_position_controller/command std_msgs/Float64 with data -0.9; the value is an example, not a declared joint limit. | vendor_doc | README.md:22-28 |
| rrbot_control.yaml configures joint_state_controller as joint_state_controller/JointStateController with publish_rate 50. | upstream_code | rrbot_control/config/rrbot_control.yaml:3-5 |
| rrbot_control.yaml configures joint1_position_controller for joint1 and joint2_position_controller for joint2 as effort_controllers/JointPositionController with PID gains 100.0, 0.01 and 10.0. | upstream_code | rrbot_control/config/rrbot_control.yaml:7-15 |
| rrbot_control.launch loads rrbot_control.yaml and spawns joint_state_controller, joint1_position_controller and joint2_position_controller through the controller_manager spawner under the /rrbot namespace. | upstream_code | rrbot_control/launch/rrbot_control.launch:3-10 |
| rrbot_control.launch remaps /joint_states to /rrbot/joint_states for robot_state_publisher. | upstream_code | rrbot_control/launch/rrbot_control.launch:13-16 |
| The rqt publisher records /rrbot/joint1_position_controller/command with type_name std_msgs/Float64, enabled False, rate 100.0 and the data expression sin(i/100). | upstream_code | rrbot_control/launch/rrbot_rqt.perspective:63 |
| The rqt plot records /rrbot/joint1_position_controller/command/data and /rrbot/joint1_position_controller/state/error as field expressions. | upstream_code | rrbot_control/launch/rrbot_rqt.perspective:36 |
| rrbot_control/package.xml declares controller_manager, joint_state_controller, robot_state_publisher, rqt_gui and effort_controllers as runtime dependencies. | upstream_code | rrbot_control/package.xml:19-24 |
| rrbot.xacro declares joint1 as a continuous joint with axis 0 1 0 and damping 0.7. | upstream_code | rrbot_description/urdf/rrbot.xacro:55-61 |
| rrbot.xacro declares joint2 as a continuous joint with axis 0 1 0 and damping 0.7. | upstream_code | rrbot_description/urdf/rrbot.xacro:90-96 |
| rrbot.xacro declares SimpleTransmission blocks for joint1 and joint2 that use hardware_interface/EffortJointInterface. | upstream_code | rrbot_description/urdf/rrbot.xacro:199-219 |
| rrbot.gazebo loads libgazebo_ros_control.so with robotNamespace /rrbot and gazebo_ros_control/DefaultRobotHWSim. | upstream_code | rrbot_description/urdf/rrbot.gazebo:5-9 |
| rrbot_world.launch exposes a paused launch argument defaulting to false and forwards it to gazebo_ros empty_world.launch with the rrbot world. | upstream_code | rrbot_gazebo/launch/rrbot_world.launch:3-18 |
| rrbot_world.launch starts gazebo_ros spawn_model to spawn the robot_description URDF as model rrbot. | upstream_code | rrbot_gazebo/launch/rrbot_world.launch:24-26 |
| The gazebo_tutorials world plugin requires libgazebo_ros_api_plugin.so from the gazebo_ros package to be loaded. | upstream_code | gazebo_tutorials/src/simple_world_plugin.cpp:12-16 |
| The Hokuyo sensor plugin declares the topic /rrbot/laser/scan; this fact records the topic, not a message type. | upstream_code | rrbot_description/urdf/rrbot.gazebo:68-71 |
| The camera plugin declares cameraName rrbot/camera1 and imageTopicName image_raw, giving the topic /rrbot/camera1/image_raw; this fact records the topic, not a message type. | upstream_code | rrbot_description/urdf/rrbot.gazebo:99-105 |
| The RViz configuration displays /rrbot/laser/scan as a rviz/LaserScan display. | upstream_code | rrbot_description/launch/rrbot.rviz:102-119 |
| The RViz configuration displays /rrbot/camera1/image_raw as a rviz/Camera display. | upstream_code | rrbot_description/launch/rrbot.rviz:124-127 |
| rrbot_control/package.xml declares the licence BSD. | upstream_code | rrbot_control/package.xml:9 |
| rrbot_description/package.xml declares the licence BSD. | upstream_code | rrbot_description/package.xml:9 |
| rrbot_gazebo/package.xml declares the licence BSD. | upstream_code | rrbot_gazebo/package.xml:7 |
| gazebo_tutorials/package.xml declares the licence TODO. | upstream_code | gazebo_tutorials/package.xml:16 |
| rrbot_rqt.launch starts rqt_gui with the rrbot_rqt.perspective file. | upstream_code | rrbot_control/launch/rrbot_rqt.launch:4-5 |
| rrbot_world.launch leaves its include of rrbot_control.launch commented out. | upstream_code | rrbot_gazebo/launch/rrbot_world.launch:28-29 |

## Scope

The package exposes the two controller command publications that the clone
declares with an explicit message type: `std_msgs/Float64` on
`/rrbot/joint1_position_controller/command` (rqt publisher) and on
`/rrbot/joint2_position_controller/command` (README). Each is one
`std_msgs/Float64` position command to an effort-based
`effort_controllers/JointPositionController`; the controller closes its PID loop
through the EffortJointInterface transmission.

The clone names `/rrbot/joint_states`, `/rrbot/laser/scan` and
`/rrbot/camera1/image_raw`, but it does not declare their ROS message types.
The ROS helper requires an explicit type binding for every endpoint, so this
package does NOT COVER those observations rather than guessing a type. RViz
display classes (`rviz/LaserScan`, `rviz/Camera`) are not ROS message types.

Both joints are `continuous` in the URDF, and the controller YAML declares only
PID gains. No line of the clone states a joint travel bound. Each command input
therefore uses `Limit.operator_required`; the supplied
`site-limits.example.json` is an example site overlay, not a device fact. The
README's `-0.9` value is an example command, not a bound.

## Safety

The pinned clone exposes no acknowledged stop. Both control endpoints are
fire-and-forget topic publications; the clone declares no pause, stop,
controller-switch, reset or safe-state service or action. A zero-position
publication is transmission only and is not an acknowledged stop. The package
therefore declares `safety_bindings = {}` and no `safe_state=True` action. The
runtime's software latch refuses new commands after an e-stop, but it cannot
interrupt a controller that has already accepted a command or stop Gazebo; a
stock e-stop reports `MHS.SAFETY.SAFE_STATE_UNREACHED`. This package is blocked
rather than claiming a stopped state.

The `paused` argument in `rrbot_world.launch` is a launch-time option that is
forwarded to `gazebo_ros`; it is not a runtime stop endpoint and the clone does
not name the `gazebo_ros` pause/reset services.

Reviewer additions (model review of wave C): `rrbot_rqt.launch` opens `rqt_gui`
with the saved perspective, whose publisher for
`/rrbot/joint1_position_controller/command` is stored disabled at rate 100 with
the data expression `sin(i/100)` (`rrbot_rqt.perspective:63`); enabled in the
GUI it competes with this package and keeps moving joint1 while MHS is latched.
`rrbot_world.launch` leaves its `rrbot_control.launch` include commented out
(`:28-29`), so the controllers run only when an operator also starts
`rrbot_control.launch`, as the README's quick start does. Licence: the README
states GPL-3.0 (`README.md:4`), the rrbot_control, rrbot_description and
rrbot_gazebo manifests declare BSD and gazebo_tutorials declares TODO; the card
says NOASSERTION with publish_review required, so the owner decides.

## Fidelity contract

`driver.py` describes the deployed fake: engine
`analytic:ROS-free rosbridge contract stand-in (no Gazebo physics)`, level F0,
determinism `none`, `timestep_ms: 0` (event-driven advertisement/publication
recording with no physics step), `realtime_factor: 0` (not paced), reset `none`,
and no snapshot/restore. The gaps disclose the absent Gazebo, ros_control, PID,
controller_manager and ROS graph, the placeholder command records, the uncovered
joint-state/laser/camera observations, the absent stop and the operator-required
joint envelopes.

## Tags

`ros`, `ros1`, `gazebo`, `simulation`, `rrbot`, `robot-arm`, `joint-position`,
`demo`

# Facts and tags for gh.erdalpekel/panda_simulation

Facts about the package's own surface cite the pinned clone at commit `70b6a9d7a426a9cc4dd3e41b2a61f817f1531f4b` (`path/in/clone:LINE`). Facts about the stop cite the reviewed companion sources that `task.json` declares (user decision of 2026-11-05; the user's authorisation of 2026-11-05 for the clones fetched under `work/companions`, listed in its `LOCK.json`), written `companion:<alias>/<path>:<LINE>`: `gazebo_ros_pkgs` (gh.ros-simulation/gazebo_ros_pkgs, fetched under work/companions as `ros-simulation__gazebo_ros_pkgs@2.8.7` at `0667c5e52e8afa1f478955d8a2569b473a5acdf1`) and `gazebo_classic` (gh.gazebosim/gazebo-classic, fetched under work/companions as `gazebosim__gazebo-classic@gazebo9_9.19.0` at `e4400ae7e04e4859eec392ac67b813402703bab0`). The version evidence that ties this package's stack to those pins is in `task.json` `companions[].version_evidence`; gate G1 re-checks it, and for a fetched companion also its LOCK.json entry, untracked files and write bits. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| simulation.launch includes gazebo_ros/empty_world.launch, spawns the model named panda from the robot_description parameter, and spawns joint_state_controller and panda_arm_controller. | upstream_code | panda_simulation/launch/simulation.launch:14-31 |
| simulation.launch starts rosbridge_websocket with argument port 9090. | upstream_code | panda_simulation/launch/simulation.launch:59-62 |
| panda_control.yaml configures joint_state_controller with publish_rate 100 and panda_arm_controller as a position_controllers/JointTrajectoryController for panda_joint1 through panda_joint7. | upstream_code | panda_simulation/config/panda_control.yaml:1-20 |
| panda_control.yaml configures joint_position_controller as panda_simulation/JointPositionController with joint_names panda_joint1 through panda_joint7 and seven gains of 1. | upstream_code | panda_simulation/config/panda_control.yaml:29-42 |
| simulation.launch loads joint_position_controller stopped and starts robot_state_initializer_node. | upstream_code | panda_simulation/launch/simulation.launch:53-57 |
| JointPositionController subscribes to the relative name command with std_msgs/Float64MultiArray. | upstream_code | panda_simulation/src/joint_position_controller.cpp:32-33 |
| JointPositionController::setCommandCallback assigns msg->data to command_. | upstream_code | panda_simulation/src/joint_position_controller.cpp:47 |
| JointPositionController::init fills command_ with each joint's position at load time. | upstream_code | panda_simulation/src/joint_position_controller.cpp:28-30 |
| JointPositionController::update writes (command_[i] - position) * gains_vec_[i] as each joint handle's command. | upstream_code | panda_simulation/src/joint_position_controller.cpp:38-45 |
| JointPositionController::starting and ::stopping have empty bodies. | upstream_code | panda_simulation/src/joint_position_controller.cpp:49-51 |
| robot_state_initializer names the absolute topic /joint_position_controller/command and advertises it as std_msgs/Float64MultiArray. | upstream_code | panda_simulation/src/robot_state_initializer.cpp:12-17 |
| robot_state_initializer switches the trajectory controllers out, publishes panda_ready_state on the joint-position command topic, sleeps 1 second, then restores the trajectory controllers. | upstream_code | panda_simulation/src/robot_state_initializer.cpp:22-71 |
| The stop callback calls move_group_arm->stop(), logs a message and returns true without checking any result. | upstream_code | panda_simulation/src/robot_control_node.cpp:56-61 |
| robot_control_node advertises constants::service_endpoints::ROBOT_STOP through ros::ServiceServer. | upstream_code | panda_simulation/src/robot_control_node.cpp:133 |
| The clone defines service_endpoints::ROBOT_STOP as the absolute name /robot_control_stop. | upstream_code | panda_utils/include/panda_utils/constants.h:125-127 |
| RobotStopMsg.srv declares no request fields and no response fields. | upstream_code | panda_msgs/srv/RobotStopMsg.srv:1 |
| The clone defines PLANNING_GROUP_ARM as panda_arm. | upstream_code | panda_utils/include/panda_utils/constants.h:114 |
| robot_control_node constructs MoveGroupInterface for PLANNING_GROUP_ARM. | upstream_code | panda_simulation/src/robot_control_node.cpp:73 |
| CollisionDetector subscribes to the absolute /joint_states topic with queue size 1. | upstream_code | panda_safety/src/CollisionDetector.cpp:293 |
| CollisionDetector.h includes sensor_msgs/JointState.h. | upstream_code | panda_safety/include/panda_safety/CollisionDetector.h:23 |
| CollisionDetector comments that /joint_states publishes the fingers at positions 0 and 1 and sets index_link_start to 2 for the arm joints. | upstream_code | panda_safety/src/CollisionDetector.cpp:40-41 |
| CollisionDetector's joint-state callback stores the complete sensor_msgs/JointState including its position array. | upstream_code | panda_safety/src/CollisionDetector.cpp:557-569 |
| CollisionDetector skips the first two position entries when it feeds the Panda arm joint group. | upstream_code | panda_safety/src/CollisionDetector.cpp:522-527 |
| robot_state_initializer uses the /controller_manager/switch_controller service of type controller_manager_msgs/SwitchController. | upstream_code | panda_simulation/src/robot_state_initializer.cpp:1-17 |
| simulation.launch relays joint_states to joint_states_desired with topic_tools/relay. | upstream_code | panda_simulation/launch/simulation.launch:48 |
| robot_control_node waits for a planning_scene subscriber and only advertises the stop service inside the home-directory branch after building the planning scene. | upstream_code | panda_simulation/src/robot_control_node.cpp:75-133 |
| When ~/.panda_simulation does not exist, robot_control_node creates ~/.panda_core instead and then iterates the ~/.panda_simulation directory. | upstream_code | panda_simulation/src/robot_control_node.cpp:82-108 |
| CollisionDetector calls /robot_control_stop when it counts collisions for the currently executed trajectory. | upstream_code | panda_safety/src/CollisionDetector.cpp:485-493 |
| simulation.launch includes gazebo_ros's empty_world.launch with its gui, paused and use_sim_time arguments. | upstream_code | panda_simulation/launch/simulation.launch:15-21 |
| The gazebo_ros gzserver wrapper adds libgazebo_ros_api_plugin to the server's plugins unless the arguments already name it. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/scripts/gzserver:20-24 |
| empty_world.launch starts the Gazebo server as the node named gazebo of package gazebo_ros, with the physics engine argument -e $(arg physics). | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:46-48 |
| empty_world.launch defaults its physics argument to ode. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:15 |
| empty_world.launch defaults its gui argument to true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:8 |
| When gui is true, empty_world.launch starts the node gazebo_gui of type gzclient. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:51-54 |
| The API plugin calls ros::init with the node name gazebo when ROS is not initialised yet. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:127-128 |
| The API plugin creates its node handle in the private namespace ~ and advertises its topics and services there. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:147 |
| The API plugin advertises the service pause_physics with the std_srvs::Empty type on its own callback queue gazebo_queue_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:462-468 |
| The API plugin advertises the service get_physics_properties with the gazebo_msgs::GetPhysicsProperties type on gazebo_queue_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:364-370 |
| gazeboQueueThread serves gazebo_queue_ in a loop with a 0.001 s wall-clock wait while the node handle is ok. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:235-242 |
| pausePhysics calls world_->SetPaused(true) and returns true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1662-1666 |
| unpausePhysics calls world_->SetPaused(false) and returns true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1668-1672 |
| getPhysicsProperties sets res.pause to world_->IsPaused(). | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1426 |
| getPhysicsProperties sets success true only when the physics engine type is ode; for any other engine it sets success false and returns false. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1433-1465 |
| The GetPhysicsProperties response field pause is true if the physics engine is paused. | upstream_code | companion:gazebo_ros_pkgs/gazebo_msgs/srv/GetPhysicsProperties.srv:4 |
| Among the world-update begin hooks that its comment says apply forces and publish sim time on /clock, the API plugin connects publishSimTime. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:224-227 |
| gazebo_ros_control connects its Update to the world-update begin event. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros_control/src/gazebo_ros_control_plugin.cpp:196-199 |
| gazebo_ros_control's Update reads the simulation time, updates the controllers and writes their commands to the simulated joints. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros_control/src/gazebo_ros_control_plugin.cpp:211-257 |
| World::Step advances simulation time and calls Update only when the world is not paused, a step increment is pending or a reset is due; otherwise it adds the step to the pause time. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:691-710 |
| World::Step holds worldUpdateMutex while it steps the world. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:683 |
| World::SetPaused stores the paused flag under worldUpdateMutex. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1428-1436 |
| World::IsPaused returns the stored paused flag. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1422-1425 |
| World::Update fires the worldUpdateBegin event and then updates every model. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:776-782 |
| World::Step calls ProcessMessages after the paused or unpaused branch, so pending messages are processed on every step, paused or not. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:691-718 |
| A WorldControl message with step calls OnStep, and one with multi_step pauses the world and sets the number of steps to run while paused. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1462-1477 |

## Scope

The package exposes the absolute `/joint_states` read capability, the custom controller's absolute
`/joint_position_controller/command` publication, and the absolute `/robot_control_stop` service as an ordinary
request (not a stop; see Safety).
The launch starts rosbridge on port 9090, but the deployment decides the WebSocket host and namespace; those are
operator configuration, not upstream facts.

The normal `panda_arm_controller` follow_joint_trajectory action is not declared. The clone writes the external
controller type in `panda_control.yaml` and the goal/result topic suffixes in `panda_simulation.yaml`, but the
action root endpoint appears nowhere in the pinned text; declaring it would guess an endpoint. The custom
position controller is the directly cited joint command. The launch loads it stopped and
`robot_state_initializer_node` switches it in only for the ready-state move, so a deployment must activate
`joint_position_controller` (for example through `/controller_manager/switch_controller`) before a publication
reaches it.

`/joint_states` carries the two finger joints before the seven arm joints according to the collision detector's
comment. The joint-state read returns the complete `position` array; it is not reordered or sliced by the driver.
The joint-position command takes exactly seven arm joint values in `panda_joint1`..`panda_joint7` order, matching
the controller's `joint_names`.

## Limits

No joint travel bound is stated in this clone. The Panda joint limits belong to the external
`franka_description` and `panda_moveit_config` repositories named by the launch, so the command input uses
`Limit.operator_required`. Every call carrying `joint_positions` is refused with
`MHS.SAFETY.LIMITS_UNSET` until an operator installs a reviewed `site-limits.json`. The controller gains, the
ready-state constants and the 100 Hz publication rates are configuration values, not motion bounds, and are not
used as limits.

## Safety

The device is simulated at R2 because the scope commands a robot arm. The clone's `/robot_control_stop` callback calls
`move_group_arm->stop()` for the `panda_arm` MoveIt group and returns true without checking any result
(`panda_simulation/src/robot_control_node.cpp:56-61`), and it does not reach the custom `joint_position_controller`
that the joint-position command drives, which stores the data as `command_` and, while running, writes
`(command_ - position) * gain` to each joint on every update (`panda_simulation/src/joint_position_controller.cpp:38-47`).
It is therefore not the stop (model review 2026-11-05; the author had bound it) and stays an ordinary request
(refused while the latch is held). The service is advertised only after the node has a `/planning_scene` subscriber
and enters the home-directory branch; when `~/.panda_simulation` does not exist the node creates `~/.panda_core`
instead and then iterates the missing directory (`panda_simulation/src/robot_control_node.cpp:82-108`). The
extension request is used instead of `cap.motion.stop.v1` because that class accepts a deceleration profile and
reports a stopping position, while the pinned `RobotStopMsg` service declares no request or response fields.

The e-stop is the Gazebo world pause of the simulator's own repository, a reviewed companion fetched at a pinned
commit: `/gazebo/pause_physics` (gazebo_ros 2.8.7, ROS 1 Melodic; `pausePhysics` calls `World::SetPaused(true)`), confirmed only by
the read-back `/gazebo/get_physics_properties` with `pause == true` (`res.pause = world_->IsPaused()`). A pause that
is not answered, a read-back that fails (a physics engine other than ODE) or `pause` false (another client unpaused
the world) is `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held and a background retry. `World::Step` of Gazebo
9.19.0 advances simulation time and runs the world update only while the world is not paused, a step increment is
pending or a reset is due, so a paused world runs no plugin, controller or sensor update. It is the paused flag, not
a measured standstill: the Gazebo GUI that `empty_world.launch` opens by default, a WorldControl step or multi_step,
or any ROS client can advance or unpause the world, and MHS does not watch the flag after the e-stop. While paused,
the topics published from world updates (and `/clock`) are silent, so their reads fail `NOT_READY` after their
timeouts; the device resource reads no topic. The deployment's gazebo_ros and Gazebo must be the pinned 2.8.7 (Melodic) and 9.19.0 releases the
companion citations name; rosbridge cannot read their versions. The pause also freezes the arm: gazebo_ros_control updates the controllers and writes their commands only
from the world update (`gazebo_ros_control_plugin.cpp:196-199, 211-257`).

No unpause is offered (the orchestrator's SAFE-042 condition). On an unpause the trajectory controller resumes any
accepted MoveIt trajectory and the custom controller, if it runs, its stored `command_`; no command value means "hold"
and the joint positions are not observable while paused, so the package cannot clear them first. After
`mhs.safety.reset` the world stays paused and a joint-position command only replaces the stored `command_`; the
operator recovers outside MHS (`/robot_control_stop` or stopping move_group, the custom controller switched off, then
the Gazebo GUI play button or `rosservice call gazebo/unpause_physics`). The launch starts rosbridge on port 9090
(`simulation.launch:59-62`), so any rosbridge client can unpause the world too. `/joint_states` left the device
resource: it is published by `joint_state_controller` from the world update and silent while paused; it stays the
explicit read `x-cap.erdalpekel.joint_states.v1`, and the joint-position receipt reports the positions it sent.

## Fidelity

The fake is a ROS-free analytic stand-in, not a recording. Its engine is
`analytic:ROS-free rosbridge fake (no Gazebo, MoveIt or physics)`, level F0, determinism `none`,
`timestep_ms: 0`, `realtime_factor: 0`, reset `none`, no snapshot/restore. It models the three declared
endpoints and the two companion Gazebo services with placeholder messages, and keeps a paused flag that
silences `/joint_states` and stops a publication from moving its placeholder joints. It runs no Gazebo physics, ros_control controller, MoveIt planning group or
Panda dynamics, and its joint values change only when it receives a placeholder joint-position publication. The
upstream launch's controller rates and the ready state are source facts, not claims about the fake's timing.

## Tags

`ros`, `ros1`, `simulation`, `gazebo`, `panda`, `franka`, `joint-position`, `stop`

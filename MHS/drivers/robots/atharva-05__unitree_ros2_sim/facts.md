# Facts and tags for gh.atharva-05/unitree_ros2_sim

Facts about the package's own surface cite the pinned clone at commit `44659704169515708ec46d0428381dc6c7730350` (`path/in/clone:LINE`). Facts about the stop cite the reviewed companion sources that `task.json` declares (user decision of 2026-11-05; the user's authorisation of 2026-11-05 for the clones fetched under `work/companions`, listed in its `LOCK.json`), written `companion:<alias>/<path>:<LINE>`: `gazebo_ros_pkgs` (gh.ros-simulation/gazebo_ros_pkgs, fetched under work/companions as `ros-simulation__gazebo_ros_pkgs@3.9.0` at `ae6e5793a31f5927df89cb58007d2a5eb567baa8`), `gazebo_ros2_control` (gh.ros-controls/gazebo_ros2_control, fetched under work/companions as `ros-controls__gazebo_ros2_control@0.4.12` at `42d875b482f0b254d9032950a91b2c5cbd7d1c3d`) and `gazebo_classic` (gh.gazebosim/gazebo-classic, the corpus clone at `b22c6e15e52299865b31093b8feebc9ca19e26e8`). The version evidence that ties this package's stack to those pins is in `task.json` `companions[].version_evidence`; gate G1 re-checks it, and for a fetched companion also its LOCK.json entry, untracked files and write bits. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The README describes the repository as a simulation environment for the Unitree GO1 robot in Gazebo 11 and ROS 2, tested with ROS Humble on Ubuntu 22.04. | vendor_doc | README.md:3 |
| The README starts go1_gazebo, then unitree_guide2 junior_ctrl; the operator presses 2 for fixed_stand and 5 for move_base mode, in which the robot accepts velocity commands. | vendor_doc | README.md:32-36 |
| The README declares the velocity control interface on the absolute /cmd_vel topic with geometry_msgs/Twist. | vendor_doc | README.md:42-45 |
| The README declares odometry on the absolute /odom topic with nav_msgs/Odometry from the ground-truth plugin. | vendor_doc | README.md:50-53 |
| The README declares 2D LiDAR data on the absolute /scan topic with sensor_msgs/LaserScan from the Gazebo sensor plugin. | vendor_doc | README.md:56-59 |
| The README declares transforms on the absolute /tf topic with tf2_msgs/TFMessage. | vendor_doc | README.md:62-65 |
| The ROS 2 State_move_base constructor creates the state_mb node and calls initRecv(). | upstream_code | unitree_guide2/src/FSM/State_move_base.cpp:49-63 |
| State_move_base::getUserCmd calls setHighCmd with the _vx, _vy and _wz values received from the Twist callback. | upstream_code | unitree_guide2/src/FSM/State_move_base.cpp:77-79 |
| State_move_base::twistCallback copies msg->linear.x, msg->linear.y and msg->angular.z into _vx, _vy and _wz. | upstream_code | unitree_guide2/src/FSM/State_move_base.cpp:81-85 |
| State_move_base::initRecv creates a subscription for geometry_msgs::msg::Twist on the absolute /cmd_vel topic with queue depth 1. | upstream_code | unitree_guide2/src/FSM/State_move_base.cpp:87-90 |
| State_Trotting::setHighCmd writes vx and vy into _vCmdBody and wz into _dYawCmd directly; it does not clamp them. | upstream_code | unitree_guide2/src/FSM/State_Trotting.cpp:129-134 |
| The Go1Robot constructor sets _robVelLimitX to -0.4..0.4, _robVelLimitY to -0.3..0.3 and _robVelLimitYaw to -0.5..0.5. | upstream_code | unitree_guide2/src/common/unitreeRobot.cpp:139-151 |
| The Gazebo ray sensor is configured for 450 samples over 0.0..6.28319 rad, range 0.4..35.0 m and update_rate 30; its plugin remaps ~/out to scan, outputs sensor_msgs/LaserScan and uses frame_name laser_link. | upstream_code | go1_sim/go1_description/xacro/robot.xacro:185-217 |
| The p3d ground-truth plugin tracks body_name base_link, publishes topic_name odom in frame_name odom and updates at 100 Hz. | upstream_code | go1_sim/go1_description/xacro/robot.xacro:220-227 |
| The ROS 2 Estimator creates a node named estimator, a publisher for nav_msgs::msg::Odometry on odom and a tf2_ros TransformBroadcaster. | upstream_code | unitree_guide2/src/control/Estimator.cpp:123-127 |
| Estimator::run fills the odometry message and the odom transform in its ROS 2 block, but the sendTransform and publish calls are commented out. | upstream_code | unitree_guide2/src/control/Estimator.cpp:226-273 |
| KeyBoard::checkCmd maps key 1 to UserCommand::L2_B (passive) and key 5 to UserCommand::L2_Y (move_base). | upstream_code | unitree_guide2/src/interface/KeyBoard.cpp:25-42 |
| State_Passive::enter sets mode 10, zero q, dq and tau, Kp 0 and Kd 8 for the Gazebo platform, and its checkChange returns PASSIVE unless the user command is L2_A. | upstream_code | unitree_guide2/src/FSM/State_Passive.cpp:9-48 |
| FSM::run calls ioInter->setPassive() when checkSafty() returns false. | upstream_code | unitree_guide2/src/FSM/FSM.cpp:38-45 |
| IOROS::RosShutDown(int sig) prints a shutdown message and calls rclcpp::shutdown(). | upstream_code | unitree_guide2/src/interface/IOROS.cpp:236-242 |
| main.cpp's ShutDown(int sig) prints 'stop the controller' and sets the running flag to false. | upstream_code | unitree_guide2/src/main.cpp:30-35 |
| IOROS::initSend creates twelve MotorCmd publishers on the per-leg controller command topics, and initRecv subscribes twelve MotorState topics and /imu_plugin/out. | upstream_code | unitree_guide2/src/interface/IOROS.cpp:352-383 |
| unitree_guide2's CMakeLists sets CATKIN_MAKE ON, SIMULATION ON, REAL_ROBOT OFF and MOVE_BASE ON, and sets ROS_2 only when CATKIN_MAKE, SIMULATION and MOVE_BASE are all on. | upstream_code | unitree_guide2/CMakeLists.txt:11-19 |
| CMake stops with an error when SIMULATION and REAL_ROBOT are both on or both off. | upstream_code | unitree_guide2/CMakeLists.txt:40-42 |
| ROS_2 adds the COMPILE_WITH_ROS2_MB definition. | upstream_code | unitree_guide2/CMakeLists.txt:71-73 |
| main constructs IOROS for the Gazebo platform under COMPILE_WITH_SIMULATION and IOSDK for the real robot under COMPILE_WITH_REAL_ROBOT. | upstream_code | unitree_guide2/src/main.cpp:68-76 |
| For ROBOT_TYPE_Go1 the IOSDK constructor builds its unitree_legged_sdk safety object as LeggedType::Aliengo and its UDP object with LOWLEVEL, 8090, 192.168.123.10 and 8007. | upstream_code | unitree_guide2/src/interface/IOSDK.cpp:10-14 |
| navigation.launch.py starts Nav2's controller_server with cmd_vel remapped to cmd_vel. | upstream_code | go1_sim/go1_navigation/launch/navigation.launch.py:118-127 |
| start_world.launch.py includes gazebo_ros's gazebo.launch.py. | upstream_code | go1_sim/go1_gazebo/launch/start_world.launch.py:44-50 |
| junior_ctrl's main loop calls ControlFrame::run until SIGINT clears the running flag. | upstream_code | unitree_guide2/src/main.cpp:106-110 |
| FSM::run exchanges commands and states, runs the estimator and the current state, and waits for the rest of its period on the system clock. | upstream_code | unitree_guide2/src/FSM/FSM.cpp:38-66 |
| State_move_base is a State_Trotting whose checkChange goes to PASSIVE on L2_B and to FIXEDSTAND on L2_A. | upstream_code | unitree_guide2/src/FSM/State_move_base.cpp:49-75 |
| The trotting state starts the gait wave when checkStepOrNot is true and sets all four legs to stance otherwise. | upstream_code | unitree_guide2/src/FSM/State_Trotting.cpp:95-99 |
| checkStepOrNot is true when the commanded x or y velocity exceeds 0.03, a position error exceeds 0.08, a velocity error exceeds 0.05 or the yaw-rate command exceeds 0.20. | upstream_code | unitree_guide2/src/FSM/State_Trotting.cpp:115-127 |
| KeyBoard::checkCmd maps key 2 to UserCommand::L2_A (fixed stand). | upstream_code | unitree_guide2/src/interface/KeyBoard.cpp:25-30 |
| gzserver.launch.py adds the init and factory gazebo_ros system plugins to the server command. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/gzserver.launch.py:55-56 |
| gzserver.launch.py defaults its init and factory arguments to true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/gzserver.launch.py:186-193 |
| The init plugin takes the shared gazebo_ros node from gazebo_ros::Node::Get(). | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_init.cpp:150-154 |
| gazebo_ros::Node::Get creates the shared node named gazebo with an empty namespace. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/node.cpp:159-171 |
| The gazebo_ros executor spins its nodes on a thread of its own. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/executor.cpp:22-23 |
| The init plugin creates the pause_physics and unpause_physics services with the std_srvs::srv::Empty type. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_init.cpp:266-277 |
| OnPause calls world_->SetPaused(true). | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_init.cpp:328-333 |
| OnUnpause calls world_->SetPaused(false). | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_init.cpp:335-340 |
| The init plugin publishes the simulation clock from a world-update-begin callback. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_init.cpp:206-207 |
| The factory plugin creates the get_model_list service with the gazebo_msgs::srv::GetModelList type. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_factory.cpp:139-143 |
| GetModelList sets header.stamp to the world's simulation time, lists the model names and sets success true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_factory.cpp:164-174 |
| The GetModelList response documents header.stamp as the simulation time when the data was collected. | upstream_code | companion:gazebo_ros_pkgs/gazebo_msgs/srv/GetModelList.srv:2-5 |
| World::Step advances simulation time and calls Update only when the world is not paused, a step increment is pending or a reset is due; otherwise it adds the step to the pause time. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:835-854 |
| World::Step holds worldUpdateMutex while it steps the world. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:824-827 |
| World::SetPaused stores the paused flag under worldUpdateMutex. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1585-1593 |
| World::IsPaused returns the stored paused flag. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1579-1582 |
| World::Update fires the worldUpdateBegin event and then updates every model. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:920-929 |
| World::Step calls ProcessMessages after the paused or unpaused branch, so pending messages are processed on every step, paused or not. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:835-863 |
| A WorldControl message with step calls OnStep, and one with multi_step pauses the world and sets the number of steps to run while paused. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1630-1640 |
| gazebo_ros2_control spins its controller manager's executor on a thread of its own. | upstream_code | companion:gazebo_ros2_control/gazebo_ros2_control/src/gazebo_ros2_control_plugin.cpp:400-407 |
| gazebo_ros2_control connects its Update to the world-update begin event. | upstream_code | companion:gazebo_ros2_control/gazebo_ros2_control/src/gazebo_ros2_control_plugin.cpp:409-414 |
| gazebo_ros2_control's Update reads the simulation time, updates the controllers and writes their commands to the joints. | upstream_code | companion:gazebo_ros2_control/gazebo_ros2_control/src/gazebo_ros2_control_plugin.cpp:419-437 |

## Scope

The integration is the simulated base's public ROS 2 navigation topic graph, not the Gazebo
physics and not the internal 12-joint controller. The velocity action publishes one
`geometry_msgs/msg/Twist` to the absolute `/cmd_vel` topic; the callback copies only
`linear.x`, `linear.y` and `angular.z` (`unitree_guide2/src/FSM/State_move_base.cpp:81-90`).
Pose and twist are read from `/odom` and `/scan` by explicit read capabilities. The README
documents `/cmd_vel`, `/odom`, `/scan` and `/tf` (`README.md:42-65`).

`/cmd_vel` is accepted only in move_base mode: the README tells the operator to start
`junior_ctrl` and press 5 (`README.md:32-36`). The driver has no ROS observation of the
active FSM mode, so the deployment must ensure that mode before sending velocity commands.
This is a deployment assumption, not an upstream Fact about the endpoint.

The README says `/odom` comes from the ground-truth plugin, and that is its only publisher at
the pin: the p3d plugin publishes `topic_name odom` at 100 Hz
(`go1_sim/go1_description/xacro/robot.xacro:220-227`), while the ROS 2 `estimator` node inside
`junior_ctrl` creates an odom publisher (`unitree_guide2/src/control/Estimator.cpp:123-127`)
whose publish call, like its `sendTransform`, is commented out (`Estimator.cpp:226-273`).
`/tf` comes from the navigation helper `go1_navigation/tf_publisher.py`.

Other `/cmd_vel` publishers: `go1_navigation/launch/navigation.launch.py` starts Nav2's servers
with `cmd_vel` remapped to `cmd_vel` (default `robot_namespace` empty); Nav2's controller
overrides this package's setpoints while navigating. A scan whose ranges contain inf or NaN
fails the read without output, because the bridge refuses non-finite numbers.

The clone also holds the real-robot UDP interface `IOSDK` (`main.cpp:68-76`,
`IOSDK.cpp:10-14`), but `ROS_2` and hence the move_base `/cmd_vel` state are compiled only in
simulation builds (`CMakeLists.txt:11-19, 40-42, 71-73`), and the unitree_legged_sdk library it
links is not in the clone; this binding has no real-robot path at the pin (model review,
2026-11-05).

`NOT COVERED: /tf, /imu_plugin/out, the twelve MotorCmd/MotorState controller topics, the
Gazebo world and collisions, the state machine's mode transitions, Nav2, RViz and any live
ROS graph.` The fake is a ROS-free analytic stand-in, not a recording of captured traffic.

## Limits

The `/cmd_vel` callback itself copies the Twist values without a numeric bound
(`unitree_guide2/src/FSM/State_move_base.cpp:77-85`,
`unitree_guide2/src/FSM/State_Trotting.cpp:129-134`). The driver therefore declares the
Go1Robot model's own configured velocity limits and enforces them in the MHS envelope
before publication:

* `linear_x`: -0.4 to 0.4 m/s, cited to `unitree_guide2/src/common/unitreeRobot.cpp:149`
  (`_robVelLimitX << -0.4, 0.4;`).
* `linear_y`: -0.3 to 0.3 m/s, cited to `unitree_guide2/src/common/unitreeRobot.cpp:150`
  (`_robVelLimitY << -0.3, 0.3;`).
* `angular_z`: -0.5 to 0.5 rad/s, cited to `unitree_guide2/src/common/unitreeRobot.cpp:151`
  (`_robVelLimitYaw << -0.5, 0.5;`).

These are robot-model limits, not a claim that the upstream move_base callback clamps the
Twist. The envelope is the driver's enforced bound; a value outside it is refused before any
publication. The keyboard path's `invNormalize` uses the same model limits
(`unitree_guide2/src/FSM/State_Trotting.cpp:136-143`), but the package does not expose the
keyboard. The ray sensor's 450 samples and 0.4..35.0 m range
(`go1_sim/go1_description/xacro/robot.xacro:185-217`) are read-side facts, not command
limits, and are not declared as Limits.

## Safety

The declaration is `mode = "simulated"` and `device_kind = "robot.mobile_base"`, with `risk = "R2"` because the
catalogue class for a mobile base is R2 and the card floor is R0. The pinned clone has no ROS stop, pause or reset
service or action of its own: the internal keyboard `L2_B` passive path (`KeyBoard.cpp:25-42`,
`State_Passive.cpp:9-48`), the internal safety check (`FSM.cpp:38-45`) and the SIGINT handlers (`IOROS.cpp:236-242`,
`main.cpp:30-35`) are not ROS bindings, and an all-zero Twist publication is transmission only.

The e-stop is the Gazebo world pause of the simulator's own repository, a reviewed companion fetched at a pinned
commit: `/pause_physics` (gazebo_ros 3.9.0 for ROS 2 Humble; `OnPause` calls `World::SetPaused(true)`). ROS 2
gazebo_ros has no service that reports the paused flag, so the stop is confirmed by a stall read-back (E1): two
`/get_model_list` answers at least 250 ms apart whose `header.stamp`, the world's simulation time
(`GetModelList` sets it from `world_->SimTime()`), did not change, each with `success` true. A pause that is not
answered, a failed read-back, a missing stamp or a stamp that advanced is `MHS.SAFETY.SAFE_STATE_UNREACHED` with the
latch held and a background retry. `World::Step` of Gazebo 11.15.1 advances simulation time and runs the world
update only while the world is not paused, a step increment is pending or a reset is due. A frozen stamp is also what
a hung but unpaused server shows (nothing advances then either), and a GUI step or a WorldControl multi_step between
the samples fails the check (fails closed). The worst case (pause 400 ms, two read-backs of 300 ms, 250 ms apart)
exceeds the default 1000 ms e-stop budget, so the package declares `estop_latency_ms = 1500` (gate G3 checks the
arithmetic). It is a frozen simulation time, not a measured standstill: any ROS 2 client of `/unpause_physics`, the
Gazebo GUI or a WorldControl message can advance or unpause the world, and MHS does not watch it after the e-stop.
While paused, the topics published from world updates (and `/clock`) are silent, so their reads fail `NOT_READY`
after their timeouts; the device resource reads no topic. The deployment's gazebo_ros, Gazebo, gazebo_ros2_control 0.4.12 and Gazebo 11.15.1 must be the
pinned releases the companion citations name; rosbridge cannot read their versions. The pause also
freezes the legs: gazebo_ros2_control updates the controllers and writes their commands only from the world update
(`gazebo_ros2_control_plugin.cpp:409-414, 419-437`).

No unpause is offered (the orchestrator's SAFE-042 condition). A zero Twist would clear move_base's stored velocity
(`State_move_base.cpp:81-85`), and the trotting state stands once its errors are below its thresholds
(`State_Trotting.cpp:95-99, 115-127`), but `junior_ctrl`'s loop keeps running on the system clock through the pause
(`main.cpp:106-110`, `FSM.cpp:38-66`) on the last joint and IMU states it received, so the stored command does not
alone decide what the legs do when the world resumes; Nav2's controller also publishes `/cmd_vel`. After
`mhs.safety.reset` the world stays paused and a cmd_vel command is stored for the next unpause; the operator recovers
outside MHS (junior_ctrl key 2 for fixed_stand, `KeyBoard.cpp:25-30`, or stopping junior_ctrl, then the Gazebo GUI
play button or `ros2 service call /unpause_physics std_srvs/srv/Empty`). `/odom` left the device resource (the p3d
plugin publishes it from the world update); it is the explicit read `x-cap.atharva-05.odometry.v1`, and the cmd_vel
receipt reports the values it sent.

`driver.lock.json` keeps `reviewed_by: null`; this is a model-authored, unreviewed package. No physical emergency
stop, hardware run or human review is claimed.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS fake (no physics)`, level F0,
determinism `none`, `timestep_ms: 0` (event-driven, no physics step), `realtime_factor: 0`
(not paced), reset `none`, and no snapshot/restore. The gaps disclose that the fake is not a
recording, that the odometry pose and scan values are placeholders, that the odometry twist
only echoes the last publication, that the scan returns three placeholder ranges while the
real ray plugin is configured for 450 samples, and that no physics, state machine or ROS
graph runs. The fake keeps a paused flag that `/pause_physics` sets, a placeholder simulation
time that `/get_model_list` reports and that advances on every answer unless paused, and
silences `/odom` and `/scan` while paused.

## Tags

`ros`, `ros2`, `gazebo`, `simulation`, `mobile-base`, `cmd-vel`, `odometry`, `laser-scan`,
`unitree`, `go1`

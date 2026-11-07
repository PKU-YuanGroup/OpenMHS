# Facts and tags for gh.agilexrobotics/ugv_gazebo_sim

Facts about the package's own surface cite the pinned clone at commit `27633a956c845903ee630538afeb17fe70afdd84` (`path/in/clone:LINE`). Facts about the stop, the paused world and `/gazebo/model_states` cite the reviewed companion sources that `task.json` declares (user decision of 2026-11-05; the user's authorisation of 2026-11-05 for the clones fetched under `work/companions`, listed in its `LOCK.json`), written `companion:<alias>/<path>:<LINE>`: `gazebo_ros_pkgs` (gh.ros-simulation/gazebo_ros_pkgs, fetched under work/companions as `ros-simulation__gazebo_ros_pkgs@2.8.7` at `0667c5e52e8afa1f478955d8a2569b473a5acdf1`) and `gazebo_classic` (gh.gazebosim/gazebo-classic, fetched under work/companions as `gazebosim__gazebo-classic@gazebo9_9.19.0` at `e4400ae7e04e4859eec392ac67b813402703bab0`). The version evidence that ties this package's stack to those pins is in `task.json` `companions[].version_evidence`. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

`/gazebo/model_states` is a fact, not a command. The package clone never names that topic, and a command binding may not cite a companion. The API plugin advertises the relative name `model_states` on its private node handle. This page does not claim the clone contains the absolute string `/gazebo/model_states`.

## Scope

Served launch: `scout/scout_gazebo_sim/launch/scout_empty_world.launch` (Scout V2) only. Not served: the product directories `autokit`, `bunker`, `hunter`, `hunter_se`, `limo`, `limo_s2`, `ranger`, `ranger_air`, `ranger_delta`, `ranger_mini`, `tracer` and `tracer_mini`, and any other launch file under `scout/`. The commented `libgazebo_ros_skid_steer_drive.so` and `libgazebo_ros_planar_move.so` blocks are not live plugins. No odometry topic is bound. No unpause is bound.

## Tags

`ros`, `ros1`, `simulation`, `gazebo`, `scout`, `scout-v2`, `cmd-vel`

## Facts

| fact | source | ref |
|---|---|---|
| scout_empty_world.launch defaults robot_namespace to /. | upstream_code | scout/scout_gazebo_sim/launch/scout_empty_world.launch:3 |
| scout_empty_world.launch defaults world_name to $(find scout_gazebo_sim)worlds/weston_robot_empty.world. | upstream_code | scout/scout_gazebo_sim/launch/scout_empty_world.launch:6 |
| scout_empty_world.launch includes $(find gazebo_ros)/launch/empty_world.launch. | upstream_code | scout/scout_gazebo_sim/launch/scout_empty_world.launch:7 |
| That include passes paused false, use_sim_time true, gui true, headless false and debug false. | upstream_code | scout/scout_gazebo_sim/launch/scout_empty_world.launch:8-13 |
| scout_empty_world.launch includes spawn_scout_v2.launch. | upstream_code | scout/scout_gazebo_sim/launch/scout_empty_world.launch:16 |
| spawn_scout_v2.launch defines arg paused with default true. | upstream_code | scout/scout_gazebo_sim/launch/spawn_scout_v2.launch:11 |
| spawn_model is invoked with -unpause and -model 'scout$(arg robot_namespace)'. | upstream_code | scout/scout_gazebo_sim/launch/spawn_scout_v2.launch:21-28 |
| spawn_scout_v2.launch loads scout_v2_control.yaml onto the parameter server. | upstream_code | scout/scout_gazebo_sim/launch/spawn_scout_v2.launch:31 |
| controller_spawner is started with scout_state_controller and the four scout_motor_fr, fl, rl and rr controllers. | upstream_code | scout/scout_gazebo_sim/launch/spawn_scout_v2.launch:34 |
| The scout_skid_steer_controller node sets the private robot_namespace parameter from the launch arg. | upstream_code | scout/scout_gazebo_sim/launch/spawn_scout_v2.launch:37-38 |
| scout_v2.gazebo loads the plugin gazebo_ros_control from libgazebo_ros_control.so. | upstream_code | scout/scout_description/urdf/scout_v2.gazebo:26-30 |
| The skid_steer_drive_controller block that names libgazebo_ros_skid_steer_drive.so is inside an XML comment. | upstream_code | scout/scout_description/urdf/scout_v2.gazebo:43-63 |
| The object_controller block that names libgazebo_ros_planar_move.so is inside an XML comment. | upstream_code | scout/scout_description/urdf/scout_v2.gazebo:65-73 |
| ScoutSkidSteer sets cmd_topic_ to robot_name_ concatenated with the literal /cmd_vel. | upstream_code | scout/scout_gazebo_sim/src/scout_skid_steer.cpp:22 |
| ScoutSkidSteer sets the four motor command topics to robot_name_ concatenated with /scout_motor_fr_controller/command, /scout_motor_fl_controller/command, /scout_motor_rl_controller/command and /scout_motor_rr_controller/command. | upstream_code | scout/scout_gazebo_sim/src/scout_skid_steer.cpp:18-21 |
| SetupSubscription subscribes to cmd_topic_ as geometry_msgs::Twist with queue size 5. | upstream_code | scout/scout_gazebo_sim/src/scout_skid_steer.cpp:27-28 |
| SetupSubscription advertises four std_msgs::Float64 publishers on the motor command topics. | upstream_code | scout/scout_gazebo_sim/src/scout_skid_steer.cpp:31-34 |
| scout_skid_steer.cpp includes geometry_msgs/Twist.h and std_msgs/Float64.h. | upstream_code | scout/scout_gazebo_sim/src/scout_skid_steer.cpp:12-13 |
| TwistCmdCallback reads linear.x and angular.z, sets k to 1.4, and publishes four Float64 commands. | upstream_code | scout/scout_gazebo_sim/src/scout_skid_steer.cpp:37-57 |
| The header sets SCOUT_WHEELBASE to 0.498 and SCOUT_WHEEL_RADIUS to 0.16459. | upstream_code | scout/scout_gazebo_sim/include/scout_gazebo/scout_skid_steer.hpp:33-34 |
| The header includes geometry_msgs/Twist.h. | upstream_code | scout/scout_gazebo_sim/include/scout_gazebo/scout_skid_steer.hpp:13 |
| The header declares TwistCmdCallback. | upstream_code | scout/scout_gazebo_sim/include/scout_gazebo/scout_skid_steer.hpp:45 |
| scout_skid_steer_controller initialises the node name scout_odom and reads the private parameter robot_namespace with default string scout_default. | upstream_code | scout/scout_gazebo_sim/src/scout_skid_steer_controller.cpp:14-20 |
| The node then calls SetupSubscription and ros::spin. | upstream_code | scout/scout_gazebo_sim/src/scout_skid_steer_controller.cpp:24-27 |
| scout_v2_control.yaml sets scout_state_controller to joint_state_controller/JointStateController with publish_rate 50 and names no topic. | upstream_code | scout/scout_gazebo_sim/config/scout_v2_control.yaml:2-4 |
| scout_v2_control.yaml sets four controllers to velocity_controllers/JointVelocityController. | upstream_code | scout/scout_gazebo_sim/config/scout_v2_control.yaml:11-40 |
| scout_gazebo_sim package.xml declares the license BSD. | upstream_code | scout/scout_gazebo_sim/package.xml:10 |
| scout_gazebo_sim package.xml buildtool_depend is catkin. | upstream_code | scout/scout_gazebo_sim/package.xml:16 |
| scout_gazebo_sim package.xml run_depend entries include gazebo_ros and gazebo_ros_control. | upstream_code | scout/scout_gazebo_sim/package.xml:24-25 |
| The Scout README names ROS Melodic on the development-environment line. | upstream_code | scout/README.md:23 |
| The Scout README installs ros-melodic-ros-controllers with apt-get. | upstream_code | scout/README.md:36 |
| The Scout README installs ros-melodic-gazebo-ros with apt-get. | upstream_code | scout/README.md:42 |
| The Scout README installs ros-melodic-gazebo-ros-control with apt-get. | upstream_code | scout/README.md:48 |
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
| The API plugin advertises the relative name model_states as gazebo_msgs::ModelStates on gazebo_queue_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:382-388 |
| onModelStatesConnect connects publishModelStates to WorldUpdateBegin when the subscriber count becomes 1. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:554-558 |
| publishModelStates appends each model's GetName, a pose taken from WorldPose and a twist taken from WorldLinearVel and WorldAngularVel, then publishes the ModelStates message. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:2203-2244 |
| ModelStates.msg declares name, pose and twist arrays, and its comments call pose and twist desired. | upstream_code | companion:gazebo_ros_pkgs/gazebo_msgs/msg/ModelStates.msg:1-4 |
| gazebo_ros_control connects its Update to the world-update begin event. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros_control/src/gazebo_ros_control_plugin.cpp:196-199 |
| gazebo_ros_control's Update reads the simulation time, updates the controllers and writes their commands to the simulated joints. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros_control/src/gazebo_ros_control_plugin.cpp:211-257 |
| World::Step advances simulation time and calls Update only when the world is not paused, a step increment is pending or a reset is due; otherwise it adds the step to the pause time. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:691-710 |
| World::Step holds worldUpdateMutex while it steps the world. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:683 |
| World::SetPaused stores the paused flag under worldUpdateMutex. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1428-1436 |
| World::IsPaused returns the stored paused flag. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1422-1425 |
| World::Update fires the worldUpdateBegin event and then updates every model. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:776-782 |
| World::Step calls ProcessMessages after the paused or unpaused branch, so pending messages are processed on every step, paused or not. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:691-718 |
| A WorldControl message with step calls OnStep, and one with multi_step pauses the world and sets the number of steps to run while paused. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1462-1477 |

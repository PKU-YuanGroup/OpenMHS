# Facts and tags for gh.mortezaaliyari/multi-robot-gazebo-navistack

Facts about the package's own surface cite the pinned clone at commit `afcc20c73158370f32cf123a0d73a698f9d02579` (`path/in/clone:LINE`). Facts about the stop cite the two reviewed companion sources that `task.json` declares (user decision of 2026-11-05) at their corpus pins, written `companion:<alias>/<path>:<LINE>`: `gazebo_ros_pkgs` (gh.ros-simulation/gazebo_ros_pkgs at `cd9cc952402375be5f274f39b29399c4087aa839`, gazebo_ros 2.9.3 for ROS 1 Noetic) and `gazebo_classic` (gh.gazebosim/gazebo-classic at `b22c6e15e52299865b31093b8feebc9ca19e26e8`, Gazebo 11.15.1). The version evidence that ties this package's stack to those pins is in `task.json` `companions[].version_evidence`; gate G1 re-checks it. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| README.md states the project targets Ubuntu Focal, ROS Noetic and Gazebo 11. | vendor_doc | README.md:11-14 |
| The closeworld2 launch includes gazebo_ros empty_world.launch with the closeworld2 world, paused=false and use_sim_time=true. | upstream_code | turtlebot3_gazebo/launch/multi_turtlebot3_closeworld2.launch:16-23 |
| The closeworld2 launch defaults first_tb3 to tb3_0 and second_tb3 to tb3_1. | upstream_code | turtlebot3_gazebo/launch/multi_turtlebot3_closeworld2.launch:3-4 |
| The closeworld2 launch opens a tb3_0 group and selects turtlebot3_burger1.urdf.xacro for it. | upstream_code | turtlebot3_gazebo/launch/multi_turtlebot3_closeworld2.launch:25-26 |
| The closeworld2 launch opens a tb3_1 group and selects turtlebot3_burger2.urdf.xacro for it. | upstream_code | turtlebot3_gazebo/launch/multi_turtlebot3_closeworld2.launch:41-42 |
| The burger1 Gazebo differential-drive plugin subscribes to the relative cmd_vel topic and publishes odometry on the relative odom topic. | upstream_code | turtlebot3/turtlebot3_description/urdf/turtlebot3_burger1.gazebo.xacro:51-55 |
| The burger2 Gazebo differential-drive plugin subscribes to the relative cmd_vel topic and publishes odometry on the relative odom topic. | upstream_code | turtlebot3/turtlebot3_description/urdf/turtlebot3_burger2.gazebo.xacro:51-55 |
| The burger1 laser sensor publishes scan at 5 Hz with 360 samples over 0 to 6.28319 rad and a range of 0.120 to 3.5 m. | upstream_code | turtlebot3/turtlebot3_description/urdf/turtlebot3_burger1.gazebo.xacro:104-121 |
| The burger2 laser sensor publishes scan at 5 Hz with 360 samples over 0 to 6.28319 rad and a range of 0.120 to 3.5 m. | upstream_code | turtlebot3/turtlebot3_description/urdf/turtlebot3_burger2.gazebo.xacro:104-121 |
| The shipped C++ drive-node header includes sensor_msgs/LaserScan, geometry_msgs/Twist and nav_msgs/Odometry. | upstream_code | turtlebot3_gazebo/include/turtlebot3_gazebo/turtlebot3_drive.h:22-26 |
| The drive node reads cmd_vel_topic_name, advertises geometry_msgs::Twist on it and subscribes to the relative scan and odom topics. | upstream_code | turtlebot3_gazebo/src/turtlebot3_drive.cpp:42-57 |
| The drive node uses compile-time LINEAR_VELOCITY 0.3 and ANGULAR_VELOCITY 1.5 constants for its own obstacle-avoidance loop; the clone states no signed cmd_vel envelope for these topics. | upstream_code | turtlebot3_gazebo/include/turtlebot3_gazebo/turtlebot3_drive.h:35-36 |
| The navigation launch sets use_sim_time true and includes amcl1, amcl2, move_base1 and move_base2. | upstream_code | turtlebot3/turtlebot3_navigation/launch/turtlebot3_navigation.launch:1-27 |
| move_base1 defaults cmd_vel_topic to /tb3_0/cmd_vel, odom_topic to /tb3_0/odom and laser_topic to /tb3_0/scan. | upstream_code | turtlebot3/turtlebot3_navigation/launch/move_base1.launch:8-11 |
| move_base1 remaps its cmd_vel, odom and scan topics to those absolute tb3_0 topics. | upstream_code | turtlebot3/turtlebot3_navigation/launch/move_base1.launch:33-35 |
| move_base2 defaults cmd_vel_topic to /tb3_1/cmd_vel, odom_topic to /tb3_1/odom and laser_topic to /tb3_1/scan. | upstream_code | turtlebot3/turtlebot3_navigation/launch/move_base2.launch:8-11 |
| move_base2 remaps its cmd_vel, odom and scan topics to those absolute tb3_1 topics. | upstream_code | turtlebot3/turtlebot3_navigation/launch/move_base2.launch:33-35 |
| The README tells the operator to set the RViz 2D Nav Goal topic to /tb3_1 or /tb3_2. | vendor_doc | README.md:39-40 |
| The gazebo_ros gzserver wrapper adds libgazebo_ros_api_plugin to the server's plugins unless the arguments already name it. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/scripts/gzserver:20-24 |
| empty_world.launch starts the Gazebo server as the node named gazebo of package gazebo_ros, with the physics engine argument -e $(arg physics). | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:46-48 |
| empty_world.launch defaults its physics argument to ode. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:15 |
| empty_world.launch defaults its gui argument to true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:8 |
| When gui is true, empty_world.launch starts the node gazebo_gui of type gzclient. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:51-54 |
| The API plugin calls ros::init with the node name gazebo when ROS is not initialised yet. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:125-126 |
| The API plugin creates its node handle in the private namespace ~ and advertises its topics and services there. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:145 |
| The API plugin advertises the service pause_physics with the std_srvs::Empty type on its own callback queue gazebo_queue_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:492-498 |
| The API plugin advertises the service unpause_physics with the std_srvs::Empty type on gazebo_queue_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:501-507 |
| The API plugin advertises the service get_physics_properties with the gazebo_msgs::GetPhysicsProperties type on gazebo_queue_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:383-389 |
| gazeboQueueThread serves gazebo_queue_ in a loop with a 0.001 s wall-clock wait while the node handle is ok. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:257-264 |
| pausePhysics calls world_->SetPaused(true) and returns true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1725-1729 |
| unpausePhysics calls world_->SetPaused(false) and returns true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1731-1735 |
| getPhysicsProperties sets res.pause to world_->IsPaused(). | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1489 |
| getPhysicsProperties sets success true only when the physics engine type is ode; for any other engine it sets success false and returns false. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1496-1528 |
| The GetPhysicsProperties response field pause is true if the physics engine is paused. | upstream_code | companion:gazebo_ros_pkgs/gazebo_msgs/srv/GetPhysicsProperties.srv:4 |
| Among the world-update begin hooks that its comment says apply forces and publish sim time on /clock, the API plugin connects publishSimTime. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:219-222 |
| World::Step advances simulation time and calls Update only when the world is not paused, a step increment is pending or a reset is due; otherwise it adds the step to the pause time. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:835-854 |
| World::Step holds worldUpdateMutex while it steps the world. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:824-827 |
| World::SetPaused stores the paused flag under worldUpdateMutex. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1585-1593 |
| World::IsPaused returns the stored paused flag. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1579-1582 |
| World::Update fires the worldUpdateBegin event and then updates every model. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:920-929 |
| World::Step calls ProcessMessages after the paused or unpaused branch, so pending messages are processed on every step, paused or not. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:835-863 |
| A WorldControl message with step calls OnStep, and one with multi_step pauses the world and sets the number of steps to run while paused. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1630-1640 |
| GazeboRosDiffDrive subscribes to its command topic with cmdVelCallback on the plugin's own callback queue. | upstream_code | companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_diff_drive.cpp:159-164 |
| GazeboRosDiffDrive connects UpdateChild to the world-update begin event. | upstream_code | companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_diff_drive.cpp:177-179 |
| When more than the update period of simulation time has passed, UpdateChild publishes odometry, reads the requested wheel speeds and sets the wheel joint velocities. | upstream_code | companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_diff_drive.cpp:269-289 |
| getWheelVelocities derives both wheel speeds from the stored x_ and rot_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_diff_drive.cpp:324-333 |
| cmdVelCallback stores linear.x in x_ and angular.z in rot_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_diff_drive.cpp:335-340 |
| QueueThread serves the plugin's callback queue with a 0.01 s wall-clock wait while the plugin is alive. | upstream_code | companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_diff_drive.cpp:342-349 |

## Scope and safety

The pinned clone runs ROS 1 Noetic and Gazebo 11. The closeworld2 launch spawns two TurtleBot3 Burger models in
the `tb3_0` and `tb3_1` groups; their Gazebo differential-drive plugins read the relative `cmd_vel` topic and
publish `odom`, and their laser sensors publish 360-sample `scan` messages at 5 Hz. The navigation launch runs
move_base1 and move_base2, whose launch defaults and remaps resolve those robot topics to `/tb3_0/...` and
`/tb3_1/...`.

The package exposes only the direct command topics and four explicit scan/odometry reads; the device resource
reads no topic, because odometry and laser scans are published only while the world runs (see the stop below), and a
cmd_vel receipt reports the two values it sent (the transmitted request). It does not expose the
move_base goal action: the pinned clone names the action topics but contains no `move_base_msgs/MoveBaseAction`
declaration, so the RosDriver action binding cannot cite a real upstream action type. It also does not expose
`/clock`, TF or the map server. The README's 2D Nav Goal examples mention `/tb3_1` and `/tb3_2`; the launch files
in this pin use `tb3_0` and `tb3_1`, so those README topic names are not used here.

A rosbridge publication reports only `published=true` and `confirmed=false`. The differential-drive plugin and
move_base do not acknowledge a velocity, arrival or stop on these topics, and the clone registers no stop service.
The stop is the Gazebo world pause of the companion gazebo_ros, which gazebo_ros's `gzserver` wrapper loads into the
server that the closeworld2 launch starts through `empty_world.launch`:

- e-stop: `/gazebo/pause_physics` (`std_srvs/Empty`): `pausePhysics` calls `World::SetPaused(true)`;
- read-back (`safety_bindings.safe_state`): `/gazebo/get_physics_properties`; the e-stop is confirmed only when its
  `pause` field is true. A failed pause, a failed read-back (a non-ODE engine) or a read-back with `pause` false gives
  `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held and a background retry;
- re-enable after a reset (`x-cap.mortezaaliyari.resume.v1`, `reenable=True`, CORE-086): it first publishes a zero
  `Twist` on `/tb3_0/cmd_vel` and `/tb3_1/cmd_vel`, then calls `/gazebo/unpause_physics`. `mhs.safety.reset` only
  releases the latch; the world stays paused until the resume runs.

One pause stops both robots: the gazebo_ros differential-drive plugin sets the wheel velocities and publishes odometry
only from its world-update hook, which a paused `World::Step` never calls. It is the paused flag, not a measured
standstill. Each plugin keeps storing every `cmd_vel` it receives on its own wall-clock queue thread and applies the
last one when the world runs, with no command timeout; the resume's zeros replace them, but they are unacknowledged,
so a stored command can still act for a few world steps, and move_base1/2 or the drive node, when they run, publish
new commands at any time. A GUI step or a WorldControl `multi_step` advances the paused world, and any client or the
Gazebo GUI can unpause it; MHS does not watch the flag after the e-stop. The deployment's gazebo_ros and Gazebo must
be the pinned 2.9.3 (Noetic) and 11 releases; rosbridge cannot read their versions, and on a graph without gazebo_ros
neither service exists and the e-stop fails with the latch held. The declared risk is R2 (mobile-base transit,
`MHS/spec/04-safety.md` section 2.1): in the simulated deployment the effect is confined to Gazebo, but the command
topics are the relative `cmd_vel` topics of two mobile bases, which a real TurtleBot3 behind the same rosbridge would
also consume, and a simulated label never lowers the risk of a binding that can affect physical equipment.

The compile-time drive-node constants are 0.3 m/s and 1.5 rad/s, but they drive only that node's own
obstacle-avoidance loop. They are not a signed `cmd_vel` envelope, so both velocity inputs use
`Limit.operator_required`: an operator overlay must supply the site bounds before any publication is accepted.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS-free contract fake (no physics)`, level F0,
determinism `none`, `timestep_ms: 0` (event-driven replies with no physics step), `realtime_factor: 0` (not
paced), reset `none`, and no snapshot/restore. The fake is not a recording of captured traffic. It keeps a paused
flag that the pause service sets, the read-back reports and the unpause clears; while it is set it publishes no odom
or scan and only stores a `cmd_vel`. Its GetPhysicsProperties numbers are placeholders. Its scan
arrays and odometry poses are placeholders and do not advance with a simulator; a command updates the odometry
stand-in by a placeholder increment so the publication has a visible state effect, but that increment is not
physics, integration time or a measured trajectory. The gaps disclose the absent Gazebo/physics/navigation
stack, the placeholder observations, the transmission-only publication receipt and the out-of-scope move_base
action, `/clock`, TF and map server.

## Tags

`ros`, `ros1`, `simulation`, `gazebo`, `turtlebot3`, `multi-robot`, `navigation`, `cmd-vel`

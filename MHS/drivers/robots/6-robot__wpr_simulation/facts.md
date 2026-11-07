# Facts and tags for gh.6-robot/wpr_simulation

Facts about the package's own surface cite the pinned clone at commit `9c2861944205b087e55482d46911cb1819532be6` (`path/in/clone:LINE`). Facts about the stop cite the two reviewed companion sources that `task.json` declares (user decision of 2026-11-05) at their corpus pins, written `companion:<alias>/<path>:<LINE>`: `gazebo_ros_pkgs` (gh.ros-simulation/gazebo_ros_pkgs at `cd9cc952402375be5f274f39b29399c4087aa839`, gazebo_ros 2.9.3 for ROS 1 Noetic) and `gazebo_classic` (gh.gazebosim/gazebo-classic at `b22c6e15e52299865b31093b8feebc9ca19e26e8`, Gazebo 11.15.1). The version evidence that ties this package's stack to those pins is in `task.json` `companions[].version_evidence`; gate G1 re-checks it. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| WPRPlugin::Load assigns the default command topic literal "cmd_vel" to command_topic_. | upstream_code | src/wpr_plugin.cpp:60 |
| WPRPlugin::Load assigns the default odometry topic literal "odom" to odometry_topic_. | upstream_code | src/wpr_plugin.cpp:70 |
| The plugin header includes the generated geometry_msgs/Twist and nav_msgs/Odometry headers. | upstream_code | include/wpr_simulation/wpr_plugin.h:49-51 |
| The plugin creates a geometry_msgs::Twist subscriber on command_topic_ and advertises a nav_msgs::Odometry publisher on odometry_topic_. | upstream_code | src/wpr_plugin.cpp:173-178 |
| WPRPlugin::cmdVelCallback stores linear.x, linear.y and angular.z in x_, y_ and rot_ under the plugin lock and sends no acknowledgement. | upstream_code | src/wpr_plugin.cpp:237-243 |
| On every world update WPRPlugin::UpdateChild adds a yaw torque from the difference between the world yaw rate and rot_ and relative forces from x_ and y_ minus the relative linear velocity, each times its p gain, and publishes odometry when more than 1/odometry_rate_ of simulated time has passed. | upstream_code | src/wpr_plugin.cpp:186-207 |
| The shipped wpb_home.model configures the WPR plugin with commandTopic cmd_vel and odometryTopic odom and no robotNamespace override. | upstream_code | models/wpb_home.model:232-233 |
| wpb_home_sim advertises the absolute /wpb_home/pose_diff topic with the geometry_msgs::Pose2D type. | upstream_code | src/wpb_home_sim.cpp:166 |
| In a 20 Hz loop, when the /pose_reset to /base_footprint transform is available within 1 s, wpb_home_sim publishes pose_diff with x and y set to 0.9 times that transform's translation and theta set to its yaw minus pose_reset.theta. | upstream_code | src/wpb_home_sim.cpp:172-187 |
| wpb_home_sim subscribes to /wpb_home/mani_ctrl, /wpb_home/ctrl and /odom. | upstream_code | src/wpb_home_sim.cpp:163-165 |
| A /wpb_home/ctrl message containing 'pose_diff reset' sets pose_reset to the current odometry pose, and every /odom message re-broadcasts the /odom to /pose_reset transform. | upstream_code | src/wpb_home_sim.cpp:117-143 |
| wpb_home_controllers.launch starts the wpb_home_sim node. | upstream_code | launch/wpb_home_controllers.launch:23 |
| The shipped wpb_simple.launch starts the Gazebo empty_world include with paused=false and use_sim_time=true. | upstream_code | launch/wpb_simple.launch:5-7 |
| WPRPlugin connects UpdateChild to the world-update begin event. | upstream_code | src/wpr_plugin.cpp:182 |
| WPRPlugin::QueueThread serves the plugin's callback queue with a 0.01 s wall-clock wait while the plugin is alive and its node handle is ok. | upstream_code | src/wpr_plugin.cpp:245-251 |
| wpb_simple.launch includes gazebo_ros's empty_world.launch. | upstream_code | launch/wpb_simple.launch:3-10 |
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

## Scope

The package selects the WPR base plugin's ROS contract, the WPB Home pose-difference publication and the Gazebo world
pause of the simulator that runs them. `/cmd_vel` is a `geometry_msgs/Twist` topic publication whose receipt also
reports the three components it handed to rosbridge (the transmitted request, not a measured velocity). `/odom` and
`/wpb_home/pose_diff` are explicit subscription observations. The device resource reads no topic: both topics are
published only while the world runs (`/odom` from `UpdateChild`, which hangs on the world-update event), so a
resource that waited for them would fail `NOT_READY` after every e-stop and reset and delay every command by its
2 s timeout. `pose_diff` is published only by `wpb_home_sim`, which only `wpb_home_controllers.launch` starts
(included by `wpb_home_mani`, `wpb_scene_1` and `wpb_table`, not by `wpb_simple.launch`); its x and y are 0.9 times
the `/pose_reset` to `/base_footprint` translation, an upstream convention passed through unchanged.

## Stop, read-back and re-enable

The clone registers no stop service; the plugin only stores the last command (`src/wpr_plugin.cpp:237-243`) and
applies it at every world update with no command timeout (`src/wpr_plugin.cpp:186-207`). The stop is the Gazebo
world pause served by the companion gazebo_ros API plugin, which the gazebo_ros `gzserver` wrapper loads into the
server that this clone's `wpb_simple.launch` starts through `empty_world.launch`:

- e-stop: `/gazebo/pause_physics` (`std_srvs/Empty`): `pausePhysics` calls `World::SetPaused(true)`;
- read-back (`safety_bindings.safe_state`): `/gazebo/get_physics_properties`; the e-stop is confirmed only when its
  `pause` field (`res.pause = world_->IsPaused()`) is true. A failed pause, a failed read-back (a physics engine other
  than ODE makes the service return false) or a read-back with `pause` false (another client or the GUI unpaused the
  world) gives `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held and a background retry;
- re-enable after a reset (`x-cap.6-robot.resume.v1`, `reenable=True`, CORE-086): it first publishes a zero `Twist`
  on `/cmd_vel`, then calls `/gazebo/unpause_physics`. `mhs.safety.reset` only releases the latch; the world stays
  paused until the resume runs.

What the pause does and does not do (Gazebo classic 11): `World::Step` updates the world only while it is not paused
(or a step is pending or a reset is due), so no model update and no `worldUpdateBegin` callback runs: the plugin
applies no force and publishes no odometry, and gazebo_ros publishes no `/clock`. It is the paused flag, not a
measured standstill. It does not stop: the plugin's callback queue, which keeps storing every `cmd_vel` it receives
(the resume's zero replaces it, but it is an unacknowledged publication handled on that queue thread, so the stored
command can still act for a few world steps after the unpause; any other publisher can store a new one at any time);
pending spawn and delete messages, which every step processes; a GUI step or a WorldControl `multi_step`, which
advances the paused world; and any client or the Gazebo GUI that `empty_world.launch` opens by default, which can
unpause it. MHS does not watch the flag after the e-stop.

## Fidelity contract

`driver.py` describes the deployed fake: engine `canned:ROS fake (no physics)`, level F0, determinism `none`,
`timestep_ms: 0` (event-driven with no physics step), `realtime_factor: 0` (not paced), reset `none`, and no
snapshot/restore. The fake keeps a paused flag that the pause service sets, the read-back reports and the unpause
clears; while it is set the fake publishes no `/odom` or `pose_diff` and only stores a `cmd_vel`. Its
GetPhysicsProperties numbers and every odometry and pose-difference value are placeholders. It runs no Gazebo,
WPRPlugin controller, `wpb_home_sim`, sensor frame, collision or timing.

## Safety

The device is simulated at R2 because the declared command drives a mobile base; its effect is confined to simulated
state. The deployment's gazebo_ros and Gazebo must be the pinned 2.9.3 (Noetic) and 11 releases; rosbridge cannot
read their versions. On a graph without gazebo_ros neither service exists and the e-stop fails with the latch held.
No physical emergency stop is claimed, and a deployment that bridges these topics to real hardware would need a
reviewed R2 device with an independent stop; the Gazebo pause does not reach hardware.

## Tags

`ros`, `ros1`, `simulation`, `gazebo`, `wpr`, `wpb-home`, `cmd-vel`, `odometry`

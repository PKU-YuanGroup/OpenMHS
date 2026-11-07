OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.novog93/sjtu_drone

Facts about the package's own surface cite the pinned clone at commit `3f8627ebddf390fd35ffb84b8654b62e0b66fca2` (`path/in/clone:LINE`). Facts about the stop cite the reviewed companion sources that `task.json` declares (user decision of 2026-11-05; the user's authorisation of 2026-11-05 for the clones fetched under `work/companions`, listed in its `LOCK.json`), written `companion:<alias>/<path>:<LINE>`: `gazebo_ros_pkgs` (gh.ros-simulation/gazebo_ros_pkgs, fetched under work/companions as `ros-simulation__gazebo_ros_pkgs@3.9.0` at `ae6e5793a31f5927df89cb58007d2a5eb567baa8`) and `gazebo_classic` (gh.gazebosim/gazebo-classic, the corpus clone at `b22c6e15e52299865b31093b8feebc9ca19e26e8`). The version evidence that ties this package's stack to those pins is in `task.json` `companions[].version_evidence`; gate G1 re-checks it, and for a fetched companion also its LOCK.json entry, untracked files and write bits. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The shipped model SDF gives the drone plugin's ROS node the namespace /simple_drone. | upstream_code | sjtu_drone_description/models/sjtu_drone/sjtu_drone.sdf:194 |
| The plugin header declares the relative topic defaults cmd_vel, posctrl, imu, takeoff, land, reset and dronevel_mode. | upstream_code | sjtu_drone_description/include/sjtu_drone_description/plugin_drone_private.h:60-68 |
| The plugin header declares the relative topic defaults gt_pose, gt_vel, gt_acc, cmd_mode, state and odom. | upstream_code | sjtu_drone_description/include/sjtu_drone_description/plugin_drone_private.h:60-68 |
| The plugin header includes geometry_msgs/Twist and Pose, sensor_msgs/Imu, std_msgs/Empty, Bool, String and Int8, and nav_msgs/Odometry. | upstream_code | sjtu_drone_description/include/sjtu_drone_description/plugin_drone_private.h:27-36 |
| The plugin header defines LANDED_MODEL 0, FLYING_MODEL 1, TAKINGOFF_MODEL 2 and LANDING_MODEL 3. | upstream_code | sjtu_drone_description/include/sjtu_drone_description/plugin_drone_private.h:45-48 |
| InitSubscribers creates a geometry_msgs::msg::Twist subscription on the cmd_vel default with best-effort KeepLast(1) QoS. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:68-73 |
| InitSubscribers creates a std_msgs::msg::Bool subscription on the posctrl default. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:77-80 |
| InitSubscribers creates a std_msgs::msg::Empty subscription on the takeoff default. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:95-99 |
| InitSubscribers creates a std_msgs::msg::Empty subscription on the land default. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:104-108 |
| InitSubscribers creates a std_msgs::msg::Empty subscription on the reset default. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:113-117 |
| InitSubscribers creates a std_msgs::msg::Bool subscription on the dronevel_mode default. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:122-126 |
| InitPublishers creates a geometry_msgs::msg::Pose publisher on the gt_pose default with queue size 1024. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:139-140 |
| InitPublishers creates a geometry_msgs::msg::Twist publisher on the gt_vel default. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:145-146 |
| InitPublishers creates a geometry_msgs::msg::Twist publisher on the gt_acc default. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:151-152 |
| InitPublishers creates a std_msgs::msg::String publisher on the cmd_mode default. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:157-158 |
| InitPublishers creates a std_msgs::msg::Int8 publisher on the state default. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:163-164 |
| The plugin's ROS setup creates only these topic subscriptions and publications; no service or action server is created for flight control or stopping. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:59-174 |
| TakeoffCallback changes LANDED_MODEL to TAKINGOFF_MODEL and resets the command timer; it publishes no acknowledgement. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:288-295 |
| LandCallback changes FLYING_MODEL or TAKINGOFF_MODEL to LANDING_MODEL and resets the command timer; it publishes no acknowledgement. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:301-308 |
| ResetCallback logs and calls Reset(); it returns no response. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:315-319 |
| The private Reset() resets the roll, pitch, yaw and velocity x, y and z PID controllers, sets the link force and torque to zero and resets the cached pose, velocity, angular velocity, acceleration and euler; it does not assign navi_state, cmd_vel, m_posCtrl, m_velMode or the position PID controllers. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:36-56 |
| DroneSimpleController::Reset() only calls the private Reset(). | upstream_code | sjtu_drone_description/src/plugin_drone.cpp:156-159 |
| UpdateDynamics computes the force and torque from the stored cmd_vel: its linear fields are position targets when m_posCtrl is set and navi_state is FLYING_MODEL; in normal control linear.z drives the vertical velocity controller and angular.z the yaw controller in every state. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:488-568 |
| UpdateDynamics adds no force or torque in LANDED_MODEL, the computed force and torque in FLYING_MODEL, 1.5 times them in TAKINGOFF_MODEL and 0.8 times them in LANDING_MODEL. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:573-585 |
| PosCtrlCallback stores the Bool data in m_posCtrl. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:262-265 |
| SwitchModeCallback stores the Bool data in m_velMode and publishes the String 'velocity' or 'position' on cmd_mode. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:328-339 |
| CmdCallback stores the full Twist and adds drift and small-noise offsets to angular x/y/z and linear z. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:227-254 |
| UpdateState changes TAKINGOFF_MODEL to FLYING_MODEL after 0.5 s and LANDING_MODEL to LANDED_MODEL after 1.0 s, then publishes the Int8 navi_state every update. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:395-416 |
| UpdateDynamics reads the Gazebo world pose and publishes that Pose on gt_pose. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:434-450 |
| UpdateDynamics publishes body_vel, computed as pose.Rot().RotateVector(velocity), as the linear part of a Twist on gt_vel. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:453-461 |
| UpdateDynamics publishes body_acc, computed as pose.Rot().RotateVector(acceleration), as the linear part of a Twist on gt_acc. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:454-467 |
| The Python helper publishes Empty, Bool and Twist messages on the private (~/) takeoff, land, reset, posctrl, cmd_vel and dronevel_mode topics. | upstream_code | sjtu_drone_control/sjtu_drone_control/drone_utils/drone_object.py:42-48 |
| The Python move helper documents linear velocity in m/s and angular velocity in rad/s. | upstream_code | sjtu_drone_control/sjtu_drone_control/drone_utils/drone_object.py:200-213 |
| The Python moveTo helper documents x, y and z as metres and publishes them in the cmd_vel Twist linear fields. | upstream_code | sjtu_drone_control/sjtu_drone_control/drone_utils/drone_object.py:215-233 |
| The README lists cmd_vel, land, takeoff, posctrl, dronevel_mode, cmd_mode, state and reset as the control topics, with their ROS message types. | vendor_doc | README.md:35-44 |
| The README lists gt_acc, gt_pose and gt_vel as the ground-truth topic contracts. | vendor_doc | README.md:46-50 |
| The shipped reset_sim.sh helper calls the /reset_world std_srvs/srv/Empty service. | upstream_code | sjtu_drone_bringup/scripts/reset_sim.sh:3 |
| The drone plugin connects its Update to the world-update begin event. | upstream_code | sjtu_drone_description/src/plugin_drone.cpp:134-135 |
| Update returns at once when no simulation time passed, and otherwise runs UpdateState and UpdateDynamics. | upstream_code | sjtu_drone_description/src/plugin_drone.cpp:143-154 |
| In position control, while flying, UpdateDynamics feeds the cmd_vel linear fields to the position controllers as targets. | upstream_code | sjtu_drone_description/src/plugin_drone_private.cpp:492-520 |
| The gazebo launch includes gazebo_ros's gzserver.launch.py with the drone world. | upstream_code | sjtu_drone_bringup/launch/sjtu_drone_gazebo.launch.py:98-105 |
| The bringup launch starts the teleop_joystick node or the keyboard teleop node in the model namespace. | upstream_code | sjtu_drone_bringup/launch/sjtu_drone_bringup.launch.py:27-48 |
| The gazebo_ros init plugin's /reset_world handler resets the world's model entities. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_init.cpp:321-326 |
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

## Scope

The package covers the primary control surface of the pinned Gazebo model plugin: the six command
publications and the `state`, `gt_pose` and `cmd_mode` observations under the shipped `/simple_drone`
namespace. `cmd_vel` is a rosbridge publication and its receipt is only `published: true`,
`confirmed: false`; no topic callback acknowledges takeoff, landing, motion or a control-mode switch.

The plugin has no service or action endpoint for flight control. The shipped `reset_sim.sh` calls the
`/reset_world` `std_srvs/srv/Empty` service, which `gazebo_ros` provides, not this repository. It is not a
stop: the plugin's only reset path, `Reset()`, resets the attitude and velocity PID controllers and the
current force and torque but leaves `navi_state`, the stored `cmd_vel` and the mode flags unchanged, and
`UpdateDynamics` keeps applying thrust from the stored command while the state is flying. The driver
therefore declares `/reset_world` only as an ordinary command (model review 2026-11-04); the e-stop is
the companion world pause (see Safety). `reset` is the plugin's unacknowledged simulation-reset publication, not the MHS
`mhs.safety.reset` operator path.

The `cmd_vel` Twist is overloaded by the plugin. In position-control mode the linear fields are pose
targets (the Python `moveTo` helper documents metres); otherwise they are velocity/tilt/rate values
(the Python `move` helper documents m/s and rad/s). The clone states no numeric input range for either
meaning, so all six components are `Limit.operator_required(...)` and a deployment refuses them until
the operator supplies `site-limits.json`.

Not covered: the front and bottom `sensor_msgs/Image` streams, the IMU/sonar/GPS/odometry topics and
the Python control nodes themselves. The fake claims only the declared topic wire contracts.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS-free scripted contract fake (no Gazebo,
no physics, no captured traffic)`, level F0, determinism `none`, `timestep_ms: 0`, `realtime_factor: 0`,
reset `none`, and no snapshot/restore. The task card prefers the upstream Gazebo simulator, but this
environment cannot build or launch ROS 2 and Gazebo, so the package uses a scripted contract fake and
records the deviation. The fake's state, pose and mode values are placeholders; it records publications
and updates a label, with no takeoff, landing or flight dynamics. It keeps a paused flag that
`/pause_physics` sets and a placeholder simulation time that `/get_model_list` reports and that advances
on every answer unless paused, and silences `state` and `gt_pose` while paused.

## Safety

The device is simulated at R2 (model review 2026-11-05; the author declared R1): cmd_vel, takeoff, land and reset command the vehicle, and REVIEW.md item 12 gives a command on such a topic the robot's hazard however simulated the deployment (a flying vehicle is mobile hardware); the server applies the device risk to every capability. `/reset_world` (gazebo_ros's init plugin, which resets the model entities,
`gazebo_ros_init.cpp:321-326`, a companion citation) is not a stop: the plugin's `Reset()` keeps `navi_state` and the
stored command, so a flying drone keeps flying, and `land` is an unacknowledged publication whose LANDED_MODEL
follows from a 1.0 s timer, not from ground contact.

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
after their timeouts; the device resource reads no topic. The deployment's gazebo_ros, Gazebo and Gazebo 11.15.1 (the clone also builds on Iron and Rolling; this package is pinned to Humble) must be the
pinned releases the companion citations name; rosbridge cannot read their versions. The pause also stops the drone: its plugin runs
`UpdateState` and `UpdateDynamics` only from the world-update event (`plugin_drone.cpp:134-135, 143-154`).

No unpause is offered (the orchestrator's SAFE-042 condition). The plugin keeps its flight state and stored command:
in position control the `cmd_vel` linear fields are position targets (`plugin_drone_private.cpp:492-520`), so a zero
Twist is a flight to the world origin; a take-off in progress continues with 1.5 times the force
(`plugin_drone_private.cpp:573-585`, `UpdateState` 395-416); `CmdCallback` adds drift and small noise to every stored
command (`plugin_drone_private.cpp:227-254`); and the bringup's teleop publishes on the same topics
(`sjtu_drone_bringup.launch.py:27-48`). After `mhs.safety.reset` the world stays paused and the commands still
publish (stored for the next unpause); the operator lands or re-commands the drone and unpauses outside MHS (the
Gazebo GUI play button or `ros2 service call /unpause_physics std_srvs/srv/Empty`). The last cmd_vel left the device
resource (it carries only client publications); it is the explicit read `x-cap.novog93.last_cmd_vel.v1`, and the
cmd_vel receipt reports the six values it sent. The clone exposes no hardware stop path.

## Tags

`ros`, `ros2`, `gazebo`, `simulation`, `quadrotor`, `drone`, `topic-control`

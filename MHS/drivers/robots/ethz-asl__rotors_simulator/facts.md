# Facts and tags for gh.ethz-asl/rotors_simulator

Facts about the package's own surface cite the pinned clone at commit `cd813b7a8c375d677352aa20ad20047feb661126` (`path/in/clone:LINE`). Facts about the stop cite the reviewed companion sources that `task.json` declares (user decision of 2026-11-05; the user's authorisation of 2026-11-05 for the clones fetched under `work/companions`, listed in its `LOCK.json`), written `companion:<alias>/<path>:<LINE>`: `gazebo_ros_pkgs` (gh.ros-simulation/gazebo_ros_pkgs, fetched under work/companions as `ros-simulation__gazebo_ros_pkgs@2.5.21` at `98bb3d0a0afc65725deaa1633e21ff6f5322b564`) and `gazebo_classic` (gh.gazebosim/gazebo-classic, fetched under work/companions as `gazebosim__gazebo-classic@gazebo7_7.16.1` at `6fea5977c4518f6d722855c0e342e1e5acf64bac`). The version evidence that ties this package's stack to those pins is in `task.json` `companions[].version_evidence`; gate G1 re-checks it, and for a fetched companion also its LOCK.json entry, untracked files and write bits. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The README describes RotorS as a MAV Gazebo simulator. | vendor_doc | README.md:4 |
| The README lists a simulated IMU and a generic odometry sensor among the sensors that can be mounted on the multirotor. | vendor_doc | README.md:7 |
| The README states the simulator starts by default in paused mode and documents the Gazebo GUI play button or a rosservice call to gazebo/unpause_physics as the ways to start it. | vendor_doc | README.md:145-150 |
| hovering_example.cpp calls the absolute /gazebo/unpause_physics service with an empty std_srvs::Empty request and retries the call while it returns false. | upstream_code | rotors_gazebo/src/hovering_example.cpp:41-50 |
| After unpausing, hovering_example.cpp waits 5 s and publishes one MultiDOFJointTrajectory waypoint, by default the position (0, 0, 1) with yaw 0. | upstream_code | rotors_gazebo/src/hovering_example.cpp:60-82 |
| The hovering launch defaults mav_name to firefly, starts Gazebo with paused=true, places the spawned MAV and the controller in the firefly namespace, and remaps the controller's odometry topic to odometry_sensor1/odometry. | upstream_code | rotors_gazebo/launch/mav_hovering_example.launch:2-35 |
| The hovering launch includes gazebo_ros's empty_world.launch with its world, paused and gui arguments. | upstream_code | rotors_gazebo/launch/mav_hovering_example.launch:16-22 |
| The hovering launch starts the hovering_example node. | upstream_code | rotors_gazebo/launch/mav_hovering_example.launch:37 |
| spawn_mav.launch defaults namespace to mav_name. | upstream_code | rotors_gazebo/launch/spawn_mav.launch:5 |
| spawn_mav.launch passes namespace into the xacro namespace argument. | upstream_code | rotors_gazebo/launch/spawn_mav.launch:26 |
| GazeboRosInterfacePlugin creates its ROS node handle at the root namespace. | upstream_code | rotors_gazebo_plugins/src/gazebo_ros_interface_plugin.cpp:71-72 |
| GazeboRosInterfacePlugin advertises each connected ROS topic on that root node handle. | upstream_code | rotors_gazebo_plugins/src/gazebo_ros_interface_plugin.cpp:147-148 |
| The generic odometry macro passes the robot namespace and odometry_topic odometry_sensor1/odometry to the odometry plugin. | upstream_code | rotors_description/urdf/mav_generic_odometry_sensor.gazebo:27-35 |
| gazebo_odometry_plugin advertises the Gazebo odometry topic as ~/<namespace>/<odometry topic> and connects the ROS topic <namespace>/<odometry topic>. | upstream_code | rotors_gazebo_plugins/src/gazebo_odometry_plugin.cpp:574-583 |
| gazebo_odometry_plugin connects its OnUpdate to the world-update begin event. | upstream_code | rotors_gazebo_plugins/src/gazebo_odometry_plugin.cpp:231-232 |
| GazeboRosInterfacePlugin converts gz_geometry_msgs::Odometry to nav_msgs::Odometry for the connected ROS odometry topic. | upstream_code | rotors_gazebo_plugins/src/gazebo_ros_interface_plugin.cpp:235-237 |
| The ROS interface plugin includes nav_msgs/Odometry.h. | upstream_code | rotors_gazebo_plugins/include/rotors_gazebo_plugins/gazebo_ros_interface_plugin.h:68 |
| The default IMU macro passes imu_topic imu to the IMU plugin. | upstream_code | rotors_description/urdf/component_snippets.xacro:848-854 |
| gazebo_imu_plugin advertises the Gazebo IMU topic as ~/<namespace>/<imu topic> and connects the ROS topic <namespace>/<imu topic>. | upstream_code | rotors_gazebo_plugins/src/gazebo_imu_plugin.cpp:350-357 |
| GazeboRosInterfacePlugin converts gz_sensor_msgs::Imu to sensor_msgs::Imu for the connected ROS IMU topic. | upstream_code | rotors_gazebo_plugins/src/gazebo_ros_interface_plugin.cpp:203-205 |
| The ROS interface plugin includes sensor_msgs/Imu.h. | upstream_code | rotors_gazebo_plugins/include/rotors_gazebo_plugins/gazebo_ros_interface_plugin.h:71 |
| The motor model connects its OnUpdate to the world-update begin event. | upstream_code | rotors_gazebo_plugins/src/gazebo_motor_model.cpp:202-203 |
| The motor model's OnUpdate computes the sampling time from the simulation time and applies the rotor forces and moments. | upstream_code | rotors_gazebo_plugins/src/gazebo_motor_model.cpp:212-226 |
| For a velocity motor the motor model stores the commanded rotor speed, capped at its maximum, as its reference input. | upstream_code | rotors_gazebo_plugins/src/gazebo_motor_model.cpp:344-348 |
| The lee position controller node sets the first point of a received trajectory as its controller's trajectory point. | upstream_code | rotors_control/src/nodes/lee_position_controller_node.cpp:144-146 |
| The lee position controller node computes rotor velocities and publishes them only from its odometry callback. | upstream_code | rotors_control/src/nodes/lee_position_controller_node.cpp:173-192 |
| The clone's basic world selects the ODE physics engine. | upstream_code | rotors_gazebo/worlds/basic.world:22 |
| The gazebo_ros gzserver wrapper adds libgazebo_ros_api_plugin to the server's plugins unless the arguments already name it. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/scripts/gzserver:20-24 |
| empty_world.launch starts the Gazebo server as the node named gazebo of package gazebo_ros, with the physics engine argument -e $(arg physics). | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:42-44 |
| empty_world.launch defaults its physics argument to ode. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:15 |
| empty_world.launch defaults its gui argument to true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:8 |
| When gui is true, empty_world.launch starts the node gazebo_gui of type gzclient. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:47-50 |
| The API plugin calls ros::init with the node name gazebo when ROS is not initialised yet. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:122-123 |
| The API plugin creates its node handle in the private namespace ~ and advertises its topics and services there. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:141 |
| The API plugin advertises the service pause_physics with the std_srvs::Empty type on its own callback queue gazebo_queue_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:469-475 |
| The API plugin advertises the service get_physics_properties with the gazebo_msgs::GetPhysicsProperties type on gazebo_queue_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:360-366 |
| gazeboQueueThread serves gazebo_queue_ in a loop with a 0.001 s wall-clock wait while the node handle is ok. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:237-244 |
| pausePhysics calls world_->SetPaused(true) and returns true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1692-1696 |
| unpausePhysics calls world_->SetPaused(false) and returns true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1698-1702 |
| getPhysicsProperties sets res.pause to world_->IsPaused(). | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1460 |
| getPhysicsProperties sets success true only when the physics engine type is ode; for any other engine it sets success false and returns false. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1467-1499 |
| The GetPhysicsProperties response field pause is true if the physics engine is paused. | upstream_code | companion:gazebo_ros_pkgs/gazebo_msgs/srv/GetPhysicsProperties.srv:4 |
| Among the world-update begin hooks that its comment says apply forces and publish sim time on /clock, the API plugin connects publishSimTime. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:199-202 |
| World::Step advances simulation time and calls Update only when the world is not paused, a step increment is pending or a reset is due; otherwise it adds the step to the pause time. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:615-634 |
| World::Step holds worldUpdateMutex while it steps the world. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:607 |
| World::SetPaused stores the paused flag under worldUpdateMutex. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1306-1314 |
| World::IsPaused returns the stored paused flag. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1300-1303 |
| World::Update fires the worldUpdateBegin event and then updates every model. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:690-695 |
| World::Step calls ProcessMessages after the paused or unpaused branch, so pending messages are processed on every step, paused or not. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:615-637 |
| A WorldControl message with step calls OnStep, and one with multi_step pauses the world and sets the number of steps to run while paused. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1340-1355 |

## Scope

The package is a configuration-only ROS 1 `RosDriver`; it declares no Python
native class and does not launch or run Gazebo, the controller nodes or the
plugins. The operator runs the pinned RotorS deployment and rosbridge
separately.

The declared endpoints are two subscriptions of the default hovering launch:
`/firefly/odometry_sensor1/odometry` (`nav_msgs/Odometry`) and `/firefly/imu`
(`sensor_msgs/Imu`). The `/firefly` prefix is the launch default: `mav_name`
defaults to `firefly` and the launch group uses `ns="$(arg mav_name)"`. The
plugins build the ROS names as `<robotNamespace>/<configured topic>`. A
deployment that changes `mav_name`, uses another launch or adds a namespace
must expose or remap the same resolved endpoints; that is a deployment
assumption, not an upstream Fact.

The clone itself exposes no ROS pause, reset, step, shutdown or motor command
service; the e-stop is the companion gazebo_ros world pause (see Safety). The
clone's trajectory and motor-speed topics are not declared: they are the
controller's commands, which this package neither sends nor clears.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS-free recording
fake for the Gazebo ROS contract (no physics)`, level F0, determinism `none`,
`timestep_ms: 0` (event-driven replies with no physics step),
`realtime_factor: 0` (not paced), reset `none`, and no snapshot/restore. The
fake starts in a placeholder running state so the observations can be
exercised; the documented upstream default is paused, and that startup sequence
is not modelled as evidence. It keeps a paused flag that the pause sets and the
read-back reports, and silences both topics while it is set. Every odometry,
IMU and service value is a placeholder.

## Safety

The device is simulated at R0: only explicit state observations and the world pause are exposed.

The e-stop is the Gazebo world pause of the simulator's own repository, a reviewed companion fetched at a pinned
commit: `/gazebo/pause_physics` (gazebo_ros 2.5.21, ROS 1 Kinetic; `pausePhysics` calls `World::SetPaused(true)`), confirmed only by
the read-back `/gazebo/get_physics_properties` with `pause == true` (`res.pause = world_->IsPaused()`). A pause that
is not answered, a read-back that fails (a physics engine other than ODE) or `pause` false (another client unpaused
the world) is `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held and a background retry. `World::Step` of Gazebo
7.16.1 advances simulation time and runs the world update only while the world is not paused, a step increment is
pending or a reset is due, so a paused world runs no plugin, controller or sensor update. It is the paused flag, not
a measured standstill: the Gazebo GUI that `empty_world.launch` opens by default, a WorldControl step or multi_step,
or any ROS client can advance or unpause the world, and MHS does not watch the flag after the e-stop. While paused,
the topics published from world updates (and `/clock`) are silent, so their reads fail `NOT_READY` after their
timeouts; the device resource reads no topic. The deployment's gazebo_ros and Gazebo must be the pinned 2.5.21 (Kinetic) and 7.16.1 releases the
companion citations name; rosbridge cannot read their versions.

No unpause is offered (the orchestrator's SAFE-042 condition: an unpause re-enable must not resume a stored motion command). Unpausing resumes the lee position controller's last waypoint (`lee_position_controller_node.cpp:144-146`; by default the hover point `hovering_example` publishes, `hovering_example.cpp:60-82`) and the motor model's last rotor-speed reference (`gazebo_motor_model.cpp:344-348`); this package commands neither, so it cannot clear them first. The earlier `x-cap.ethz-asl.sim_start.v1`, the same unpause, was removed for that reason. After `mhs.safety.reset` the world stays paused; the operator restarts or re-commands the controller and then unpauses outside MHS, with the Gazebo GUI play button or `rosservice call gazebo/unpause_physics` (`README.md:145-150`). This is not a physical emergency stop, no physical device is present, and the package makes no hardware-safety claim.

## Tags

`ros`, `ros1`, `simulation`, `gazebo`, `rotors`, `mav`, `odometry`, `imu`

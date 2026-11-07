# Facts and tags for gh.gsilano/crazys

Facts about the package's own surface cite the pinned clone at commit `c7ee25a7c6f89d41468e33c857ded99f3e804e70` (`path/in/clone:LINE`). Facts about the stop cite the reviewed companion sources that `task.json` declares (user decision of 2026-11-05; the user's authorisation of 2026-11-05 for the clones fetched under `work/companions`, listed in its `LOCK.json`), written `companion:<alias>/<path>:<LINE>`: `gazebo_ros_pkgs` (gh.ros-simulation/gazebo_ros_pkgs, fetched under work/companions as `ros-simulation__gazebo_ros_pkgs@2.5.21` at `98bb3d0a0afc65725deaa1633e21ff6f5322b564`) and `gazebo_classic` (gh.gazebosim/gazebo-classic, fetched under work/companions as `gazebosim__gazebo-classic@gazebo7_7.16.1` at `6fea5977c4518f6d722855c0e342e1e5acf64bac`). The version evidence that ties this package's stack to those pins is in `task.json` `companions[].version_evidence`; gate G1 re-checks it, and for a fetched companion also its LOCK.json entry, untracked files and write bits. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The README says the hovering example publishes the reference on command/trajectory, the position controller reads it with odometry_sensor1/odometry, and the motor speeds go to command/motor_speed. | vendor_doc | README.md:420 |
| The Crazyflie command topic constant is documented as "command/roll_pitch_yawrate_thrust" in the RotorS control common header. | upstream_code | rotors_control/include/rotors_control/common.h:40-42 |
| The Crazyflie roll/pitch/yaw-rate/thrust node subscribes to the command topic with queue size 1 and to odometry with queue size 1. | upstream_code | rotors_control/src/nodes/roll_pitch_yawrate_thrust_crazyflie_node.cpp:35-38 |
| The command message type is mav_msgs/RollPitchYawrateThrustCrazyflie. | upstream_code | rotors_control/src/nodes/roll_pitch_yawrate_thrust_crazyflie_node.h:25 |
| The joystick interface fills the command's roll, pitch, yaw_rate and thrust fields. | upstream_code | rotors_joy_interface/src/joy_crazyflie.cpp:30-36 |
| Joy::StopMav sets roll, pitch, yaw_rate and thrust to zero; it is a local joystick method, not a ROS service or action. | upstream_code | rotors_joy_interface/src/joy_crazyflie.cpp:61-66 |
| The launch file defaults mav_name to crazyflie2. | upstream_code | rotors_gazebo/launch/crazyflie2_with_joy.launch:3 |
| The joystick launch groups the Crazyflie nodes under the mav_name namespace. | upstream_code | rotors_gazebo/launch/crazyflie2_with_joy.launch:29 |
| The launch remaps the controller's odometry to odometry_sensor1/odometry. | upstream_code | rotors_gazebo/launch/crazyflie2_with_joy.launch:45 |
| The generic odometry sensor macro is configured with odometry_topic odometry_sensor1/odometry. | upstream_code | rotors_description/urdf/mav_generic_odometry_sensor.gazebo:35 |
| The odometry type used by the Crazyflie controller is nav_msgs/Odometry. | upstream_code | rotors_control/src/nodes/roll_pitch_yawrate_thrust_crazyflie_node.h:27 |
| hovering_example calls /gazebo/unpause_physics with a std_srvs/Empty request. | upstream_code | rotors_gazebo/src/nodes/hovering_example.cpp:41-42 |
| The rqt_rotors HIL plugin names the MAVROS services /mavros/cmd/arming, /mavros/cmd/command and /mavros/set_mode. | upstream_code | rqt_rotors/src/rqt_rotors/hil_plugin.py:45-47 |
| The HIL plugin creates ServiceProxy clients for the arming, command and set_mode services. | upstream_code | rqt_rotors/src/rqt_rotors/hil_plugin.py:90-92 |
| The HIL plugin's arm button calls the arming service with True. | upstream_code | rqt_rotors/src/rqt_rotors/hil_plugin.py:104-105 |
| The joystick launch fixes paused to true and passes it to the gazebo_ros empty_world launch. | upstream_code | rotors_gazebo/launch/crazyflie2_with_joy.launch:9-26 |
| The joystick launch starts joy_node and rotors_joy_interface_crazyflie in the mav_name group. | upstream_code | rotors_gazebo/launch/crazyflie2_with_joy.launch:39-41 |
| Joy::JoyCallback sets the command fields from the joystick axes and publishes the command on every joystick message. | upstream_code | rotors_joy_interface/src/joy_crazyflie.cpp:68-102 |
| The bag plugin advertises its recording service with GazeboBagPlugin::RecordingServiceCallback. | upstream_code | rotors_gazebo_plugins/src/gazebo_bag_plugin.cpp:111-113 |
| RecordingServiceCallback starts or stops bag recording according to req.record. | upstream_code | rotors_gazebo_plugins/src/gazebo_bag_plugin.cpp:411-431 |
| The octomap plugin advertises a service named world/get_octomap unless the octomapServiceName parameter overrides it. | upstream_code | rotors_gazebo_plugins/src/gazebo_octomap_plugin.cpp:43-52 |
| The octomap service callback builds the octomap and writes it to req.filename when one is given. | upstream_code | rotors_gazebo_plugins/src/gazebo_octomap_plugin.cpp:57-74 |
| The Crazyflie controller returns zero rotor velocities while controller_active_ is false. | upstream_code | rotors_control/src/library/roll_pitch_yawrate_thrust_crazyflie.cpp:65-69 |
| SetRollPitchYawrateThrust stores the command and sets controller_active_ to true. | upstream_code | rotors_control/src/library/roll_pitch_yawrate_thrust_crazyflie.cpp:222-228 |
| The Crazyflie controller clamps each rotor velocity to the range 0 to MAX_PROPELLERS_ANGULAR_VELOCITY. | upstream_code | rotors_control/src/library/roll_pitch_yawrate_thrust_crazyflie.cpp:80-106 |
| The joystick reads max_roll, max_pitch, max_yaw_rate and max_thrust as private parameters with the MAX_ROLL, MAX_PITCH, MAX_YAWRATE and MAX_THRUST defaults. | upstream_code | rotors_joy_interface/src/joy_crazyflie.cpp:47-50 |
| joy_crazyflie.cpp defines MAX_THRUST as 8162.0 with the comment propeller angular velocities [PWM], MAX_ROLL and MAX_PITCH as 30 degrees in radians and MAX_YAWRATE as 200 degrees per second in radians. | upstream_code | rotors_joy_interface/src/joy_crazyflie.cpp:22-25 |
| The Crazyflie node's command callback converts each roll/pitch/yaw-rate/thrust message and passes it to SetRollPitchYawrateThrust. | upstream_code | rotors_control/src/nodes/roll_pitch_yawrate_thrust_crazyflie_node.cpp:93-99 |
| The Crazyflie node computes rotor velocities and publishes them on the actuators topic only from its odometry callback. | upstream_code | rotors_control/src/nodes/roll_pitch_yawrate_thrust_crazyflie_node.cpp:102-126 |
| For each rotor the motor model stores the commanded rotor speed, capped at its maximum, as its reference. | upstream_code | rotors_gazebo_plugins/src/gazebo_motor_model.cpp:237-239 |
| The Crazyflie basic world selects the ODE physics engine. | upstream_code | rotors_gazebo/worlds/basic_crazyflie.world:27 |
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

The package exposes the Crazyflie direct command publication on the resolved
`/crazyflie2/command/roll_pitch_yawrate_thrust` endpoint and one explicit
`nav_msgs/Odometry` observation on `/crazyflie2/odometry_sensor1/odometry`.
The launch files default `mav_name` to `crazyflie2` and put the nodes in that
namespace; a deployment that changes `mav_name` or remaps either topic must
expose the declared absolute endpoints. The relative upstream tokens
`command/roll_pitch_yawrate_thrust` and `odometry_sensor1/odometry` are kept as
`source_name`, not guessed from the operator's graph.

The default `command/trajectory` waypoint path, `command/motor_speed`, the
Gazebo `/gazebo/unpause_physics` call (no unpause is offered; see Safety), TF, IMU,
camera/depth and octomap are NOT COVERED. The direct command is the joystick example's primary flight
interface; a waypoint publication would be another fire-and-forget topic.

## Safety

The vehicle is simulated at risk R2 (integrator v4, 2026-11-05; the author and the model review declared R0).
REVIEW.md item 12 gives a simulator package's command the robot's hazard unless a cited line shows that only the
simulator consumes its topic. The setpoint goes out on the RotorS command topic `command/roll_pitch_yawrate_thrust`
(`rotors_control/include/rotors_control/common.h:40-42`), no fact cites that only a simulator consumes it, and the clone
also ships a hardware-in-the-loop autopilot interface (`rqt_rotors/src/rqt_rotors/hil_plugin.py:45-47, 90-92`); a
flying vehicle is mobile hardware (R2) however simulated the deployment. The command is a topic publication: it is
fire-and-forget and the receipt
reports only that rosbridge accepted the message (`confirmed` is always false) and the four values it sent. It does
not establish execution, target attainment or stopping.

The pinned clone exposes no acknowledged stop of its own. The example nodes call `/gazebo/unpause_physics`
(`hovering_example.cpp:41-42`), which starts physics, and the rqt_rotors HIL plugin creates MAVROS arming, command and
set_mode clients for a hardware-in-the-loop autopilot (`rqt_rotors/src/rqt_rotors/hil_plugin.py:45-47, 90-92`); the
advertised services are the bag recording service (`gazebo_bag_plugin.cpp:111-113, 411-431`) and the
`world/get_octomap` service (`gazebo_octomap_plugin.cpp:43-52, 57-74`); `Joy::StopMav` zeroes a local joystick message
(`joy_crazyflie.cpp:61-66`) and is not a ROS service.

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

No unpause is offered (the orchestrator's SAFE-042 condition). The Crazyflie node passes every command to
`SetRollPitchYawrateThrust` (`roll_pitch_yawrate_thrust_crazyflie_node.cpp:93-99`), which stores it with no timeout
and activates the controller (`roll_pitch_yawrate_thrust_crazyflie.cpp:223-228`); the motor models keep their last
rotor speed (`gazebo_motor_model.cpp:237-239`). The clone states no hover thrust and a zero thrust is not a hold (the
vehicle falls once the world runs), so this package cannot clear the stored command before an unpause. After
`mhs.safety.reset` the world stays paused and commands still publish (the controller stores them for the next
unpause); the operator lands or re-commands the vehicle and unpauses outside MHS, with the Gazebo GUI play button or
`rosservice call gazebo/unpause_physics`.

The four command inputs are `Limit.operator_required` (model review 2026-11-05; the author declared no Limit on these
actuating inputs). The joystick's `max_roll`, `max_pitch`, `max_yaw_rate` and `max_thrust` are private parameters with
the `MAX_*` defaults (`joy_crazyflie.cpp:22-25,47-50`), and the controller clamps its rotor velocities to
0..MAX_PROPELLERS_ANGULAR_VELOCITY (`roll_pitch_yawrate_thrust_crazyflie.cpp:80-106`); neither bounds the command.
Every command is refused with `MHS.SAFETY.LIMITS_UNSET` until an operator installs a reviewed `site-limits.json`;
`site-limits.example.json` is an example overlay for the fake gate only.

The joystick launch fixes `paused` to true (`crazyflie2_with_joy.launch:9-26`) and starts `joy_node` and
`rotors_joy_interface_crazyflie`, which publish on the same command topic on every joystick message
(`crazyflie2_with_joy.launch:39-41`, `joy_crazyflie.cpp:68-102`). The odometry left the device resource: it is
published from the world update and silent while paused, so the resource reads no topic and commands and resets do
not wait for it.

## Fidelity contract

The fake is an analytic, ROS-free transport model, not a recording and not
Gazebo. `driver.py` records engine `analytic:ROS-free transport model (no
physics)`, level F0, determinism `none`, `timestep_ms: 0`, `realtime_factor: 0`
(not paced), reset `none`, and no snapshot/restore. The odometry starts from
placeholder values and shifts by a small placeholder amount proportional to the
command while its paused flag is clear; that is an analytic stand-in, not
physics or simulation time. It keeps a paused flag that the companion pause
sets and the read-back reports, and silences the odometry while it is set. The
gaps disclose the absent dynamics, controller, sensors and ROS graph.

## Tags

`ros`, `ros1`, `simulation`, `gazebo`, `crazyflie`, `uav`, `quadrotor`, `odometry`

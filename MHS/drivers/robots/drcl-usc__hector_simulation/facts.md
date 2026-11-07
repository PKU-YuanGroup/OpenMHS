OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.drcl-usc/hector_simulation

Facts about the package's own surface cite the pinned clone at commit `edfdc7b1a9855c71887ac2cf2ebe0bb5dee5ea49` (`path/in/clone:LINE`). Facts about the stop cite the two reviewed companion sources that `task.json` declares (user decision of 2026-11-05) at their corpus pins, written `companion:<alias>/<path>:<LINE>`: `gazebo_ros_pkgs` (gh.ros-simulation/gazebo_ros_pkgs at `cd9cc952402375be5f274f39b29399c4087aa839`, gazebo_ros 2.9.3 for ROS 1 Noetic) and `gazebo_classic` (gh.gazebosim/gazebo-classic at `b22c6e15e52299865b31093b8feebc9ca19e26e8`, Gazebo 11.15.1). The version evidence that ties this package's stack to those pins is in `task.json` `companions[].version_evidence`; gate G1 re-checks it. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| hector_control initializes ROS with the node name 'hector_control' and the AnonymousName option, and hard-codes the robot name to 'hector'. | upstream_code | Hector_ROS_Simulation/hector_control/src/main.cpp:35-38 |
| CheatIO::initSend advertises ten unitree_legged_msgs/MotorCmd publishers whose names are '/' + _robot_name + '_gazebo/<joint>_controller/command'. | upstream_code | Hector_ROS_Simulation/hector_control/src/interface/CheatIO.cpp:77-88 |
| CheatIO::sendCmd sets every MotorCmd.mode to 0x0A and copies q, dq, tau, Kd and Kp before publishing each of the ten messages. | upstream_code | Hector_ROS_Simulation/hector_control/src/interface/CheatIO.cpp:44-58 |
| UnitreeJointController::init subscribes to the relative literal 'command' and publishes unitree_legged_msgs/MotorState on name_space + '/state'. | upstream_code | Hector_ROS_Simulation/unitree_ros/unitree_legged_control/src/joint_controller.cpp:88-95 |
| The joint controller includes unitree_legged_msgs/MotorCmd.h and MotorState.h. | upstream_code | Hector_ROS_Simulation/unitree_ros/unitree_legged_control/include/joint_controller.h:21-22 |
| UnitreeJointController::update applies the received q/Kp, dq/Kd and tau when mode is PMSM; while mode is BRAKE it sets zero position stiffness, zero velocity, damping 20 and zero torque. | upstream_code | Hector_ROS_Simulation/unitree_ros/unitree_legged_control/src/joint_controller.cpp:135-164 |
| UnitreeJointController::stopping is an empty function. | upstream_code | Hector_ROS_Simulation/unitree_ros/unitree_legged_control/src/joint_controller.cpp:207-208 |
| main.cpp's ShutDown handler prints 'stop' and sets the global running flag to false. | upstream_code | Hector_ROS_Simulation/hector_control/src/main.cpp:14-20 |
| CheatIO subscribes to the absolute /gazebo/model_states topic with a queue size of 1. | upstream_code | Hector_ROS_Simulation/hector_control/src/interface/CheatIO.cpp:91 |
| CheatIO.h includes gazebo_msgs/ModelStates.h, the declared message type of /gazebo/model_states. | upstream_code | Hector_ROS_Simulation/hector_control/include/interface/CheatIO.h:12 |
| CheatIO::StateCallback selects the model named '<robot_name>_gazebo' and copies its pose and twist into the controller's cheated high state. | upstream_code | Hector_ROS_Simulation/hector_control/src/interface/CheatIO.cpp:104-126 |
| biped.launch starts the ten named joint controllers inside controller_manager with ns='/hector_gazebo'. | upstream_code | Hector_ROS_Simulation/unitree_ros/unitree_gazebo/launch/biped.launch:46-51 |
| biped.launch leaves the unitree_gazebo servo node commented out. | upstream_code | Hector_ROS_Simulation/unitree_ros/unitree_gazebo/launch/biped.launch:60 |
| The README tells the operator to launch biped.launch, run 'rosrun hector_control hector_ctrl' and click the simulator's start button, and, when the controller does not start, to terminate it, pause and reset the simulator (ctrl + R) and rerun it. | vendor_doc | Readme.md:61-68 |
| The shipped xacro sets hip_max 45, hip_min -45, hip_velocity_max 21 and hip_torque_max 33.5. | upstream_code | Hector_ROS_Simulation/hector_description/xacro/const.xacro:37-40 |
| The shipped xacro sets hip2_max 45, hip2_min -45, hip2_velocity_max 21 and hip2_torque_max 33.5. | upstream_code | Hector_ROS_Simulation/hector_description/xacro/const.xacro:84-87 |
| The shipped xacro sets thigh_max 100, thigh_min -100, thigh_velocity_max 21 and thigh_torque_max 33.5. | upstream_code | Hector_ROS_Simulation/hector_description/xacro/const.xacro:123-126 |
| The shipped xacro sets calf_max 100, calf_min -100, calf_velocity_max 14 and calf_torque_max 67. | upstream_code | Hector_ROS_Simulation/hector_description/xacro/const.xacro:185-188 |
| The shipped xacro sets toe_max 100, toe_min -100, toe_velocity_max 21 and toe_torque_max 33.5. | upstream_code | Hector_ROS_Simulation/hector_description/xacro/const.xacro:213-216 |
| leg.xacro passes hip_torque_max and hip_velocity_max unchanged to the URDF limit's effort and velocity attributes and converts hip_min and hip_max with PI/180 for its lower and upper attributes. | upstream_code | Hector_ROS_Simulation/hector_description/xacro/leg.xacro:16 |
| positionLimits clamps a revolute or prismatic joint's commanded position to the URDF lower and upper limits, velocityLimits its velocity to plus or minus the URDF velocity limit, and effortLimits its torque to plus or minus the URDF effort limit. | upstream_code | Hector_ROS_Simulation/unitree_ros/unitree_legged_control/src/joint_controller.cpp:210-226 |
| runFSMController runs the FSM controller in a loop paced by ros::Rate(1000) while the running flag is true. | upstream_code | Hector_ROS_Simulation/hector_control/src/main.cpp:22-30 |
| biped.launch declares the paused argument with default true and passes it to gazebo_ros's empty_world.launch. | upstream_code | Hector_ROS_Simulation/unitree_ros/unitree_gazebo/launch/biped.launch:7-19 |
| The repository is licensed under the BSD 3-Clause license. | vendor_doc | License.md:1-4 |
| The vendored unitree_legged_control joint controller states that it is Unitree Robotics code governed by the MPL-2.0 license. | upstream_code | Hector_ROS_Simulation/unitree_ros/unitree_legged_control/src/joint_controller.cpp:1-4 |
| gazebo.xacro loads the gazebo_ros_control plugin libgazebo_ros_control.so with robotNamespace /hector_gazebo. | upstream_code | Hector_ROS_Simulation/hector_description/xacro/gazebo.xacro:4-8 |
| UnitreeJointController::setCommandCB copies mode, q, Kp, dq, Kd and tau of the received MotorCmd into lastCmd and writes it to the realtime command buffer. | upstream_code | Hector_ROS_Simulation/unitree_ros/unitree_legged_control/src/joint_controller.cpp:33-45 |
| joint_controller.h defines PMSM as 0x0A and BRAKE as 0x00. | upstream_code | Hector_ROS_Simulation/unitree_ros/unitree_legged_control/include/joint_controller.h:26-27 |
| biped.launch includes gazebo_ros's empty_world.launch. | upstream_code | Hector_ROS_Simulation/unitree_ros/unitree_gazebo/launch/biped.launch:15 |
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
| GazeboRosControlPlugin connects its Update method to the world-update begin event. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros_control/src/gazebo_ros_control_plugin.cpp:196-199 |
| GazeboRosControlPlugin::Update reads the simulated robot state, runs the controller manager update and writes the resulting commands to the Gazebo model. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros_control/src/gazebo_ros_control_plugin.cpp:211-258 |
| The API plugin advertises the model_states topic (gazebo_msgs::ModelStates) with onModelStatesConnect as its connect callback. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:400-407 |
| When the first subscriber of the model states connects, the API plugin connects publishModelStates to the world-update begin event. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:571-576 |

## Scope

The package binds the ten `unitree_legged_msgs/MotorCmd` publications that
`CheatIO` uses for the active HECTOR joint controllers and the
`/gazebo/model_states` observation. The command topics are the controller's
relative `command` subscriptions (`joint_controller.cpp:90`) resolved in the
`/hector_gazebo` controller namespace named by `biped.launch:47-51`; the
absolute endpoints are therefore deployment assumptions for that shipped
namespace. The clone constructs the per-joint `MotorState` names at run time as
`name_space + "/state"` (`joint_controller.cpp:94-95`) and has no quoted
absolute literal for them, so this package does not bind those state topics.
The `CheatIO` model-state read returns every `/gazebo/model_states` entry; the
caller selects the `hector_gazebo` entry by name, as `CheatIO.cpp:104-126` does.

The optional `unitree_gazebo/servo` node, the unused `HighLevelIO` class and the
keyboard teleoperation in `hector_control` are outside this declaration. The
README's pause/reset are manual GUI actions, not ROS endpoints in the clone; the
stop below uses the companion gazebo_ros services instead. The device resource
reads no topic: `/gazebo/model_states` is published only while the world runs, so
it is the explicit read capability, and a MotorCmd receipt reports the five values
it sent (the transmitted request, not a measurement).

## Safety

The clone registers no ROS service or action that stops the joint controllers.
`UnitreeJointController::stopping()` is empty, `hector_control` handles only a
local SIGINT, and the only alternative command shape is another unacknowledged
`MotorCmd` publication (`BRAKE` at `joint_controller.cpp:158-164`). The e-stop is
therefore the companion Gazebo world pause (next section). While the world is
paused, gazebo_ros_control runs neither the controller manager update nor the
torque write, so the ten controllers apply no torque. Each controller keeps the
last `MotorCmd` it stored (`setCommandCB`, `joint_controller.cpp:33-45`; applied
in `update`, `139-185`), including one received during the pause. No unpause is
offered. The package cannot clear that command first: `BRAKE` (`158-164`) sets
zero position stiffness, zero velocity, damping 20 and zero torque, so it removes
the position stiffness and applies damping only; a `PMSM` command sets the
position it names (`142-145`) and the package reads no joint position;
`starting()` (`117-129`) holds the current position, but gazebo_ros_control runs
the controller manager only from the world update
(`gazebo_ros_control_plugin.cpp:196-199, 251`), which a paused world does not
run; and `hector_ctrl`, when it runs, republishes all ten `MotorCmd` messages
from the main loop (`main.cpp:80-83` calls `CheatIO::sendRecv`; `CheatIO.cpp:44-58`
publishes them and forces mode `0x0A`). The FSM loop (`main.cpp:22-30`) is a
different thread. A Gazebo world reset clears timing only
(`GazeboRosControlPlugin::Reset`, `260-266`), not `lastCmd`. The constructor
zeros `lastCmd` (`joint_controller.cpp:15-18`) and `biped.launch` starts the
world paused (`biped.launch:7`), so the stopped state is also the start state of
a fresh launch. After `mhs.safety.reset` the world stays paused. The operator
recovers outside MHS: stop `hector_ctrl` (`signal(SIGINT, ShutDown)` at
`main.cpp:78` and `ShutDown` at `16-20` set `running` false; the README's
`ctrl+\` at `Readme.md:68` is SIGQUIT and is not that handler), relaunch
`biped.launch`, then press the simulator start button (`Readme.md:67`). The
declared risk is R2
because the command surface can drive a powered biped's joints.

## Stop and read-back

The clone registers no stop service. The stop is the Gazebo world pause served by the companion gazebo_ros API
plugin, which gazebo_ros's `gzserver` wrapper loads into the server that this clone's launch starts through
`empty_world.launch`:

- e-stop: `/gazebo/pause_physics` (`std_srvs/Empty`): `pausePhysics` calls `World::SetPaused(true)`;
- read-back (`safety_bindings.safe_state`): `/gazebo/get_physics_properties`; the e-stop is confirmed only when its
  `pause` field (`res.pause = world_->IsPaused()`) is true. A failed pause, a failed read-back (a physics engine other
  than ODE makes the service return false) or a read-back with `pause` false (another client or the GUI unpaused the
  world) gives `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held and a background retry;
- no re-enable and no ordinary unpause. `mhs.safety.reset` only releases the latch; the world stays paused. The
  earlier `x-cap.drcl-usc.resume.v1` was removed (SAFE-042). The operator recovers outside MHS as the Safety
  section states.

What the pause does and does not do (Gazebo classic 11): `World::Step` updates the world only while it is not paused
(or a step is pending or a reset is due), so no model update and no `worldUpdateBegin` callback runs, and gazebo_ros
publishes no `/clock`. It is the paused flag, not a measured standstill. It does not stop: callbacks that store
commands (they act again when the world runs); pending spawn and delete messages, which every step processes; a GUI
step or a WorldControl `multi_step`, which advances the paused world; and any client or the Gazebo GUI, which can
unpause it. MHS does not watch the flag after the e-stop. The pause runs on gazebo_ros's own callback queue, one
request at a time, with the other world services. The deployment's gazebo_ros and Gazebo must be the pinned 2.9.3
(Noetic) and 11 releases; rosbridge cannot read their versions, and on a graph without gazebo_ros neither service
exists and the e-stop fails with the latch held.

## Limits

The position bounds are the shipped xacro configuration values in degrees
(`*_max` and `*_min`), which `leg.xacro` converts with `PI/180` for the URDF
revolute limits; they are not universal hardware bounds. The velocity and torque
inputs are `operator_required` (reviewer correction): the xacro's `*_velocity_max`
and `*_torque_max` reach the URDF `velocity` and `effort` attributes unconverted,
the joint controller clamps `dq` and `tau` to plus or minus those values
(`joint_controller.cpp:149-156, 216-226`), so the velocity value is in the unit of
`dq` (rad/s), not deg/s as the author's bound assumed, and the clone shows no
negative number for either. The stiffness (`Kp`) and damping (`Kd`) inputs are
`operator_required`: the walking controller computes them and the clone states
no numeric bound. `site-limits.example.json` is an illustrative operator overlay
for these four inputs; it is not a fact and it is not applied automatically.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS-free protocol fake
(no Gazebo physics)`, level F0, determinism `none`, `timestep_ms: 0`,
`realtime_factor: 0`, reset `none`, and no snapshot/restore. The fake returns
canned `ModelStates` placeholders and a placeholder pose nudge after a command,
and keeps a paused flag that the pause service sets and the read-back reports. It
does not serve `/gazebo/unpause_physics`. While the flag is set it publishes no
`ModelStates` and only stores a `MotorCmd`. Its GetPhysicsProperties numbers are
placeholders. It runs no Gazebo
world, physics step, controller loop or sensor. The package does not claim that a
publication moved the robot.

## Tags

`ros`, `ros1`, `gazebo`, `simulation`, `humanoid`, `biped`, `hector`,
`joint-command`

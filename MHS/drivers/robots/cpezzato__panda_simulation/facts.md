OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.cpezzato/panda_simulation

Facts about the package's own surface cite the pinned clone at commit
`58e1675a372bfef5a30b4dfd6bd5c898f8c012c9` (`path/in/clone:LINE`). Facts about
the stop cite the reviewed companion sources that `task.json` declares (user
decision of 2026-11-05; the user's authorisation of 2026-11-05 for the clones
fetched under `work/companions`, listed in its `LOCK.json`), written
`companion:<alias>/<path>:<LINE>`: `gazebo_ros_pkgs`
(gh.ros-simulation/gazebo_ros_pkgs, fetched under work/companions as
`ros-simulation__gazebo_ros_pkgs@2.5.21` at
`98bb3d0a0afc65725deaa1633e21ff6f5322b564`) and `gazebo_classic`
(gh.gazebosim/gazebo-classic, fetched under work/companions as
`gazebosim__gazebo-classic@gazebo7_7.16.1` at
`6fea5977c4518f6d722855c0e342e1e5acf64bac`). The version evidence that ties
this package's stack to those pins is in `task.json`
`companions[].version_evidence`; gate G1 re-checks it, and for a fetched
companion also its LOCK.json entry, untracked files and write bits. The README
names `ros-kinetic-desktop-full` (README.md:41) and also says ROS Melodic with
Gazebo 9 can be used (README.md:73). This package serves only the Kinetic pin
above. The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The README states that the launch file starts a Gazebo simulation in pause with a single robot, runs the panda_control_AIC node by default, and the operator presses play. | vendor_doc | README.md:66 |
| The README's installation asks for ros-kinetic-desktop-full. | vendor_doc | README.md:41 |
| The README sources /opt/ros/kinetic/setup.bash inside the container image. | vendor_doc | README.md:54 |
| The README's troubleshooting says that with ROS Melodic and Gazebo 9 the robot meshes will probably not be shown and tells the user to remove the transparent attribute in the visual .dae files. | vendor_doc | README.md:73 |
| simulation.launch declares the paused argument with default true and passes it to the gazebo_ros empty_world launch. | upstream_code | panda_simulation/launch/simulation.launch:5-19 |
| simulation.launch declares use_sim_time with default true and passes it to the gazebo_ros empty_world launch. | upstream_code | panda_simulation/launch/simulation.launch:6-17 |
| simulation.launch loads the robot description under /robot1 and spawns the joint_state_controller plus one effort controller for each of the seven panda joints. | upstream_code | panda_simulation/launch/simulation.launch:23-43 |
| simulation.launch starts the panda_control_AIC node without a namespace and leaves the MRAC node commented out. | upstream_code | panda_simulation/launch/simulation.launch:49-51 |
| panda_control.yaml configures joint_state_controller as joint_state_controller/JointStateController with publish_rate 1000. | upstream_code | panda_simulation/config/panda_control.yaml:2-4 |
| panda_control.yaml configures panda_joint1 through panda_joint7 each as an effort_controllers/JointEffortController on that joint. | upstream_code | panda_simulation/config/panda_control.yaml:6-37 |
| panda_arm_world.urdf.xacro instantiates panda_arm and the gazebo and transmission macros, and the hand instantiation is commented out. | upstream_code | franka_description/robots/panda_arm_world.urdf.xacro:25-30 |
| The panda_arm macro declares ${arm_id}_joint8 as revolute with effort 1, lower 0 and upper 0.1. | upstream_code | franka_description/robots/panda_arm.xacro:269-276 |
| The panda transmission macro loads the gazebo_ros_control plugin from libgazebo_ros_control.so. | upstream_code | franka_description/robots/panda.transmission.xacro:7-11 |
| The panda transmission macro declares hardware_interface/EffortJointInterface transmissions for joint1 through joint8. | upstream_code | franka_description/robots/panda.transmission.xacro:14-100 |
| The AIC constructor creates seven absolute std_msgs/Float64 publishers named /robot1/panda_joint1..7_controller/command, subscribes to /robot1/joint_states, and also creates publishers for panda_free_energy and the controller's belief and sensory-error topics; it creates no service server. | upstream_code | panda_control/src/classes/AIC.cpp:15-42 |
| The AIC constructor subscribes to the absolute /robot1/joint_states and passes AIC::jointStatesCallback as its handler. | upstream_code | panda_control/src/classes/AIC.cpp:25 |
| AIC.h includes sensor_msgs/JointState.h, which declares the type used by the joint-state subscription. | upstream_code | panda_control/include/AIC.h:23 |
| AIC::jointStatesCallback copies position[i] and velocity[i] for i from 0 to 6 without reading the joint names. | upstream_code | panda_control/src/classes/AIC.cpp:45-51 |
| AIC::computeActions computes one torque per joint and publishes the seven values through tauPub1 to tauPub7. | upstream_code | panda_control/src/classes/AIC.cpp:152-162 |
| AIC::computeActions updates the torque vector u from its previous value by a gradient step on the position and velocity errors. | upstream_code | panda_control/src/classes/AIC.cpp:153-154 |
| AIC::minimiseF calls computeActions, then publishes the free-energy scalar through IFE_pub and the sensory prediction error and belief arrays. | upstream_code | panda_control/src/classes/AIC.cpp:137-149 |
| The AIC main loop runs at ros::Rate(1000), calls minimiseF while the node is alive, and cycles between hardcoded desired joint positions every 6000 cycles; it has no service, action, cancellation or reset path. | upstream_code | panda_control/src/AIC_controller.cpp:61-92 |
| The AIC desired joint positions are hardcoded in main and are not read from a parameter, topic or service. | upstream_code | panda_control/src/AIC_controller.cpp:29-59 |
| The Panda arm xacro states effort 87 on the joint1, joint2, joint3 and joint4 limit lines and effort 12 on the joint5, joint6 and joint7 limit lines. | upstream_code | franka_description/robots/panda_arm.xacro:103-259 |
| The gazebo_ros gzserver wrapper adds libgazebo_ros_api_plugin to the server's plugins unless the arguments already name it. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/scripts/gzserver:20-24 |
| empty_world.launch starts the Gazebo server as the node named gazebo of package gazebo_ros, with the physics engine argument -e $(arg physics). | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:42-44 |
| empty_world.launch defaults its physics argument to ode. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:15 |
| empty_world.launch defaults its gui argument to true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:8 |
| When gui is true, empty_world.launch starts the node gazebo_gui of type gzclient. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:47-50 |
| empty_world.launch passes -u to the server when its paused argument is true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:29-30 |
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
| gazebo_ros_control connects its Update to the world-update begin event. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros_control/src/gazebo_ros_control_plugin.cpp:208-211 |
| gazebo_ros_control's Update reads the simulation time, updates the controllers and writes their commands to the simulated joints. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros_control/src/gazebo_ros_control_plugin.cpp:223-270 |
| World::Step advances simulation time and calls Update only when the world is not paused, a step increment is pending or a reset is due; otherwise it adds the step to the pause time. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:615-634 |
| World::Step holds worldUpdateMutex while it steps the world. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:607 |
| World::SetPaused stores the paused flag under worldUpdateMutex. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1306-1314 |
| World::IsPaused returns the stored paused flag. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1300-1303 |
| World::Update fires the worldUpdateBegin event and then updates every model. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:690-695 |
| World::Step calls ProcessMessages after the paused or unpaused branch, so pending messages are processed on every step, paused or not. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:615-637 |
| A WorldControl message with step calls OnStep, and one with multi_step pauses the world and sets the number of steps to run while paused. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1340-1355 |

## Scope

The package binds the absolute `/robot1/joint_states` observation
(`sensor_msgs/JointState`), the AIC's relative `panda_free_energy` observation
(`std_msgs/Float64`) and seven absolute effort publications on
`/robot1/panda_joint1..7_controller/command` (`std_msgs/Float64`). The
observations are explicit subscribe actions, so the empty resource snapshot
never waits for a sample. Each effort receipt reports the value handed to
rosbridge (`sent_effort`), which is the transmitted request and not a measured
torque. The joint-state output carries the ROS 1 `std_msgs/Header`
(`seq`, `stamp.secs/nsecs`, `frame_id`) with the four arrays.

The launch includes gazebo_ros `empty_world.launch` (simulation.launch:13-19)
with `paused` default true and `use_sim_time` default true, and starts
`panda_control_AIC`. The shipped description comments out the hand
instantiation. The `panda_arm` macro still declares `${arm_id}_joint8`
(`panda_arm.xacro:269-276`, revolute, effort 1, range 0 to 0.1). The AIC
callback reads indices 0 through 6. The transmission macro still declares
`${robot_name}_joint8`. A deployment that adds the hand or namespaces the
nodes must expose the corresponding resolved endpoints.

## Safety

The device is simulated but publishes joint effort commands, so `risk` is R2
(REVIEW.md item 12). The pinned clone advertises no service that stops the AIC
loop. The e-stop is the companion gazebo_ros service `/gazebo/pause_physics`
(`std_srvs/Empty`), confirmed only when `/gazebo/get_physics_properties` reads
`pause` true (`gazebo_ros_api_plugin.cpp:1460`, `res.pause = world_->IsPaused()`).
`World::Step` still updates when the paused flag is clear, a step is pending
or a reset is due (`World.cc:615-617`). Otherwise gazebo_ros_control updates no
controller and writes no effort. The read-back is the paused flag, not a
measured standstill.

No unpause is offered. Stopping `panda_control_AIC` does not clear retained
`joint_effort_command_` (`default_robot_hw_sim.cpp:315-316` applies the last
command on the next update unless `e_stop_active_`) or the AIC torque state
`u`. `AIC::~AIC` is empty (`AIC.cpp:43`) and main returns without clearing
state (`AIC_controller.cpp:93`). Each cycle updates `u` from its previous value
(`AIC.cpp:154`) and publishes it (`AIC.cpp:157-162`) at `ros::Rate(1000)`
(`AIC_controller.cpp:62`). The package cannot clear that state, so an external
unpause would resume stored motion (SAFE-042). The world stays paused until an
operator-reviewed procedure has independently verified that those retained
controller commands are cleared or reinitialized. This package does not provide
that procedure. After `mhs.safety.reset` the latch releases and the world stays
paused. The GUI, a WorldControl message or any other client can unpause or step
the world. `safety_status` returns the cached confirmation and does not call
`get_physics_properties` again, so it cannot detect that external unpause or
step.

While the world is paused and no step or reset is pending, `/robot1/joint_states`
and `/clock` are silent, and the joint-state read fails at its 2 s timeout.
The fake still answers `/panda_free_energy` while paused. A live free-energy
read while `/clock` is silent is unverified. The device resource reads no
topic. The read-back returns false for a physics engine other than ODE
(empty_world.launch defaults to ode), and the e-stop then stays unconfirmed
with the latch held. The README's Melodic and Gazebo 9 note is a deployment
this package does not serve.

## Limits

The xacro limit lines state an unsigned effort attribute (87 for joints 1-4,
12 for joints 5-7; `franka_description/robots/panda_arm.xacro:103-259`) and no
signed command bound, so they cannot source a -87..87 or -12..12 envelope.
Every effort input is `Limit.operator_required`, and every effort call is
refused with `MHS.SAFETY.LIMITS_UNSET` until an operator installs a reviewed
`site-limits.json`. `site-limits.example.json` (-1..1 N.m per joint) is an
example overlay for the fake gate only, not a fact or a device bound.

## Tags

`ros`, `ros1`, `gazebo`, `simulation`, `panda`, `franka`, `active-inference`,
`joint-state`, `effort`, `stop`

# Facts and tags for gh.evronix/quadruped_sim2sim

Facts about the package's own surface cite the pinned clone at commit `99040173a6ec16efb56e236d57fd088fdd61484a` (`path/in/clone:LINE`). Facts about the stop cite the reviewed companion sources that `task.json` declares (user decision of 2026-11-05; the user's authorisation of 2026-11-05 for the clones fetched under `work/companions`, listed in its `LOCK.json`), written `companion:<alias>/<path>:<LINE>`: `gazebo_ros_pkgs` (gh.ros-simulation/gazebo_ros_pkgs, fetched under work/companions as `ros-simulation__gazebo_ros_pkgs@3.9.0` at `ae6e5793a31f5927df89cb58007d2a5eb567baa8`), `gazebo_ros2_control` (gh.ros-controls/gazebo_ros2_control, fetched under work/companions as `ros-controls__gazebo_ros2_control@0.4.12` at `42d875b482f0b254d9032950a91b2c5cbd7d1c3d`) and `gazebo_classic` (gh.gazebosim/gazebo-classic, the corpus clone at `b22c6e15e52299865b31093b8feebc9ca19e26e8`). The version evidence that ties this package's stack to those pins is in `task.json` `companions[].version_evidence`; gate G1 re-checks it, and for a fetched companion also its LOCK.json entry, untracked files and write bits. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Scope recon

The repository is a ROS 2 (rclpy) sim-to-sim pipeline, not a Python object API and not a Gymnasium environment. The
three policy controllers (`load_dreamwaq_policy.py`, `load_him_policy.py`, `load_wtw_policy.py`) share this runtime
interface:

| direction | native operation | endpoint | type | source |
|---|---|---|---|---|
| in | subscribe | `/robot_velocity_command` | `geometry_msgs/msg/PoseStamped` | `robot_controller/robot_controller/load_dreamwaq_policy.py:168-170`, import at `:7` |
| in | subscribe | `/imu_plugin/out` | `sensor_msgs/msg/Imu` | `robot_controller/robot_controller/load_dreamwaq_policy.py:176-178`, import at `:8` |
| in | subscribe | `/joint_states` | `sensor_msgs/msg/JointState` | `robot_controller/robot_controller/load_dreamwaq_policy.py:179-181`, import at `:8` |
| out | publish | `/joint_effort_controller/commands` | `std_msgs/msg/Float64MultiArray` | `robot_controller/robot_controller/load_dreamwaq_policy.py:171-173`, import at `:9` |
| out | publish | `/policy` (DreamWaQ only) | `std_msgs/msg/Float64MultiArray` | `robot_controller/robot_controller/load_dreamwaq_policy.py:174`, import at `:9` |

The velocity callback copies `pose.position.x`, `pose.position.y` and `pose.position.z` into the command vector
(`load_dreamwaq_policy.py:185-189`). HIM's callback comment names the same three values x, y and yaw
(`load_him_policy.py:215-219`), and its observation builder labels the scales lin_vel, lin_vel and ang_vel
(`load_him_policy.py:250-253`). The UI labels the wire fields X Velocity, Y Velocity and Angular Z Velocity
(`robot_UI/robot_UI/submodule/robot_UI.py:81-93`). The clone states no numeric velocity envelope: the text fields
accept arbitrary floats and the joystick scale is UI scaling, so the driver marks all three inputs
`operator_required` rather than inventing a bound.

The joint-state callbacks consume at least 12 positions and reorder 12 indices
(`load_dreamwaq_policy.py:201-214`; `load_him_policy.py:231-245`; `load_wtw_policy.py:126-134`). The wire arrays are
returned in the publisher's order with their names; this driver does not apply the policy's private remapping.

## Stop, reset and safety path

The device is simulated at risk R2 (integrator v4, 2026-11-05; the author and the model review declared R0). REVIEW.md
item 12 gives a simulator package's command the robot's hazard unless a cited line shows that only the simulator
consumes its topic. The velocity setpoint on `/robot_velocity_command` feeds the learned policy nodes, which publish
joint efforts to a ros2_control `JointGroupEffortController` (`load_dreamwaq_policy.py:168-182`,
`robot_gazebo/config/go1_ros_control.yaml:1-10, 31-53`), the controller a real robot's ros2_control hardware would serve
as well; the only line about real robots says their integration is "Coming soon..." (`README.md:113-115`), which is not
a citation that the topic is simulator-only. A legged robot is R2 however simulated the deployment; the command
capability is R2 too.

The three controller constructors register subscriptions, publishers and a timer only; none declares a ROS service,
ROS action, stop call or reset call (`load_dreamwaq_policy.py:168-182`, `load_him_policy.py:200-211`,
`load_wtw_policy.py:103-113`). The clone's Real Robot Integration section is still "Coming soon..."
(`README.md:113-115`).

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

No unpause is offered (the orchestrator's SAFE-042 condition). The policy node keeps its last setpoint, which starts
at a non-zero 0.15 (`load_dreamwaq_policy.py:167`), and publishes joint efforts every 5 ms
(`load_dreamwaq_policy.py:182, 230-270`); the README starts it with `ros2 run` and no parameter
(`README.md:86-90`), so its timer runs on the system clock through the pause on stale joint and IMU samples, and a
learned policy at a zero setpoint still drives the legs. The package cannot clear what the legs do when the world
resumes. After `mhs.safety.reset` the world stays paused; the operator stops the policy node and unpauses outside MHS
(the Gazebo GUI play button or `ros2 service call /unpause_physics std_srvs/srv/Empty`). No physical stop is
claimed.

## Facts

| fact | source | ref |
|---|---|---|
| README describes the repository as a Sim2Sim pipeline for RL quadruped policies in ROS 2 Gazebo. | vendor_doc | README.md:9 |
| README says the stack is tested on ROS 2 Humble and Ubuntu 22.04. | vendor_doc | README.md:41 |
| README lists the Gazebo launch, three policy controller executables and the UI executable. | vendor_doc | README.md:74-101 |
| README says the UI controls the robot's command_velocity interactively. | vendor_doc | README.md:104 |
| DreamWaQ creates a PoseStamped subscription on /robot_velocity_command with queue depth 10. | upstream_code | robot_controller/robot_controller/load_dreamwaq_policy.py:168-170 |
| DreamWaQ imports PoseStamped from geometry_msgs.msg. | upstream_code | robot_controller/robot_controller/load_dreamwaq_policy.py:7 |
| DreamWaQ's velocity callback copies pose.position x, y and z into the command vector. | upstream_code | robot_controller/robot_controller/load_dreamwaq_policy.py:185-189 |
| DreamWaQ creates Float64MultiArray publishers on /joint_effort_controller/commands and /policy. | upstream_code | robot_controller/robot_controller/load_dreamwaq_policy.py:171-174 |
| DreamWaQ subscribes to Imu on /imu_plugin/out and JointState on /joint_states. | upstream_code | robot_controller/robot_controller/load_dreamwaq_policy.py:176-181 |
| DreamWaQ imports Imu and JointState from sensor_msgs.msg. | upstream_code | robot_controller/robot_controller/load_dreamwaq_policy.py:8 |
| DreamWaQ's joint-state callback requires at least 12 positions and reorders 12 indices; the controller does not verify the attached joint names. | upstream_code | robot_controller/robot_controller/load_dreamwaq_policy.py:201-214 |
| DreamWaQ runs a 0.005 s timer and its comment labels the policy dt 0.02 and the PD controller dt 0.005. | upstream_code | robot_controller/robot_controller/load_dreamwaq_policy.py:182 |
| HIM's command callback comment names x, y and yaw. | upstream_code | robot_controller/robot_controller/load_him_policy.py:215-219 |
| HIM's observation builder comments the three command scales as lin_vel, lin_vel and ang_vel. | upstream_code | robot_controller/robot_controller/load_him_policy.py:250-253 |
| Walk-These-Ways creates the same PoseStamped, Imu, JointState, effort publisher and timer interface. | upstream_code | robot_controller/robot_controller/load_wtw_policy.py:103-113 |
| Walk-These-Ways clips policy actions to 10, scales by 0.25, reduces hip entries by 0.5 and uses proportional 20 and derivative 0.5 gains. | upstream_code | robot_controller/robot_controller/load_wtw_policy.py:175-183 |
| HIM clips the computed torque command to -80 and 80. | upstream_code | robot_controller/robot_controller/load_him_policy.py:321-322 |
| The Gazebo controller manager runs at 1000 Hz and declares a joint_state_broadcaster plus an effort_controllers/JointGroupEffortController. | upstream_code | robot_gazebo/config/go1_ros_control.yaml:1-10 |
| The effort controller lists the FL, FR, RL and RR hip, thigh and calf joints and uses the effort command interface. | upstream_code | robot_gazebo/config/go1_ros_control.yaml:31-53 |
| The Gazebo launch enables use_sim_time and spawns entity go1 at z 0.4. | upstream_code | robot_gazebo/launch/go1_gazebo.launch.py:65-78 |
| The URDF declares the FR hip joint as revolute with effort 23.7, lower -0.863, upper 0.863 and velocity 30.1. | upstream_code | robot_description/urdf/go1/go1.urdf.xacro:100-106 |
| The URDF declares the FR calf joint as revolute with effort 35.55, lower -2.818, upper -0.888 and velocity 20.06. | upstream_code | robot_description/urdf/go1/go1.urdf.xacro:170-176 |
| README's Real Robot Integration section is still 'Coming soon...'. | vendor_doc | README.md:113-115 |
| DreamWaQ starts with the command vector 0.15, 0.0, 0.0. | upstream_code | robot_controller/robot_controller/load_dreamwaq_policy.py:167 |
| DreamWaQ's control loop runs the policy every fourth tick, then computes PD torques toward the policy's joint targets and publishes them on every tick. | upstream_code | robot_controller/robot_controller/load_dreamwaq_policy.py:230-270 |
| The README starts the Gazebo simulation with ros2 launch and each policy controller with ros2 run and no argument. | vendor_doc | README.md:72-96 |
| The Gazebo launch includes gazebo_ros's gazebo.launch.py. | upstream_code | robot_gazebo/launch/go1_gazebo.launch.py:23-25 |
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

## Tags

`ros`, `ros2`, `gazebo`, `quadruped`, `simulation`, `policy`, `velocity`, `joint-state`, `imu`

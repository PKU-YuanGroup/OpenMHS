OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.uthiras/scara_robot_ros2

Facts about the package's own surface cite the pinned clone at commit `ece3e91727b0922b336dadf803afaefbcc405e28` (`path/in/clone:LINE`). Facts about the stop cite the reviewed companion sources that `task.json` declares (user decision of 2026-11-05; the user's authorisation of 2026-11-05 for the clones fetched under `work/companions`, listed in its `LOCK.json`), written `companion:<alias>/<path>:<LINE>`: `gazebo_ros_pkgs` (gh.ros-simulation/gazebo_ros_pkgs, fetched under work/companions as `ros-simulation__gazebo_ros_pkgs@3.9.0` at `ae6e5793a31f5927df89cb58007d2a5eb567baa8`), `gazebo_ros2_control` (gh.ros-controls/gazebo_ros2_control, fetched under work/companions as `ros-controls__gazebo_ros2_control@0.4.12` at `42d875b482f0b254d9032950a91b2c5cbd7d1c3d`) and `gazebo_classic` (gh.gazebosim/gazebo-classic, the corpus clone at `b22c6e15e52299865b31093b8feebc9ca19e26e8`). The version evidence that ties this package's stack to those pins is in `task.json` `companions[].version_evidence`; gate G1 re-checks it, and for a fetched companion also its LOCK.json entry, untracked files and write bits. The Humble token on the package side is a committed colcon artifact (`install/setup.bash:22`, `build/rrbot_description/colcon_command_prefix_build.sh.env:37`), not a README line. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The traj_follow node creates the q_ref service of type Ref. | upstream_code | src/Foundation_Project/py_srvcli/py_srvcli/traj_follow.py:21 |
| The traj_follow node creates a joint_states subscription with sensor_msgs/JointState and a publisher for std_msgs/Float64MultiArray on /forward_effort_controller/commands. | upstream_code | src/Foundation_Project/py_srvcli/py_srvcli/traj_follow.py:22-23 |
| The traj_follow listener reads positions 0..2 and velocities 0..2, uses fixed gains 1, 1.5, 1 and 2.5, and computes tau1, tau2 and tau3 from qref1..3; tau3 adds a constant -9.8. | upstream_code | src/Foundation_Project/py_srvcli/py_srvcli/traj_follow.py:30-47 |
| The q_ref callback assigns qref1, qref2 and qref3 from request fields a, b and c and returns qref1 in response field i. | upstream_code | src/Foundation_Project/py_srvcli/py_srvcli/traj_follow.py:67-74 |
| The traj_follow constructor sets qref1, qref2 and qref3 to 0.0 and creates the q_ref service, the joint_states subscription and the effort publisher; it creates no other service, subscription or publisher. | upstream_code | src/Foundation_Project/py_srvcli/py_srvcli/traj_follow.py:13-24 |
| The traj_follow listener publishes the computed efforts on /forward_effort_controller/commands at the end of every joint_states callback. | upstream_code | src/Foundation_Project/py_srvcli/py_srvcli/traj_follow.py:25-66 |
| The control_velocity node creates the Forward_Velocity_Kinematics Fvel service and the Inverse_Velocity_Kinematics Ivel service, creates a joint_states subscription and a publisher for std_msgs/Float64MultiArray on /forward_effort_controller/commands. | upstream_code | src/Foundation_Project/py_srvcli/py_srvcli/control_velocity.py:60-63 |
| The Ivel callback assigns ev1, ev2 and ev3 from request endeff_vel_x, endeff_vel_y and endeff_vel_z. | upstream_code | src/Foundation_Project/py_srvcli/py_srvcli/control_velocity.py:214-216 |
| The control_velocity listener uses J_inv multiplied by the Ev globals to form desired_velocity and computes a PID effort on every joint_states message. | upstream_code | src/Foundation_Project/py_srvcli/py_srvcli/control_velocity.py:108-124 |
| The Fvel callback computes end-effector velocities from the requested joint velocities and returns endeff_vel_x, endeff_vel_y and endeff_vel_z. | upstream_code | src/Foundation_Project/py_srvcli/py_srvcli/control_velocity.py:195-204 |
| The control_velocity constructor initialises its globals and creates the Fvel and Ivel services, the joint_states subscription and the effort publisher; it creates no other service, subscription or publisher. | upstream_code | src/Foundation_Project/py_srvcli/py_srvcli/control_velocity.py:14-64 |
| The control_velocity listener adds -9.8 to the joint3 effort and publishes the efforts on /forward_effort_controller/commands at the end of every joint_states callback. | upstream_code | src/Foundation_Project/py_srvcli/py_srvcli/control_velocity.py:65-164 |
| The FK node creates a joint_states subscription with sensor_msgs/JointState and a publisher for the homogeneous matrix as a std_msgs/String on the relative topic h_mat. | upstream_code | src/FK/FK/end_pose.py:13-18 |
| The FK listener computes A1, A2, A3 and their product H, writes H into a four-line string and publishes it on h_mat. | upstream_code | src/FK/FK/end_pose.py:28-46 |
| The service_member_function node creates the Inverse_Kinematics service of type Ik. | upstream_code | src/Foundation_Project/py_srvcli/py_srvcli/service_member_function.py:11 |
| The service_member_function IK callback assigns the five response fields from its four two-link solutions and the computed d3. | upstream_code | src/Foundation_Project/py_srvcli/py_srvcli/service_member_function.py:70-74 |
| The py_srvcli console scripts run traj_follow for service and listener, control_velocity for control, and name a Velocity_Service module for vel; there is no console script for service_member_function. | upstream_code | src/Foundation_Project/py_srvcli/setup.py:21-27 |
| The URDF declares joint1 and joint2 as continuous revolute joints and joint3 as a prismatic joint whose limit is lower -${height4-width}, upper 0, effort 1000 and velocity 0.2. | upstream_code | src/rrbot_simulation_files/rrbot_simulation_files/rrbot_description/urdf/rrbot_description.urdf.xacro:49-124 |
| The ros2_control description declares position and velocity command interfaces at -10..10 and effort command interfaces at -100..100 for joint1, joint2 and joint3. | upstream_code | src/rrbot_simulation_files/rrbot_simulation_files/rrbot_description/ros2_control/rrbot.ros2_control.xacro:16-66 |
| The rrbot_world launch includes Gazebo, starts controller_manager, spawns the joint state broadcaster, spawns forward_position_controller and forward_velocity_controller stopped, and spawns forward_effort_controller active. | upstream_code | src/rrbot_simulation_files/rrbot_simulation_files/rrbot_gazebo/launch/rrbot_world.launch.py:33-106 |
| The rrbot_world launch includes gazebo_ros's gazebo.launch.py with the rrbot world. | upstream_code | src/rrbot_simulation_files/rrbot_simulation_files/rrbot_gazebo/launch/rrbot_world.launch.py:42-46 |
| The rrbot_world launch starts a Node with package controller_manager and executable ros2_control_node, and passes robot_description and robot_controllers as its parameters. | upstream_code | src/rrbot_simulation_files/rrbot_simulation_files/rrbot_gazebo/launch/rrbot_world.launch.py:69-75 |
| The launch description starts gazebo, spawn_entity, the standalone controller_manager node, robot_state_publisher, the joint_state_broadcaster spawner and the delayed controller spawners. | upstream_code | src/rrbot_simulation_files/rrbot_simulation_files/rrbot_gazebo/launch/rrbot_world.launch.py:130-139 |
| The spawners name the controller manager /controller_manager. | upstream_code | src/rrbot_simulation_files/rrbot_simulation_files/rrbot_gazebo/launch/rrbot_world.launch.py:82-106 |
| The rrbot Gazebo description loads the gazebo_ros2_control plugin (libgazebo_ros2_control.so) with the gazebo_controllers.yaml parameters. | upstream_code | src/rrbot_simulation_files/rrbot_simulation_files/rrbot_description/gazebo/rrbot.gazebo.xacro:11-15 |
| The rrbot ros2_control description uses the gazebo_ros2_control/GazeboSystem hardware plugin. | upstream_code | src/rrbot_simulation_files/rrbot_simulation_files/rrbot_description/ros2_control/rrbot.ros2_control.xacro:13-15 |
| The controller_switch client creates /controller_manager/switch_controller and sets activate_controllers to forward_velocity_controller and deactivate_controllers to forward_position_controller. | upstream_code | src/rrbot_simulation_files/rrbot_simulation_files/rrbot_gazebo/src/controller_switch.cpp:17-21 |
| The gazebo_controllers configuration declares forward_effort_controller as a forward_command_controller/ForwardCommandController for joint1, joint2 and joint3 with the effort interface. | upstream_code | src/rrbot_simulation_files/rrbot_simulation_files/rrbot_gazebo/config/gazebo_controllers.yaml:11-54 |
| The README runs ros2 run FK listener. | vendor_doc | README.md:29-35 |
| The README runs py_srvcli service and calls q_ref, and runs py_srvcli control and calls Forward_Velocity_Kinematics and Inverse_Velocity_Kinematics. | vendor_doc | README.md:70-104 |
| The README calls Inverse_Kinematics after ros2 run py_srvcli service. | vendor_doc | README.md:47-51 |
| The py_srvcli package.xml declares Apache License 2.0. | upstream_code | src/Foundation_Project/py_srvcli/package.xml:8 |
| The FK package manifest still contains the placeholder license text TODO: License declaration. | upstream_code | src/FK/package.xml:8 |
| The ikinterface package manifest still contains the placeholder license text TODO: License declaration. | upstream_code | src/Foundation_Project/ikinterface/package.xml:8 |
| The rrbot_gazebo package.xml declares BSD. | upstream_code | src/rrbot_simulation_files/rrbot_simulation_files/rrbot_gazebo/package.xml:11 |
| gazebo.launch.py includes gzserver.launch.py unless its server argument is false. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/gazebo.launch.py:32-38 |
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
| The gazebo_ros2_control plugin creates its controller manager node with the name controller_manager. | upstream_code | companion:gazebo_ros2_control/gazebo_ros2_control/src/gazebo_ros2_control_plugin.cpp:362-370 |
| The gazebo_ros2_control plugin calls GazeboSystem::initSim with the model the plugin is loaded for. | upstream_code | companion:gazebo_ros2_control/gazebo_ros2_control/src/gazebo_ros2_control_plugin.cpp:337-346 |
| gazebo_ros2_control spins its controller manager's executor on a thread of its own. | upstream_code | companion:gazebo_ros2_control/gazebo_ros2_control/src/gazebo_ros2_control_plugin.cpp:400-407 |
| gazebo_ros2_control connects its Update to the world-update begin event. | upstream_code | companion:gazebo_ros2_control/gazebo_ros2_control/src/gazebo_ros2_control_plugin.cpp:409-414 |
| gazebo_ros2_control's Update reads the simulation time, updates the controllers and writes their commands to the joints. | upstream_code | companion:gazebo_ros2_control/gazebo_ros2_control/src/gazebo_ros2_control_plugin.cpp:419-437 |
| GazeboSystem::initSim creates the system's private data and stores the parent model. | upstream_code | companion:gazebo_ros2_control/gazebo_ros2_control/src/gazebo_system.cpp:134-144 |
| GazeboSystem::write reads the simulation time from the parent model's world. | upstream_code | companion:gazebo_ros2_control/gazebo_ros2_control/src/gazebo_system.cpp:818-825 |

## Scope and interface

The shipped `py_srvcli` entry points are `service`/`listener` (traj_follow), `control` (control_velocity) and `vel` (which names the absent `py_srvcli.Velocity_Service`). The FK package installs the `listener` executable. The IK file exists but has no console script, and the README's `ros2 run py_srvcli service` starts traj_follow rather than the IK node.

The bound interfaces are:

* `/pause_physics` (`std_srvs/srv/Empty`): the e-stop. gazebo_ros 3.9.0 `OnPause` calls `World::SetPaused(true)`.
* `/get_model_list` (`gazebo_msgs/srv/GetModelList`): the E1 stall read-back. Two answers 250 ms apart must carry the same `header.stamp` (the world's sim time). That pair is the confirmation window. `safety_status` returns the cached result of that pair.
* `/forward_effort_controller/commands` (`std_msgs/msg/Float64MultiArray`): one publication of three joint efforts. The receipt is `published`, `confirmed` (always false) and `sent_efforts` (the three values handed to rosbridge, not a measurement).
* `x-cap.uthiras.joint_states.v1` reads one fresh `/joint_states` sample. It is not the device resource.
* `/h_mat` (`std_msgs/msg/String`): the FK node's textual homogeneous matrix.
* `/Forward_Velocity_Kinematics` (`ikinterface/srv/Fvel`): the observational Jacobian-product service.

The device resource reads no topic. The high-level `q_ref` and `Ivel` services are effectful, but their responses expose no success/failure field, so they are not bound. `Inverse_Kinematics` is not bound: its module is not a console script, and its inputs have no stated bounds.

## Safety

The e-stop pauses the Gazebo world and confirms it only inside a two-sample window: two `/get_model_list` answers 250 ms apart with the same `header.stamp` (`estop_latency_ms` 1500). That is a frozen sim time for those two samples, not a measured standstill. `World::Step` still advances sim time and calls `Update` while paused when `stepInc` is pending or a reset is due (`World.cc:835-841`). A WorldControl step or multi_step can schedule that (`World.cc:1630-1639`). gazebo_ros2_control writes joint commands on each such update (`gazebo_ros2_control_plugin.cpp:433-436`). `safety_status` returns the cached confirmation and does not call `/get_model_list` again. No unpause and no re-enable are offered. traj_follow (`traj_follow.py:25-66`, including the constant `-9.8` on joint3 at line 47) and control_velocity (`control_velocity.py:65-164`, `effort[2] += -9.8` at line 124, publish at line 164) publish a new effort on every `joint_states` callback. The controller's stored command is not in a declared companion, so this package cannot clear it. `mhs.safety.reset` releases the latch only. The operator stops traj_follow and control_velocity, decides the effort, and unpauses outside MHS.

`rrbot_world.launch.py:69-75` starts a standalone `controller_manager` `ros2_control_node` beside the gazebo_ros2_control plugin. `GazeboSystem::initSim` stores `parent_model_` (`gazebo_system.cpp:134-144`, called from the plugin at `gazebo_ros2_control_plugin.cpp:337-346`). `GazeboSystem::write` reads sim time with `parent_model_->GetWorld()` (`gazebo_system.cpp:818-825`). Which node publishes `/joint_states` while the world is paused is not settled by that source. The fake silences `/joint_states` while paused unless `wall_clock_joint_states` is set, and that switch still returns a sample. Do not read a joint-state sample as a stopped state.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS-free recording transport for the pinned ROS 2 services and topics (no Gazebo)`, level F0, determinism `none`, `timestep_ms: 0`, `realtime_factor: 0`, reset `none`, and no snapshot/restore. The gaps disclose the absent physics, the two-sample confirmation window, the cached `safety_status`, the paused step and reset path, the unsettled `/joint_states` publisher, the colcon-artifact distro evidence, and that recovery is outside MHS with no unpause. Evidence is fake `contract_checked` only.

## Tags

`ros`, `ros2`, `scara`, `rrp`, `gazebo`, `kinematics`, `trajectory`, `simulation`

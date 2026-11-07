# Facts and tags for gh.lihuang3/ur5_ros-gazebo

Facts about the package's own surface cite the pinned clone at commit `2f7b9b056bb41b9412f86589a60e25ba2816b78b` (`path/in/clone:LINE`). Facts about the stop cite the reviewed companion sources that `task.json` declares (user decision of 2026-11-05; the user's authorisation of 2026-11-05 for the clones fetched under `work/companions`, listed in its `LOCK.json`), written `companion:<alias>/<path>:<LINE>`: `gazebo_ros_pkgs` (gh.ros-simulation/gazebo_ros_pkgs, fetched under work/companions as `ros-simulation__gazebo_ros_pkgs@2.5.21` at `98bb3d0a0afc65725deaa1633e21ff6f5322b564`) and `gazebo_classic` (gh.gazebosim/gazebo-classic, fetched under work/companions as `gazebosim__gazebo-classic@gazebo7_7.16.1` at `6fea5977c4518f6d722855c0e342e1e5acf64bac`). The version evidence that ties this package's stack to those pins is in `task.json` `companions[].version_evidence`; gate G1 re-checks it, and for a fetched companion also its LOCK.json entry, untracked files and write bits. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The README describes the repository as a UR5 pick-and-place demonstration in ROS and Gazebo using a USB camera and vacuum grippers. | vendor_doc | README.md:1 |
| The README says the default ur_description files include no camera or vacuum gripper modules and tells the user to copy the clone's common.gazebo.xacro and ur5.urdf.xacro over them. | vendor_doc | README.md:46-49 |
| The initialization launch starts Gazebo, uploads the robot description from the ur_description package, starts the UR5 arm controller and MoveIt, then starts the blocks_spawner, blocks_poses_publisher, ur5_vision, ur5_mp and ur5_gripper nodes. | upstream_code | launch/initialize.launch:9-54 |
| The launch loads the arm controller from the ur_gazebo package and remaps /follow_joint_trajectory to /arm_controller/follow_joint_trajectory when sim is true. | upstream_code | launch/initialize.launch:27-33 |
| The URDF declares the libgazebo_ros_vacuum_gripper.so plugin for the first gripper with robotNamespace /ur5/vacuum_gripper and topicName grasping. | upstream_code | src/ur_description/ur5.urdf.xacro:357-363 |
| The URDF declares further vacuum-gripper plugins under /ur5/vacuum_gripper1 through /ur5/vacuum_gripper8; the channel-3 plugin also names its topic grasping2. | upstream_code | src/ur_description/ur5.urdf.xacro:396-675 |
| The first vacuum plugin config sets maxForce 50, maxDistance 0.05 and minDistance 0.01. | upstream_code | src/ur_description/ur5.urdf.xacro:361-363 |
| The gripper node waits for the absolute /ur5/vacuum_gripper/on service and calls it with an Empty service proxy. | upstream_code | ur5_gripper.py:20-26 |
| The gripper node waits for the absolute /ur5/vacuum_gripper/off service and calls it with an Empty service proxy. | upstream_code | ur5_gripper.py:128-134 |
| The gripper node defines on and off functions for the eight additional channels, each naming /ur5/vacuum_gripperN/on or /ur5/vacuum_gripperN/off. | upstream_code | ur5_gripper.py:32-208 |
| The gripper node imports Empty from std_srvs.srv and Bool from std_msgs.msg. | upstream_code | ur5_gripper.py:10-11 |
| The gripper node subscribes to /ur5/vacuum_gripper/grasping with the Bool type. | upstream_code | ur5_gripper.py:235 |
| The trigger callback calls every gripper on function when msg.flag2 is true and every off function otherwise. | upstream_code | ur5_gripper.py:208-230 |
| The gripper node subscribes trigger to the relative cxy1 Tracker topic. | upstream_code | ur5_gripper.py:237 |
| The vision node subscribes to /ur5/usbcam/image_raw with the Image type and publishes the relative topic cxy with the Tracker type. | upstream_code | ur5_vision.py:47-48 |
| The motion node subscribes to the relative cxy Tracker topic and publishes the relative cxy1 Tracker topic. | upstream_code | ur5_mp.py:44-45 |
| The motion node constructs MoveGroupCommander('manipulator') and executes plans through the MoveIt client. | upstream_code | ur5_mp.py:62-141 |
| The motion node registers cleanup with rospy.on_shutdown. | upstream_code | ur5_mp.py:57 |
| cleanup calls self.arm.stop() and shuts down MoveIt. | upstream_code | ur5_mp.py:149-158 |
| The motion node publishes the tracker with cxy_pub with flag2 1 when len(self.pointx) is 11, and with flag2 0 after it has executed the lift, transition, end-state and retreat plans. | upstream_code | ur5_mp.py:203-262 |
| The motion node's header states that the program is distributed under the GNU General Public License, version 2 or later. | upstream_code | ur5_mp.py:10-22 |
| The Tracker message declares float64 x, y, z, error_x, error_y and error_z and bool flag1, flag2 and flag3. | upstream_code | msg/Tracker.msg:1-12 |
| The block-pose node subscribes to /current_blocks and /gazebo/model_states and advertises the relative blocks_poses topic with the ur5_notebook/blocks_poses type. | upstream_code | blocks_poses_publisher.cpp:108-113 |
| The blocks_poses message declares float64 arrays x, y and z. | upstream_code | msg/blocks_poses.msg:1-7 |
| The camera plugin declares cameraName ur5/usbcam and imageTopicName image_raw with an 800 by 800 R8G8B8 image at 30 Hz. | upstream_code | src/ur_description/common.gazebo.xacro:40-71 |
| The package manifest leaves the license field as TODO. | upstream_code | package.xml:15 |
| The initialization launch includes gazebo_ros's empty_world.launch with the world worlds/empty.world and paused and gui arguments that default to false and true. | upstream_code | launch/initialize.launch:5-16 |
| The vacuum gripper plugin advertises its grasping Bool topic and its on and off std_srvs::Empty services on a custom callback queue. | upstream_code | companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_vacuum_gripper.cpp:116-133 |
| The vacuum gripper plugin serves that queue on its own thread and connects UpdateChild to the world-update begin event. | upstream_code | companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_vacuum_gripper.cpp:136-142 |
| The on service sets the stored status to true and the off service sets it to false. | upstream_code | companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_vacuum_gripper.cpp:147-168 |
| UpdateChild publishes grasping false when the status is off; when it is on it pulls every link within 0.05 m of the gripper link with a force of at most 20 and publishes grasping true for such a link. | upstream_code | companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_vacuum_gripper.cpp:172-230 |
| The vacuum plugin's queue thread serves its callbacks with a 0.01 s wall-clock wait while its node handle is ok. | upstream_code | companion:gazebo_ros_pkgs/gazebo_plugins/src/gazebo_ros_vacuum_gripper.cpp:235-243 |
| gazebo_ros_control connects its Update to the world-update begin event. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros_control/src/gazebo_ros_control_plugin.cpp:208-211 |
| gazebo_ros_control's Update reads the simulation time, updates the controllers and writes their commands to the simulated joints. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros_control/src/gazebo_ros_control_plugin.cpp:223-270 |
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

The package serves the ROS-callable gripper surface declared by the clone: the
nine absolute `std_srvs/Empty` vacuum `on`/`off` services that
`ur5_gripper.py` waits for and calls, the first plugin's
`/ur5/vacuum_gripper/grasping` `std_msgs/Bool` topic, the `/cxy`
`ur5_notebook/Tracker` topic published by the vision node and the
`/blocks_poses` `ur5_notebook/blocks_poses` topic published by the block-pose
node. Each binding cites the line that states its endpoint and the import or
include line that states its type.

The UR5 arm itself is moved by the clone's Python nodes through the MoveIt
`moveit_commander` client; the clone declares no ROS service or action for arm
motion. That motion, the external `arm_controller` and its
`FollowJointTrajectory` action, the camera image stream, block spawning and
the remaining Gazebo model services are NOT COVERED. The vacuum service
acknowledgement is not a measured grasp: the empty `std_srvs/Empty` response
only proves that the plugin handler returned.

## Safety

The simulated device is R2 because the demonstration is a UR5 arm that picks and drops a box.

The clone offers no acknowledged stop of its own (model review, 2026-11-05; the author had bound the first channel's
`/ur5/vacuum_gripper/off` service as the e-stop). Releasing the vacuum drops a held payload: the vacuum plugin is
gazebo_ros's `libgazebo_ros_vacuum_gripper`, whose off service only sets its stored status to false
(`gazebo_ros_vacuum_gripper.cpp:147-168`, a companion citation), and it does not stop the arm. The vacuum-off
commands stay ordinary commands.

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
companion citations name; rosbridge cannot read their versions. The pause also
freezes the arm: gazebo_ros_control updates the controllers and writes their commands only from the world update
(`gazebo_ros_control_plugin.cpp:208-211, 223-270`), and each vacuum channel keeps its stored status.

No unpause is offered (the orchestrator's SAFE-042 condition). On an unpause the arm controller resumes the MoveIt
trajectory `ur5_mp` sent and each vacuum channel acts with its stored status (`gazebo_ros_vacuum_gripper.cpp:172-230`);
the package cannot clear the trajectory and must not release the vacuum. While paused the vacuum services still
answer (the plugin serves them on its own wall-clock queue thread, `gazebo_ros_vacuum_gripper.cpp:136-142, 235-243`),
so a vacuum command after `mhs.safety.reset` changes the stored status that acts on the next unpause. The operator
recovers outside MHS: stop or restart `ur5_mp` and MoveIt (its shutdown callback runs `self.arm.stop()`,
`ur5_mp.py:57, 149-158`), then press play in the Gazebo GUI or call `rosservice call gazebo/unpause_physics`. The
shipped `ur5_gripper.py` still switches every channel on again whenever `ur5_mp` publishes a Tracker with `flag2`
true on `cxy1` (`ur5_gripper.py:208-237`, `ur5_mp.py:203-262`).

The vacuum plugins and the camera exist only after the user copies the clone's `src/ur_description` xacro files over
the installed universal_robot `ur_description` package (`README.md:46-49`); `initialize.launch` uploads the robot
description from that package. `ur5_mp.py` and `ur5_vision.py` carry GPL-2.0-or-later headers while `package.xml`
leaves the licence as TODO (publish_review required).

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS contract fake (no
physics)`, level F0, determinism `none`, `timestep_ms: 0`, `realtime_factor: 0`,
reset `none` and no snapshot/restore. The fake answers the declared services
and subscriptions and the two companion Gazebo services with placeholder
values, keeps a paused flag that silences the three topics, and runs no
Gazebo, vacuum plugin, ODE physics, MoveIt, camera or wall-clock loop. The gaps disclose the absent
attachment physics, the placeholder observations and the unexposed arm,
camera and spawning surfaces. No real ROS graph, Gazebo, MoveIt, simulator or
hardware was contacted.

## Tags

`ros`, `ros1`, `gazebo`, `ur5`, `vacuum-gripper`, `pick-and-place`

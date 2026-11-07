# Facts and tags for gh.ad-sdl/sdl-simulation

Facts about the package's own surface cite the pinned clone at commit `7ae7b7ac5581a891451e0007c0cd8de885773082` (`path/in/clone:LINE`). Facts about the stop cite the reviewed companion sources that `task.json` declares (user decision of 2026-11-05; a reviewed `LOCK.json` `needed_by` addition for the clones already fetched under `work/companions`), written `companion:<alias>/<path>:<LINE>`: `gazebo_ros_pkgs` (gh.ros-simulation/gazebo_ros_pkgs, fetched under work/companions as `ros-simulation__gazebo_ros_pkgs@2.8.7` at `0667c5e52e8afa1f478955d8a2569b473a5acdf1`) and `gazebo_classic` (gh.gazebosim/gazebo-classic, fetched under work/companions as `gazebosim__gazebo-classic@gazebo9_9.19.0` at `e4400ae7e04e4859eec392ac67b813402703bab0`). The version evidence that ties this package's stack to those pins is in `task.json` `companions[].version_evidence`; gate G1 re-checks it. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The README describes the repository as code for the SDL simulation project at Argonne National Laboratory/University of Chicago. | vendor_doc | README.md:3 |
| The README says ROS Melodic is assumed installed. | vendor_doc | README.md:6 |
| The README publishes geometry_msgs/Pose to /ur_arm/moveit/goal_pose to control the arm. | vendor_doc | README.md:79-91 |
| sdl_moveit_node.py subscribes to /ur_arm/moveit/goal_pose with the fully qualified geometry_msgs.msg.Pose type. | upstream_code | sdl_gazebo/src/sdl_moveit_node.py:136 |
| go_to_pose_goal sets the pose target, blocks in self.group.go(wait=True), calls self.group.stop(), and clears the pose targets; the stop call is inside the callback after motion returns. | upstream_code | sdl_gazebo/src/sdl_moveit_node.py:114-122 |
| sdl_nav_moveit_combined.launch starts the ur_python_planner node from sdl_gazebo/src/sdl_moveit_node.py. | upstream_code | sdl_gazebo/launch/sdl_nav_moveit_combined.launch:32 |
| sdl_nav_moveit_combined.launch defaults tf_prefix to an empty string and includes lab_world.launch. | upstream_code | sdl_gazebo/launch/sdl_nav_moveit_combined.launch:2-9 |
| The README tells the operator to press the play button in Gazebo after the paused launch. | vendor_doc | README.md:57-62 |
| lab_world.launch passes paused=true to the empty-world launch when no namespace is configured. | upstream_code | sdl_gazebo/launch/lab_world.launch:44-55 |
| The branch that runs when namespace is not empty includes empty_world.launch with paused=false. | upstream_code | sdl_gazebo/launch/lab_world.launch:14-23 |
| lab_ar.world sets the default physics element type to ode. | upstream_code | sdl_gazebo/world/lab_ar.world:67 |
| The demo node creates a PoseStamped publisher on move_base_simple/goal, a Pose publisher on /ur_arm/moveit/goal_pose, and Float64 publishers on the left and right gripper command topics. | upstream_code | sdl_gazebo/python-nodes/can_demo_no_camera.py:18-21 |
| can_demo.py publishes PoseStamped on move_base_simple/goal, Pose on /ur_arm/moveit/goal_pose and Float64 on both gripper command topics, and subscribes to /move_group/status. | upstream_code | sdl_gazebo/python-nodes/can_demo.py:18-22 |
| The README says the MIR is navigated by publishing to /move_base_simple/goal. | vendor_doc | README.md:99 |
| sdl_nav_moveit_combined.launch includes mir_navigation's move_base.xml. | upstream_code | sdl_gazebo/launch/sdl_nav_moveit_combined.launch:36-38 |
| The README says the 2F140 gripper is controlled by publishing to /left_gripper_position_controller/command and /right_gripper_position_controller/command. | vendor_doc | README.md:107 |
| gripper_control.yaml declares left_gripper_position_controller and right_gripper_position_controller as position_controllers/JointPositionController for finger_joint and right_outer_knuckle_joint. | upstream_code | sdl_gazebo/config/gripper_control.yaml:1-6 |
| ros_controllers.launch loads gazebo_controller.yaml and gripper_control.yaml with rosparam and spawns left_gripper_position_controller and right_gripper_position_controller. | upstream_code | sdl_moveit_config/launch/ros_controllers.launch:6-11 |
| gazebo_controller.yaml names gazebo_ros_control as the key of a pid_gains map. | upstream_code | sdl_moveit_config/config/gazebo_controller.yaml:1-2 |
| can_demo_no_camera.py imports PoseStamped and Pose from geometry_msgs.msg and Float64 from std_msgs.msg. | upstream_code | sdl_gazebo/python-nodes/can_demo_no_camera.py:1-7 |
| can_demo.py subscribes to /move_group/status with actionlib_msgs.msg.GoalStatusArray. | upstream_code | sdl_gazebo/python-nodes/can_demo.py:20 |
| can_demo_no_camera.py subscribes to move_base/status with actionlib_msgs.msg.GoalStatusArray. | upstream_code | sdl_gazebo/python-nodes/can_demo_no_camera.py:29 |
| The navigation demo's lock_control sends the arm, gripper and drive-away commands when status_list is empty or its first entry's text is 'Goal reached.', and otherwise sets locked. | upstream_code | sdl_gazebo/python-nodes/can_demo_no_camera.py:32-45 |
| Idle.execute logs Executing state BAR and returns outcome2. | upstream_code | sdl_gazebo/python-nodes/table_1_smach.py:8-10 |
| ros_controllers.yaml declares ur_arm_controller with action_ns follow_joint_trajectory and the short type FollowJointTrajectory, but no fully qualified ROS action type. | upstream_code | sdl_moveit_config/config/ros_controllers.yaml:29-40 |
| move_group.launch starts the moveit_ros_move_group move_group node, commented as the move_group node/action server. | upstream_code | sdl_moveit_config/launch/move_group.launch:67-68 |
| sdl_moveit_config/package.xml declares the BSD licence. | upstream_code | sdl_moveit_config/package.xml:11 |
| sdl_gazebo/package.xml still carries the licence placeholder TODO. | upstream_code | sdl_gazebo/package.xml:16 |
| The gazebo_ros gzserver wrapper adds libgazebo_ros_api_plugin to the server's plugins unless the arguments already name it. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/scripts/gzserver:20-24 |
| empty_world.launch starts the Gazebo server as the node named gazebo of package gazebo_ros, with the physics engine argument -e $(arg physics). | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:46-48 |
| empty_world.launch defaults its physics argument to ode. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:15 |
| empty_world.launch defaults its gui argument to true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:8 |
| When gui is true, empty_world.launch starts the node gazebo_gui of type gzclient. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:51-54 |
| When its paused argument is true, empty_world.launch sets command_arg1 to -u. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/launch/empty_world.launch:30-31 |
| The API plugin calls ros::init with the node name gazebo when ROS is not initialised yet. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:127-128 |
| The API plugin creates its node handle in the private namespace ~ and advertises its topics and services there. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:147 |
| The API plugin advertises the service pause_physics with the std_srvs::Empty type on its own callback queue gazebo_queue_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:462-468 |
| The API plugin advertises the service get_physics_properties with the gazebo_msgs::GetPhysicsProperties type on gazebo_queue_. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:364-370 |
| gazeboQueueThread serves gazebo_queue_ in a loop with a 0.001 s wall-clock wait while the node handle is ok. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:235-242 |
| pausePhysics calls world_->SetPaused(true) and returns true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1662-1666 |
| unpausePhysics calls world_->SetPaused(false) and returns true. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1668-1672 |
| getPhysicsProperties sets res.pause to world_->IsPaused(). | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1426 |
| getPhysicsProperties sets success true only when the physics engine type is ode; for any other engine it sets success false and returns false. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1433-1465 |
| The GetPhysicsProperties response field pause is true if the physics engine is paused. | upstream_code | companion:gazebo_ros_pkgs/gazebo_msgs/srv/GetPhysicsProperties.srv:4 |
| Among the world-update begin hooks that its comment says apply forces and publish sim time on /clock, the API plugin connects publishSimTime. | upstream_code | companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:224-227 |
| World::Step advances simulation time and calls Update only when the world is not paused, a step increment is pending or a reset is due; otherwise it adds the step to the pause time. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:691-710 |
| World::Step holds worldUpdateMutex while it steps the world. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:683 |
| World::SetPaused returns when the paused flag already equals its argument and otherwise stores the flag under worldUpdateMutex. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1428-1436 |
| World::IsPaused returns the stored paused flag. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1422-1425 |
| World::Update fires the worldUpdateBegin event and then updates every model. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:776-782 |
| World::Step calls ProcessMessages after the paused or unpaused branch, so pending messages are processed on every step, paused or not. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:691-718 |
| A WorldControl message with step calls OnStep, and one with multi_step pauses the world and sets the number of steps to run while paused. | upstream_code | companion:gazebo_classic/gazebo/physics/World.cc:1462-1477 |

## Scope

The package serves the simulated mobile manipulator's ROS 1 topic graph. Primary control is the unacknowledged arm goal publication on `/ur_arm/moveit/goal_pose`. The package also publishes the map-frame navigation goal and the two gripper position commands. Each publication receipt reports the values it sent. The MoveIt and move_base action-status topics stay explicit reads. They are not the device resource, and this page does not claim they go silent while the world is paused.

## Limits

Every numeric arm, base and gripper input is `Limit.operator_required`. The clone states example poses and gripper commands, not a workspace, navigation or stroke envelope. `site-limits.example.json` is an illustrative operator overlay, not a device fact.

## Safety

The device is simulated at R2. The e-stop is `/gazebo/pause_physics` (`std_srvs/Empty`), confirmed only when `/gazebo/get_physics_properties` reads `pause` true. Gazebo 9 `World::Step` advances simulation time and calls `Update` only when the world is not paused, a step is pending or a reset is due. That is the paused flag, not a measured standstill, and this package does not claim that gazebo_ros_control or the actionlib status timers stop. No unpause is offered: `group.go` blocks and `group.stop` runs only after it returns and is not a ROS endpoint (`sdl_gazebo/src/sdl_moveit_node.py:114-119`), and this package cannot clear the navigation goal or the gripper publications. `mhs.safety.reset` releases the latch only. Recovery stays paused, and the affected simulation stack is restarted before any manual resume, because those pending requests cannot be shown to have been discarded.

The default launch (`tf_prefix` empty) takes the no-namespace branch, which starts the world paused (`sdl_gazebo/launch/lab_world.launch:44-55`). `README.md:57-62` tells the operator to press play at startup; that is not the e-stop recovery. The namespaced branch passes `paused=false` (`lab_world.launch:14-23`) and is not the launch this package serves. The Gazebo include sits outside the namespace group in both branches.

`sdl_moveit_config/package.xml` says BSD and `sdl_gazebo/package.xml` still says TODO. The card records `NOASSERTION` and `publish_review` required. No ROS graph, Gazebo, MoveIt or hardware was run. Evidence is `contract_checked` on the fake only.

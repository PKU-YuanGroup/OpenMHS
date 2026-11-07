OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.zzy5510/ur5-grasp-and-kinect-demo-on-gazebo

Every fact cites the pinned clone at commit `a5b25d72fe7637ebfad26a60c4bc57c1a8b418c4`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The shipped main.launch starts the simulation launch and the MoveIt move_group launch. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/ur_tc/smart_grasping_sandbox_sample/launch/main.launch:7-12 |
| launch_simulation.launch includes gazebo_ros empty_world.launch with use_sim_time true and the world file from smart_grasping_sandbox_sample. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/ur_tc/smart_grasping_sandbox_sample/launch/launch_simulation.launch:12-20 |
| The gazebo_ros gzserver wrapper appends -s libgazebo_ros_api_plugin.so unless that plugin is already present in the arguments. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/depends/gazebo_ros_pkgs/gazebo_ros/scripts/gzserver:20-24 |
| GazeboRosApiPlugin initializes the ROS node with the name gazebo. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/depends/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:122 |
| GazeboRosApiPlugin advertises its services on a private node handle named '~'. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/depends/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:140 |
| advertiseServices creates the relative pause_physics and unpause_physics services with the std_srvs/Empty type. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/depends/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:430-445 |
| pausePhysics calls world_->SetPaused(true) and returns true. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/depends/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1626-1630 |
| unpausePhysics calls world_->SetPaused(false) and returns true. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/depends/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:1632-1636 |
| GazeboRosApiPlugin advertises rosgraph_msgs/Clock on the absolute /clock topic. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/depends/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:221 |
| GazeboRosApiPlugin connects publishSimTime to the world update-begin event. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/depends/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:201 |
| publishSimTime reads world_->SimTime() and publishes it as rosgraph_msgs/Clock. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/depends/gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp:2091-2110 |
| JointStateController advertises sensor_msgs/JointState on the relative joint_states name through the root node handle. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/depends/ros_controllers/joint_state_controller/src/joint_state_controller.cpp:57 |
| The shipped joint-state controller configuration sets the controller type and publish_rate 50. | upstream_code | src/universal_robot/ur_gazebo/controller/joint_state_controller.yaml:1-3 |
| The shipped controller_utils.launch loads the joint-state controller configuration and spawns the joint_state_controller. | upstream_code | src/universal_robot/ur_gazebo/launch/controller_utils.launch:14-16 |
| launch_simulation.launch loads arm_controller_ur10.yaml and spawns arm_controller, then loads gripper_gazebo_trajectory.yaml and spawns hand_controller. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/ur_tc/smart_grasping_sandbox_sample/launch/launch_simulation.launch:43-48 |
| arm_controller_ur10.yaml, which launch_simulation.launch loads, names six joints in the order shoulder_pan_joint, shoulder_lift_joint, elbow_joint, wrist_1_joint, wrist_2_joint and wrist_3_joint. | upstream_code | src/universal_robot/ur_gazebo/controller/arm_controller_ur10.yaml:3-9 |
| launch_simulation.launch sets robot_description from ur_with_kinect.xacro. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/ur_tc/smart_grasping_sandbox_sample/launch/launch_simulation.launch:23 |
| ur_with_kinect.xacro includes model2.urdf and kinect.xacro. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/ur_tc/ur_desc/urdf/ur5_robotiq_85/ur_with_kinect.xacro:5-6 |
| model2.urdf declares arm_to_finger1 and arm_to_finger2 as prismatic joints. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/ur_tc/ur_desc/urdf/ur5_robotiq_85/model2.urdf:366-396 |
| model2.urdf loads the gazebo_ros_control plugin with DefaultRobotHWSim. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/ur_tc/ur_desc/urdf/ur5_robotiq_85/model2.urdf:5-6 |
| launch_simulation.launch declares gui with default true and paused with default false. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/ur_tc/smart_grasping_sandbox_sample/launch/launch_simulation.launch:2-5 |
| move_generic_model.py's move_model pauses physics, sets the model state and then unpauses physics through g_unpause when pause_physics is true. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/depends/spawn_robot_tools/spawn_robot_tools_pkg/src/spawn_robot_tools_pkg/move_generic_model.py:103-164 |
| ur5_bringup.launch takes a robot_ip argument for the IP of the robot controller. | upstream_code | src/universal_robot/ur_bringup/launch/ur5_bringup.launch:11-12 |
| Robotiq85Gripper opens a serial port, by default /dev/ttyUSB0 at 115200 baud. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/ur_tc/robotiq_85_gripper/robotiq_85_driver/src/robotiq_85/robotiq_85_gripper.py:6-10 |
| The shipped model2.urdf declares the six arm joints as revolute joints with a position limit from -3.14159265359 to 3.14159265359 rad. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/ur_tc/ur_desc/urdf/ur5_robotiq_85/model2.urdf:43-203 |
| The Kinect's gazebo_ros_openni_kinect plugin publishes rgb/image_raw, depth/image_raw, depth/points and the two camera-info topics under its camera name. | upstream_code | src/UR_with_Robotiq_grasp_gazebo/ur_tc/ur_desc/urdf/ur5_robotiq_85/kinect.xacro:46-54 |

## Scope

The package is a configuration-only ROS 1 `RosDriver`. The operator runs Gazebo,
the controllers and rosbridge; the driver does not launch, import or validate
them. The declared surface is:

- `/gazebo/pause_physics` and `/gazebo/unpause_physics` (`std_srvs/Empty`),
  created by `GazeboRosApiPlugin` on the private `~` node handle of the node
  named `gazebo`;
- `/clock` (`rosgraph_msgs/Clock`), published from the Gazebo world update;
- `/joint_states` (`sensor_msgs/JointState`), published by the shipped
  joint-state controller for every registered joint: the six revolute arm joints
  (rad, rad/s, N.m) and the prismatic `arm_to_finger1` and `arm_to_finger2`
  (m, m/s, N), so the output arrays carry unit `1` and name the units per joint.

The card's hints name the separate `robotiq_85_driver` Python/Modbus class.
That package is a hardware gripper driver (it opens a serial port, by default
`/dev/ttyUSB0`), not the simulation control surface; the clone also vendors
`ur_modern_driver` and `ur_bringup` launch files for a real UR arm at a `robot_ip`;
the shipped simulation launch uses `hand_controller` and MoveIt instead. The
card's device plan and candidate classes were therefore not adopted literally.
The arm trajectory controllers, MoveIt planning, the Kinect image and
point-cloud streams, the gripper command topics and the remaining Gazebo
services are **NOT COVERED**.

The two observations are explicit subscriptions. They are deliberately not
automatic resource reads: a live `/clock` and `/joint_states` may go silent
while the world is paused, and the main resource snapshot stays empty.

## Safety

The device is simulated at R2. The input-free `pause` action and the
`/gazebo/pause_physics` service are the declared stop path. The service
callback sets Gazebo's paused flag, so the world stops stepping; the
acknowledgement proves only that the service callback returned, not that the
arm, a controller or a pending trajectory goal has stopped. The shipped launch
starts Gazebo unpaused and the demo drives the arm through MoveIt and
`FollowJointTrajectory` controllers, which this package does not cancel.

After an e-stop the runtime latches and refuses ordinary commands.
`mhs.safety.reset` clears only the software latch and leaves the world paused
(there is no reset binding). The explicit `resume` action is an ordinary
command, refused while latched; after it unpauses Gazebo, a pending controller
goal may continue. The pause holds only until something unpauses the world: the
`resume` command, the Gazebo GUI that `launch_simulation.launch` opens by default
(`gui` true), or another client such as the vendored spawn_robot_tools
`move_model`, which unpauses physics after moving a model (its own launch files,
not the shipped `main.launch`). On a graph that runs the vendored real-arm driver
instead of Gazebo, `/gazebo/pause_physics` does not exist and the e-stop fails
with the latch held, while `/joint_states` would read the real arm.

The spawned arm (`model2.urdf` through `ur_with_kinect.xacro`) uses the ur10
meshes and UR10 link offsets, and the launch loads `arm_controller_ur10.yaml`,
although the repository and its paths name a UR5. This is not a hardware emergency stop and the fake makes no
physical-safety claim.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS contract fake
(no physics)`, level F0, determinism `none`, `timestep_ms: 0`,
`realtime_factor: 0`, reset `none`, no snapshot/restore. The gaps disclose the
absent Gazebo, ODE, controller, MoveIt and wall-clock loop; the placeholder
clock and joint samples; the local pause flag; the silent observations while
paused; and the unexposed motion, image, point-cloud and remaining Gazebo
surfaces.

## Tags

`ros`, `ros1`, `gazebo`, `simulation`, `ur5`, `robot-arm`, `kinect`, `pause`

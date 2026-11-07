# Facts and scope for gh.unity-technologies/unity-robotics-hub

Written by Grok (grok-4.7, a model and not a human) as
ext-p5-reauthor--unity-technologies__unity-robotics-hub-20261105. Every fact cites the pinned
clone at commit `b8d1e1d4c76c9ce75fc145cdbf55a9072cc77364`. `upstream_code` refs name
`path/in/clone:LINE` or a bounded range. Two facts cite git submodules of the clone
(`tutorials/pick_and_place/ROS/src/moveit_msgs`, `tutorials/pick_and_place/ROS/src/ros_tcp_endpoint`):
the gate reads them at the commit the pinned tree's gitlink records (`G1.SUBMODULE_SOURCE`).
The same facts are written into `driver.py` (`facts = [...]`). The reference file is generated
from the driver, not from this page.

The package plans only. It calls `/niryo_moveit` and returns four trajectories with `executed`
false. The Unity arm, the gripper, the ROS-TCP endpoint, the `/niryo_joints` publisher and
`sim_real_pnp` stay uncovered. `niryo_one_ros` is not cited.

## Facts

| fact | source | ref |
|---|---|---|
| moveit_server initialises moveit_commander, starts node niryo_moveit_server, advertises service niryo_moveit of type MoverService with callback plan_pick_and_place, and calls rospy.spin. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/mover.py:124-130 |
| MoverService takes NiryoMoveitJoints joints_input, a geometry_msgs/Pose pick_pose and a geometry_msgs/Pose place_pose, and returns a moveit_msgs/RobotTrajectory[] named trajectories. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/srv/MoverService.srv:1-5 |
| NiryoMoveitJoints carries float64[6] joints and its own geometry_msgs/Pose pick_pose and place_pose. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/msg/NiryoMoveitJoints.msg:1-3 |
| moveit_msgs/RobotTrajectory holds a trajectory_msgs/JointTrajectory joint_trajectory and a trajectory_msgs/MultiDOFJointTrajectory multi_dof_joint_trajectory. | upstream_code | tutorials/pick_and_place/ROS/src/moveit_msgs/msg/RobotTrajectory.msg:1-2 |
| The moveit_msgs package version is 0.11.1 and its license element is BSD. | upstream_code | tutorials/pick_and_place/ROS/src/moveit_msgs/package.xml:3-14 |
| The planner's joint names are joint_1, joint_2, joint_3, joint_4, joint_5 and joint_6. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/mover.py:23 |
| plan_trajectory writes the given start angles into a JointState, sets that as the MoveIt start state, sets the destination pose, calls move_group.plan, raises Exception when the plan is false, and otherwise returns planCompat(plan). | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/mover.py:36-55 |
| planCompat returns plan[1] when sys.version_info is at least (3, 0), and otherwise returns plan. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/mover.py:26-31 |
| plan_pick_and_place constructs a MoveGroupCommander for the group name arm as a local variable. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/mover.py:75-76 |
| The start configuration is req.joints_input.joints. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/mover.py:78 |
| The pre-grasp plan targets req.pick_pose from that start configuration. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/mover.py:81 |
| When the pre-grasp trajectory has no points, plan_pick_and_place returns the still-empty response. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/mover.py:84-85 |
| The grasp plan targets a copy of req.pick_pose whose position.z is reduced by 0.05; the comment calls that a static value coming from Unity. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/mover.py:90-92 |
| When the grasp trajectory has no points, the callback returns the still-empty response. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/mover.py:94-95 |
| The pick-up plan targets req.pick_pose from the grasp plan's last joint positions. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/mover.py:100 |
| When the pick-up trajectory has no points, the callback returns the still-empty response. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/mover.py:102-103 |
| The place plan targets req.place_pose. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/mover.py:108 |
| When the place trajectory has no points, the callback returns the still-empty response. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/mover.py:110-111 |
| When every stage has points, the callback appends the four plans and calls clear_pose_targets. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/mover.py:113-119 |
| The docstring says gripper behaviour is handled outside this trajectory planning. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/mover.py:66-68 |
| The SRDF group arm is the chain from base_link to tool_link. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/config/niryo_one.srdf:32-34 |
| The SRDF file header says the program is free software under the GNU General Public License, either version 3 or any later version. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/config/niryo_one.srdf:8-11 |
| part_3.launch starts server_endpoint from ros_tcp_endpoint, the mover node running mover.py, and includes demo.launch. The tcp_port argument defaults to 10000. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/launch/part_3.launch:1-10 |
| demo.launch includes controllers.launch with simulation_mode true and includes move_group.launch. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/launch/demo.launch:5-10 |
| controllers.launch defaults simulation_mode to false. Its comment says true makes the controller echo the position command and deactivates hardware. fake_communication is set from simulation_mode. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/launch/controllers.launch:3-16 |
| controllers.launch spawns joint_state_controller and niryo_one_follow_joint_trajectory_controller. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/launch/controllers.launch:31-34 |
| move_group.launch defaults allow_trajectory_execution to true and fake_execution to false. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/launch/move_group.launch:15-16 |
| demo.launch sets /move_group/start_state_max_bounds_error to 0.3. The comment says this allows joints to be outside of min and max values when starting. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/launch/demo.launch:19-21 |
| The xacro sets PI to 3.14159265359 and the rotation-limit properties shoulder -3.05433 to 3.05433, arm -1.91986 to 0.640187, elbow -1.397485 to ${PI/2}, forearm -3.05433 to 3.05433, wrist -1.74533 to 1.91986, and hand -2.57436 to 2.57436. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_one_urdf/niryo_one.urdf.xacro:37-50 |
| joint_1 through joint_6 are revolute, and each limit lower and upper attribute names an xacro limit property. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_one_urdf/niryo_one.urdf.xacro:174-220 |
| joint_limits.yaml says joint properties can be changed with the keys max_position, min_position, max_velocity and max_acceleration, and the joint_1 entry sets max_velocity 2.2 and max_acceleration 1.5. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/config/joint_limits.yaml:1-9 |
| part_4.launch starts server_endpoint and the node sim_real_pnp running sim_real_pnp.py. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/launch/part_4.launch:5-9 |
| listener subscribes to topic sim_real_pnp with type MoverServiceRequest and callback plan_pick_and_place. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/sim_real_pnp.py:170-173 |
| send_trajectory_goal sets RobotMoveGoal cmd.Trajectory and cmd.cmd_type to TRAJECTORY_COMMAND_ID, then calls send_goal and wait_for_result. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/sim_real_pnp.py:79-86 |
| sim_real_pnp plan_pick_and_place waits for the action server niryo_one/commander/robot_action. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/sim_real_pnp.py:123-124 |
| PICK_PLACE_HEIGHT_OFFSET is 0.065. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/scripts/sim_real_pnp.py:41 |
| TrajectoryPlanner's serialized field m_RosServiceName defaults to niryo_moveit. | upstream_code | tutorials/pick_and_place/Scripts/TrajectoryPlanner.cs:19 |
| CurrentJointConfig copies each ArticulationBody jointPosition[0] into joints.joints. | upstream_code | tutorials/pick_and_place/Scripts/TrajectoryPlanner.cs:105-113 |
| PublishJoints builds a MoverServiceRequest from CurrentJointConfig and the target and placement poses converted with To<FLU>, and sends it to m_RosServiceName with TrajectoryResponse. | upstream_code | tutorials/pick_and_place/Scripts/TrajectoryPlanner.cs:123-144 |
| TrajectoryResponse starts ExecuteTrajectories when response.trajectories.Length is greater than 0. | upstream_code | tutorials/pick_and_place/Scripts/TrajectoryPlanner.cs:147-152 |
| ExecuteTrajectories writes each point's positions, multiplied by Mathf.Rad2Deg, as ArticulationBody xDrive targets, calls CloseGripper when poseIndex equals Poses.Grasp, and calls OpenGripper after the plans. | upstream_code | tutorials/pick_and_place/Scripts/TrajectoryPlanner.cs:171-207 |
| SourceDestinationPublisher's m_TopicName defaults to /niryo_joints, and Start registers a publisher of NiryoMoveitJointsMsg on that topic. | upstream_code | tutorials/pick_and_place/Scripts/SourceDestinationPublisher.cs:18-38 |
| RealSimPickAndPlace's rosRobotCommandsTopicName defaults to niryo_one/commander/robot_action/goal. | upstream_code | tutorials/pick_and_place/Scripts_Part4/RealSimPickAndPlace.cs:25 |
| RealSimPickAndPlace Start subscribes to rosRobotCommandsTopicName for RobotMoveActionGoal with ExecuteRobotCommands. | upstream_code | tutorials/pick_and_place/Scripts_Part4/RealSimPickAndPlace.cs:69-73 |
| The pick-and-place Docker image starts FROM ros:melodic-ros-base. | upstream_code | tutorials/pick_and_place/docker/Dockerfile:1 |
| The Docker image installs ros-melodic-moveit and ros-melodic-rosbridge-suite. | upstream_code | tutorials/pick_and_place/docker/Dockerfile:5 |
| LICENSE.md says the software is made available under the Apache 2.0 license. | vendor_doc | LICENSE.md:3 |
| The niryo_moveit package.xml license element is Apache 2.0. | upstream_code | tutorials/pick_and_place/ROS/src/niryo_moveit/package.xml:10 |
| The ros_tcp_endpoint package version is 0.7.0 and its license element is Apache 2.0. | upstream_code | tutorials/pick_and_place/ROS/src/ros_tcp_endpoint/package.xml:3-9 |

## Scope

The command is `x-cap.unity-technologies.niryo_pick_place_plan.v1` (`plan_pick_and_place`), verb `invoke`,
exclusive. Exclusive covers this endpoint's locally active invocations. `rospy.spin` only waits
(`mover.py:130`); it does not serialise service callbacks, so another client of `/niryo_moveit` can
overlap this callback on the shared MoveIt `move_group` node. Plan only while Unity is not calling
the service. A deadline or an e-stop does not retire a plan already sent. The ROS binding is
`operation: read` on `/niryo_moveit` (`niryo_moveit/MoverService`,
`mover.py:128`, type import `:21`). The six start angles are radians and are sent as
`joints_input.joints`. The pick and place positions and quaternions are sent as the service-level
poses. The output is four plans of joint names and points, plus `executed`, which is always false.

Joint indexes 0, 1, 3, 4 and 5 use the xacro rotation-limit properties. Elbow index 2 is
operator_required because the upper property is `${PI/2}`. Pose components are operator_required.
`site-limits.example.json` is an operator example. Its elbow max is `3.14159265359/2` from the
file's PI literal and is not a Limit source. `demo.launch` allows 0.3 rad of start error past the
URDF limits. This package does not add 0.3.

The SRDF file header is GPL-3.0. The card and `niryo_moveit/package.xml` are Apache-2.0. The lock
keeps the card's Apache-2.0.

## Not covered

The Unity arm and gripper (`TrajectoryPlanner.cs:171-207`), the ROS-TCP endpoint
(`part_3.launch:5-8`), the `/niryo_joints` publisher (`SourceDestinationPublisher.cs:18`), and the
part-4 action client (`sim_real_pnp.py:79-86`, `:123-124`, `:170-173`). `niryo_one_ros` is the
real-robot driver and is not cited.

## Deployment notes for a live run (never run for this package)

The tutorial image is `tutorials/pick_and_place/docker/Dockerfile` (`FROM ros:melodic-ros-base`,
line 1; `ros-melodic-moveit` and `ros-melodic-rosbridge-suite`, line 5). `part_3.launch` starts
the ROS-TCP endpoint and `mover.py`. The operator starts rosbridge and publishes its port. This
package was not run against that image.

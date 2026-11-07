# Facts and scope for gh.unity-technologies/robotics-object-pose-estimation

Written by Claude (claude-opus-5-5, a model and not a human) as phase-4 agent p4-unity. Every fact cites the pinned
clone at commit `45156479bee5d308085022aa8f20edc0c6a3bccc`; `upstream_code` refs name `path/in/clone:LINE` or a
bounded range. Two facts cite git submodules of the clone (`ROS/src/moveit_msgs`, `ROS/src/ros_tcp_endpoint`): the
gate reads them at the commit the pinned tree's gitlink records (`G1.SUBMODULE_SOURCE`). The same facts are written
into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| mover.py's moveit_server initialises moveit_commander and the ur3_moveit_server node and advertises the service ur3_moveit of type MoverService with the callback plan_pick_and_place. | upstream_code | ROS/src/ur3_moveit/scripts/mover.py:137-144 |
| MoverService takes UR3MoveitJoints joints_input, a geometry_msgs/Pose pick_pose and a geometry_msgs/Pose place_pose, and returns a moveit_msgs/RobotTrajectory[] named trajectories. | upstream_code | ROS/src/ur3_moveit/srv/MoverService.srv:1-5 |
| UR3MoveitJoints carries six float64 joint values joint_00 to joint_05 and its own pick_pose and place_pose. | upstream_code | ROS/src/ur3_moveit/msg/UR3MoveitJoints.msg:1-8 |
| moveit_msgs/RobotTrajectory holds a trajectory_msgs/JointTrajectory joint_trajectory and a trajectory_msgs/MultiDOFJointTrajectory multi_dof_joint_trajectory. | upstream_code | ROS/src/moveit_msgs/msg/RobotTrajectory.msg:1-2 |
| The planner's joint names are shoulder_pan_joint, shoulder_lift_joint, elbow_joint, wrist_1_joint, wrist_2_joint and wrist_3_joint. | upstream_code | ROS/src/ur3_moveit/scripts/mover.py:21 |
| plan_pick_and_place converts joint_00 to joint_05 of the request from degrees to radians with math.radians to form the start configuration. | upstream_code | ROS/src/ur3_moveit/scripts/mover.py:66-73 |
| plan_trajectory sets the start state to the given joint angles, sets the destination pose as the pose target and returns the result of move_group.plan(). | upstream_code | ROS/src/ur3_moveit/scripts/mover.py:35-46 |
| Under Python 3, planCompat returns element 1 of the tuple that plan() returns. | upstream_code | ROS/src/ur3_moveit/scripts/mover.py:23-29 |
| plan_pick_and_place appends five plans, pre grasp, grasp, pick up, place and post place, each starting at the last point of the previous one, clears the pose targets and returns the response. | upstream_code | ROS/src/ur3_moveit/scripts/mover.py:75-110 |
| The grasp plan targets the pick pose lowered by 0.075 in z; the comment calls it a static value coming from Unity. | upstream_code | ROS/src/ur3_moveit/scripts/mover.py:81-84 |
| The post-place plan targets the place pose raised by 0.075 in z. | upstream_code | ROS/src/ur3_moveit/scripts/mover.py:101-104 |
| plan_pick_and_place first calls setup_scene. | upstream_code | ROS/src/ur3_moveit/scripts/mover.py:61-62 |
| setup_scene assigns a new MoveGroupCommander for the group arm to the module-global move_group, creates a PlanningSceneInterface and a RobotCommander, sleeps 2 s and adds a box named table of size (1.2, 1.8, 0.01) at z -0.02+0.77 in the planning frame. | upstream_code | ROS/src/ur3_moveit/scripts/mover.py:112-126 |
| The docstring says gripper behaviour is handled outside this trajectory planning: the gripper closes after the grasp position and opens after the place position. | upstream_code | ROS/src/ur3_moveit/scripts/mover.py:49-60 |
| The SRDF defines the group arm as the chain from base_link to ee_link. | upstream_code | ROS/src/ur3_moveit/config/ur3_with_gripper.srdf:12-14 |
| The SRDF's default group state of arm sets all six arm joints to 0. | upstream_code | ROS/src/ur3_moveit/config/ur3_with_gripper.srdf:42-49 |
| pose_est.launch loads params.yaml, includes demo.launch and starts server_endpoint.py, pose_estimation_script.py and mover.py. | upstream_code | ROS/src/ur3_moveit/launch/pose_est.launch:1-7 |
| demo.launch loads ur3_with_gripper.urdf as robot_description, includes ros_controllers.launch, spawns arm_controller and starts move_group.launch. | upstream_code | ROS/src/ur3_moveit/launch/demo.launch:3-18 |
| move_group.launch defaults allow_trajectory_execution to true and fake_execution to false. | upstream_code | ROS/src/ur3_moveit/launch/move_group.launch:16-17 |
| ros_controllers.yaml lists one controller with an empty name, action_ns follow_joint_trajectory, type FollowJointTrajectory and the six arm joints. | upstream_code | ROS/src/ur3_moveit/config/ros_controllers.yaml:1-11 |
| The documentation says the launch may report that the controller spawner process died and that this is safe to ignore once the final message is Ready to plan. | vendor_doc | Documentation/4_pick_and_place.md:211 |
| server_endpoint.py starts the ROS-TCP TcpServer with three routes: a UR3Trajectory subscriber, the ur3_moveit service as ur3_moveit, and the pose_estimation_service service as pose_estimation_srv. | upstream_code | ROS/src/ur3_moveit/scripts/server_endpoint.py:9-21 |
| The ROS-TCP endpoint reads its ROS_IP, ROS_TCP_PORT (default 10000), UNITY_IP and UNITY_SERVER_PORT (default 5005) parameters. | upstream_code | ROS/src/ros_tcp_endpoint/src/ros_tcp_endpoint/server.py:43-55 |
| The ROS-TCP endpoint's client thread reads one message per connection, routes it by destination name and, for a service, sends the response back on that connection and closes it. | upstream_code | ROS/src/ros_tcp_endpoint/src/ros_tcp_endpoint/client.py:142-186 |
| The ROS-TCP endpoint's RosService calls the ROS service up to three times on a ServiceException and returns None after any other exception. | upstream_code | ROS/src/ros_tcp_endpoint/src/ros_tcp_endpoint/service.py:35-61 |
| Unity's PublishJoints builds the MoverService request from the arm's current joint targets, the estimated cube position plus a pick offset and the goal position plus a place offset, and sends it to rosServiceName with TrajectoryResponse as the callback. | upstream_code | PoseEstimationDemoProject/Assets/TutorialAssets/Scripts/TrajectoryPlanner.cs:236-256 |
| TrajectoryPlanner's public field rosServiceName defaults to ur3_moveit. | upstream_code | PoseEstimationDemoProject/Assets/TutorialAssets/Scripts/TrajectoryPlanner.cs:32 |
| Unity's CurrentJointConfig fills joint_00 to joint_05 from the xDrive targets of the six arm articulation bodies. | upstream_code | PoseEstimationDemoProject/Assets/TutorialAssets/Scripts/TrajectoryPlanner.cs:222-234 |
| TrajectoryPlanner's fixed values are a 0.06 s joint assignment wait, a 0.5 s pose assignment wait, a gripper angle of 14, a pick offset of 0.255 and a place offset of 0.275 in Unity's y axis. | upstream_code | PoseEstimationDemoProject/Assets/TutorialAssets/Scripts/TrajectoryPlanner.cs:20-25 |
| TrajectoryResponse starts the ExecuteTrajectories coroutine when the response holds trajectories and otherwise logs an error and re-enables the buttons. | upstream_code | PoseEstimationDemoProject/Assets/TutorialAssets/Scripts/TrajectoryPlanner.cs:258-272 |
| ExecuteTrajectories writes each point's positions, converted with Rad2Deg, as the xDrive targets of the arm joints, waits after each point, closes the gripper after the grasp plan and opens it after the place plan. | upstream_code | PoseEstimationDemoProject/Assets/TutorialAssets/Scripts/TrajectoryPlanner.cs:288-333 |
| The pose estimation button handler captures the camera image and invokes the pose estimation service. | upstream_code | PoseEstimationDemoProject/Assets/TutorialAssets/Scripts/TrajectoryPlanner.cs:105-120 |
| InvokePoseEstimationService builds a sensor_msgs Image with encoding RGBA from the render texture and sends a PoseEstimationServiceRequest to pose_estimation_srv. | upstream_code | PoseEstimationDemoProject/Assets/TutorialAssets/Scripts/TrajectoryPlanner.cs:168-176 |
| pose_estimation_script.py advertises pose_estimation_service of type PoseEstimationService. | upstream_code | ROS/src/ur3_moveit/scripts/pose_estimation_script.py:102-109 |
| PoseEstimationService takes a sensor_msgs/Image image and returns a geometry_msgs/Pose estimated_pose. | upstream_code | ROS/src/ur3_moveit/srv/PoseEstimationService.srv:1-3 |
| _save_image writes each request image as a numbered PNG (Input<count>.png) under the package's images directory, creating the directory when it is missing. | upstream_code | ROS/src/ur3_moveit/scripts/pose_estimation_script.py:22-41 |
| The documentation runs roslaunch ur3_moveit pose_est.launch, then Play in Unity, then the Pose Estimation button; MoveIt returns trajectories to Unity, where the poses are executed. | vendor_doc | Documentation/4_pick_and_place.md:197-226 |
| The documented container publishes ports 10000 and 5005. | vendor_doc | Documentation/4_pick_and_place.md:77 |
| The Docker image builds from ros:noetic-ros-base. | upstream_code | docker/Dockerfile:1 |
| The Docker image installs ros-noetic-moveit and ros-noetic-rosbridge-suite among its apt packages. | upstream_code | docker/Dockerfile:5 |
| The Docker image copies the moveit_msgs, robotiq, ros_tcp_endpoint, universal_robot and ur3_moveit packages into the catkin workspace. | upstream_code | docker/Dockerfile:14-18 |
| The repository is licensed under the Apache License, Version 2.0. | vendor_doc | LICENSE:1-2 |

## Scope

The device served is the demo's MoveIt pick-and-place planner, the rospy service `ur3_moveit`
(`ur3_moveit/MoverService`, `ROS/src/ur3_moveit/scripts/mover.py:141`), reached through rosbridge as `/ur3_moveit`.
One capability, `x-cap.unity-technologies.pick_place_plan.v1`, sends the six start angles (degrees) and the pick
and place poses and returns the five planned trajectories (joint names and points per plan). It is declared a
command (verb `invoke`, exclusive on this endpoint; integrator v4, 2026-11-05), not a read: the callback plans and
returns, and its state changes are the table box it re-adds to MoveIt's planning scene before planning and the
module-global `MoveGroupCommander` it replaces (see below). Its ROS binding stays an observational call
(`operation: "read"`), because RosBridge refuses an effectful service command without an application success
predicate (`MoverService.srv:1-5` answers trajectories only) and an effectful ROS surface without an acknowledged stop
leaves every e-stop unreached, while nothing the call starts executes on any arm. Every input bound is
`operator_required`: the clone states the UR3 joint limits only in radians, -3.14159265359 to 3.14159265359 for each
arm joint (`ROS/src/ur3_moveit/URDF/ur3_with_gripper.urdf:361, 389, 417, 445, 473, 501`), while the request takes
degrees, and it states no workspace bound and no quaternion bound; `site-limits.example.json` is an example overlay. A
zero or non-finite quaternion and a non-finite angle or position are refused (`MHS.CAPABILITY.INPUT_INVALID`) before
the service is called.

PLAN ONLY. A planning call through rosbridge is answered to this endpoint and never to Unity. In the upstream
pipeline the trajectories are executed by Unity alone, in a coroutine that only the response to Unity's own request
starts (`TrajectoryPlanner.cs:255-264`, `:288-333`); the Unity scripts subscribe to no ROS topic and implement no
service, so nothing outside Unity can command, own or stop that execution. The receipt certifies a plan, never
motion; its `executed` output is always `false`.

One indirect effect remains. The node keeps its `MoveGroupCommander` in a module global that every call replaces
(`mover.py:112-116`), and rospy serves calls from different clients in parallel, so a planning call that overlaps
Unity's own planning call can mix this package's start state or targets into the plan that Unity then executes in its
simulation. The package serialises its own calls (the action is exclusive) but cannot see Unity's: plan only while
the Unity scene is not planning (its Pose Estimation button has not been pressed, or its pick-and-place has ended).

Stop: the profile's only command executes nothing, so the runtime's software latch is the whole safety path;
nothing this package sends can move anything. A pick-and-place that Unity started from its own button is not reached
by this endpoint's e-stop; it stops only in the Unity editor.

Risk: R1, the card's floor. The package commands no arm, simulated or real; by the hazard table it would be R0.

## Not covered

- The Unity scene (UR3 arm, Robotiq gripper articulation, cube, camera) and its coroutine execution: no external
  interface exists (`TrajectoryPlanner.cs` sends two service requests and nothing else over ROS-TCP).
- The pose estimation service `pose_estimation_service` (`pose_estimation_script.py:102-109`): its input is the full
  RGBA image that Unity renders inside its button handler and sends in its own request (`TrajectoryPlanner.cs:105-120`,
  `:168-176`); no ROS topic carries it, so this endpoint has no producer for it, and the SDK has no input route for a
  client-supplied image (see the RESULT notes).
- The ROS-TCP endpoint (`server_endpoint.py:9-21`, submodule `ros_tcp_endpoint` 0.2.0): Unity's transport. This
  package uses rosbridge, which the upstream image installs (`docker/Dockerfile:5`); the operator starts it.
- The vendored `universal_robot` (real UR drivers) and `robotiq` (real Robotiq gripper drivers) submodules: the
  upstream launch does not start them, and they are not this repository's device.

## Deployment notes for a live run (never run for this package)

Start the documented ROS side (`roslaunch ur3_moveit pose_est.launch`, `Documentation/4_pick_and_place.md:197-209`)
in the documented container (`:77` publishes ports 10000 and 5005), add a rosbridge websocket in the same ROS master
and publish its port, and point the `sim` deployment's `endpoint` at it. The service name assumes the documented
launch (no namespace). Plans of concurrent callers (Unity's own button, another client) share the node's global
`MoveGroupCommander` (`mover.py:112-116`) and can interleave (see Scope).

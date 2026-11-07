OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of an Anthropic MHS research preview.

# Facts and tags for gh.ifra-cranfield/ros2_robotsimulation

Every fact cites the pinned clone at commit `ee3a4de4cae38de3d83f3c925693bb417e6d047e`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| MoveJ creates the ROS 2 action server /MoveJ on the MoveJ_ActionServer node. | upstream_code | ros2_actions/scripts/moveJ_action.cpp:81-86 |
| MoveJ.action declares a JointPose goal, a float64 speed, a string result and a string feedback. | upstream_code | ros2_data/action/MoveJ.action:1-6 |
| JointPose.msg declares joint1 through joint6 as float64. | upstream_code | ros2_data/msg/JointPose.msg:1-6 |
| MoveJ multiplies each of the six goal joint values by k before assigning the MoveIt joint targets. | upstream_code | ros2_actions/scripts/moveJ_action.cpp:301-306 |
| MoveJ defines the degree-to-radian constant k = pi/180. | upstream_code | ros2_actions/scripts/moveJ_action.cpp:50-51 |
| MoveJ applies the goal speed with setMaxVelocityScalingFactor and 1.0 with setMaxAccelerationScalingFactor. | upstream_code | ros2_actions/scripts/moveJ_action.cpp:142-144 |
| MoveJ checks each goal joint against per-robot degree limits selected by the ROB_PARAM string before planning; the irb120, irb1200, irb6640, cr35ia, ur3, ur5 and ur10 branches are present. | upstream_code | ros2_actions/scripts/moveJ_action.cpp:163-289 |
| MoveJ plans with MoveIt, calls move(), then reports MoveJ:SUCCESS, MoveJ:FAILED or MoveJ:CANCELED; a planning failure still calls goal_handle->succeed with MoveJ:FAILED. | upstream_code | ros2_actions/scripts/moveJ_action.cpp:310-335 |
| MoveJ's cancel handler calls move_group_interface.stop() and accepts the cancellation. | upstream_code | ros2_actions/scripts/moveJ_action.cpp:117-128 |
| The MoveJ execute path checks is_canceling only after move() returns. | upstream_code | ros2_actions/scripts/moveJ_action.cpp:317-329 |
| MoveJs creates the ROS 2 action server /MoveJs with a JointPoseS goal and a float64 speed. | upstream_code | ros2_actions/scripts/moveJs_action.cpp:81-86 |
| MoveJs.action declares a JointPoseS goal, a float64 speed, a string result and a string feedback. | upstream_code | ros2_data/action/MoveJs.action:1-6 |
| JointPoseS.msg declares joint1 through joint7 as float64. | upstream_code | ros2_data/msg/JointPoseS.msg:1-7 |
| MoveXYZ creates the ROS 2 action server /MoveXYZ and includes the generated MoveXYZ action header. | upstream_code | ros2_actions/scripts/moveXYZ_action.cpp:80-85 |
| MoveXYZ sets an absolute target pose from positionx, positiony and positionz and keeps the current end-effector orientation. | upstream_code | ros2_actions/scripts/moveXYZ_action.cpp:163-172 |
| MoveXYZ reports MoveXYZ:SUCCESS, MoveXYZ:FAILED or MoveXYZ:CANCELED, and a planning failure still succeeds the goal with MoveXYZ:FAILED. | upstream_code | ros2_actions/scripts/moveXYZ_action.cpp:174-200 |
| MoveG creates the ROS 2 action server /MoveG and includes the generated MoveG action header. | upstream_code | ros2_actions/scripts/moveG_action.cpp:80-85 |
| MoveG checks the gripper goal against panda_gripper upper 0.04 and egp64 upper 0.025, both with lower 0.0, then assigns the goal to both gripper joints. | upstream_code | ros2_actions/scripts/moveG_action.cpp:150-175 |
| MoveG reports MoveG:SUCCESS, MoveG:FAILED or MoveG:CANCELED, and a planning failure still succeeds the goal with MoveG:FAILED. | upstream_code | ros2_actions/scripts/moveG_action.cpp:183-210 |
| The README states the speed value must be in (0, 1], with 1 the maximum velocity and 0 the invalid null velocity. | vendor_doc | ros2_actions/README.md:41 |
| The README describes /MoveJ as the 6-DOF joint-waypoint action and /MoveJs as its 7-DOF variant. | vendor_doc | ros2_actions/README.md:4-8 |
| The README describes the ROS 2 actions as executing robot and end-effector motions in Gazebo simulation. | vendor_doc | ros2_actions/README.md:2 |
| The Attacher action loops until a cancel request or a String True on /ros2_Detach, and returns an empty result; it exposes no stop service or stop action. | upstream_code | ros2_grasping/scripts/attacher_action.py:181-239 |
| The MoveJ server registration and cancel callback are its only stop-shaped control path: the callback calls move_group_interface.stop() and accepts cancellation. | upstream_code | ros2_actions/scripts/moveJ_action.cpp:81-128 |

## Scope

The package binds the four primary robot/end-effector action servers: `/MoveJ`
and `/MoveJs` for joint waypoints in degrees, `/MoveXYZ` for an absolute
Cartesian position with the current orientation, and `/MoveG` for a parallel
gripper opening. The action servers run in a Gazebo and MoveIt 2 simulation
launched by the repository's per-robot packages; this driver does not launch
Gazebo, MoveIt, a robot node or rosbridge.

`/MoveJ`, `/MoveJs`, `/MoveXYZ`, `/MoveG`, `/MoveL`, `/MoveR`, `/MoveROT`,
`/MoveRP`, `/MoveYPR` and `/MoveXYZW` are all ROS 2 actions. This package binds
the first four because they are the primary joint, absolute Cartesian and
gripper controls; the other motion variants remain unbound and are not replaced
by an observation-only surface. The `Attacher` action is also unbound: it is a
pose-replication loop with an empty result and no independent terminal
success field.

The speed field uses the README's `(0, 1]` interval. The joint and Cartesian
values have no driver-side limit because the upstream server checks the joint
limits of the robot selected by its `ROB_PARAM` parameter, and the robot model
is a deployment choice rather than a fixed device. `/MoveG` likewise checks the
selected gripper model's own upper bound.

## Safety and blocker

The pinned action servers expose no pause, stop, hold, reset or safe-state
service or action. The only stop-shaped path is the action cancel callback,
which calls `move_group_interface.stop()` and accepts the cancellation. The
RosDriver contract does not accept action cancellation as an acknowledged stop
binding. No safe-state action is fabricated, so a stock `mhs.safety.estop`
reports `MHS.SAFETY.SAFE_STATE_UNREACHED` and the package is recorded as blocked
on `HELPER_MISSING`. The fake is a ROS-free F0 recording and does not prove a
real stop, a real ROS graph or any hardware behaviour.

## Tags

`ros`, `ros2`, `simulation`, `gazebo`, `moveit`, `robot-arm`, `gripper`,
`ifra`, `cranfield`

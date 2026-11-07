# Facts and tags for gh.shouryash007/robothon-2026

Every fact cites the pinned clone at commit
`32a2722fda7758d5ea85101a240b11aa55f4e3f0`.  `vendor_doc` refs name a text file of the
clone; `upstream_code` refs name `path/in/clone:LINE`.  The same facts are written into
`driver.py` (`facts = [...]`); the generated reference is built from the driver, not
from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The README's primary command launches so101_gazebo.launch.py with moveit:=follower. | vendor_doc | README.md:2 |
| The README runs object_detector.py against the Gazebo graph with use_sim_time:=true. | vendor_doc | README.md:6 |
| The README bridges /d435i/image as sensor_msgs/msg/Image from a Gazebo Image message. | vendor_doc | README.md:4 |
| object_detector.py imports JointTrajectory and JointTrajectoryPoint from trajectory_msgs.msg. | upstream_code | hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/object_detector.py:5 |
| object_detector.py creates a publisher on the absolute /arm_controller/joint_trajectory topic with queue size 10. | upstream_code | hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/object_detector.py:14 |
| The scanning message names shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll and gripper in that order and sets six positions and a time_from_start.sec of 4. | upstream_code | hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/object_detector.py:30-38 |
| move_to_scanning_pose publishes the same message ten times with 0.1 s sleeps, then sleeps 5.0 s before setting scanning_complete. | upstream_code | hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/object_detector.py:41-48 |
| execute_grasp builds nine trajectory points with time_from_start.sec values from 3 through 20 and publishes the message once. | upstream_code | hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/object_detector.py:77-138 |
| object_detector.py subscribes to /d435i/image as sensor_msgs/Image. | upstream_code | hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/object_detector.py:27 |
| so101_gazebo config/controllers.yaml defines arm_controller as a joint_trajectory_controller/JointTrajectoryController over shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll and gripper. | upstream_code | hackathon_ws/hackathon_ws/src/so101_gazebo/config/controllers.yaml:9-20 |
| so101.urdf declares a ros2_control system with the gazebo_ros2_control/GazeboSystem plugin and loads libgazebo_ros2_control with the so101_gazebo config/controllers.yaml. | upstream_code | hackathon_ws/hackathon_ws/src/so101_description/urdf/so101.urdf:515-549 |
| The MoveIt so101_new_calib.urdf.xacro includes so101.urdf, instantiates its ros2_control macro as GazeboSimSystem and loads libgz_ros2_control-system with so101_moveit_config config/ros2_controllers.yaml. | upstream_code | hackathon_ws/hackathon_ws/src/so101_moveit_config/config/so101_new_calib.urdf.xacro:5-35 |
| ros2_controllers.yaml gives arm_controller the five joints shoulder_pan through wrist_roll and a separate gripper_controller the gripper joint. | upstream_code | hackathon_ws/hackathon_ws/src/so101_moveit_config/config/ros2_controllers.yaml:23-44 |
| With moveit:=follower the launch includes the MoveIt rsp and move_group launches with use_sim_time true. | upstream_code | hackathon_ws/hackathon_ws/src/so101_gazebo/launch/so101_gazebo.launch.py:245-260 |
| The arm_controller configuration sets open_loop_control true. | upstream_code | hackathon_ws/hackathon_ws/src/so101_gazebo/config/controllers.yaml:25 |
| The launch resolves robot_controllers to the so101_gazebo config/controllers.yaml path. | upstream_code | hackathon_ws/hackathon_ws/src/so101_gazebo/launch/so101_gazebo.launch.py:118-119 |
| The launch starts controller_manager/ros2_control_node with the robot_controllers parameter file. | upstream_code | hackathon_ws/hackathon_ws/src/so101_gazebo/launch/so101_gazebo.launch.py:204-211 |
| The launch spawns joint_state_broadcaster, arm_controller and gripper_controller with the robot_controllers parameter file. | upstream_code | hackathon_ws/hackathon_ws/src/so101_gazebo/launch/so101_gazebo.launch.py:271-282 |
| The URDF names the model so101_new_calib. | upstream_code | hackathon_ws/hackathon_ws/src/so101_description/urdf/so101.urdf:4 |
| The URDF gives shoulder_pan a revolute range of -1.91986..1.91986 rad. | upstream_code | hackathon_ws/hackathon_ws/src/so101_description/urdf/so101.urdf:495-500 |
| The URDF gives shoulder_lift a revolute range of -1.74533..1.74533 rad. | upstream_code | hackathon_ws/hackathon_ws/src/so101_description/urdf/so101.urdf:474-479 |
| The URDF gives elbow_flex a revolute range of -1.69..1.69 rad. | upstream_code | hackathon_ws/hackathon_ws/src/so101_description/urdf/so101.urdf:453-458 |
| The URDF gives wrist_flex a revolute range of -1.65806..1.65806 rad. | upstream_code | hackathon_ws/hackathon_ws/src/so101_description/urdf/so101.urdf:431-436 |
| The URDF gives wrist_roll a revolute range of -2.74385..2.84121 rad. | upstream_code | hackathon_ws/hackathon_ws/src/so101_description/urdf/so101.urdf:410-415 |
| The URDF gives gripper a revolute range of -0.174533..1.74533 rad. | upstream_code | hackathon_ws/hackathon_ws/src/so101_description/urdf/so101.urdf:389-394 |
| so101_gazebo_bridge.py publishes to /arm_controller/joint_trajectory and /gripper_controller/joint_trajectory with JointTrajectory messages. | upstream_code | hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/so101_gazebo_bridge.py:18-26 |
| The teleop bridge names five arm joints and one gripper joint separately. | upstream_code | hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/so101_gazebo_bridge.py:30-31 |
| process_command fills a missing arm joint with 0.0, publishes the arm only when at least one arm key was present, and publishes the gripper independently. | upstream_code | hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/so101_gazebo_bridge.py:72-106 |
| So101GazeboBridge.stop only clears its running flag and closes the UDP socket; it has no controller or trajectory stop call. | upstream_code | hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/so101_gazebo_bridge.py:108-110 |
| MoveIt's simple controller configuration names arm_controller and gripper_controller with type FollowJointTrajectory and action_ns follow_joint_trajectory, but writes no resolved ROS action endpoint or type. | upstream_code | hackathon_ws/hackathon_ws/src/so101_moveit_config/config/moveit_controllers.yaml:10-25 |
| pick_place_test.py builds a MoveGroup goal in send_goal but never calls an asynchronous send method, and run_test only calls send_goal. | upstream_code | hackathon_ws/hackathon_ws/src/so101_gazebo/scripts/pick_place_test.py:20-51 |
| The so101_gazebo package manifest declares Apache-2.0. | upstream_code | hackathon_ws/hackathon_ws/src/so101_gazebo/package.xml:8 |
| The so101_moveit_config package manifest declares BSD. | upstream_code | hackathon_ws/hackathon_ws/src/so101_moveit_config/package.xml:11 |

## Scope

The selected interface is the upstream's own six-joint trajectory publication on
`/arm_controller/joint_trajectory` (`object_detector.py:14,30-38`).  The so101_gazebo
`controllers.yaml` configures that controller as a
`joint_trajectory_controller/JointTrajectoryController` over the six joints in the same
order (`controllers.yaml:9-20`) with `open_loop_control: true` (`controllers.yaml:25`); see
the model-review paragraph below for the second configuration.  The driver fixes `joint_names` to that order and maps one
`points` input array to the native `trajectory_msgs/msg/JointTrajectory.points` field.
The receipt says `published=true` and `confirmed=false`: a rosbridge topic publication
does not prove controller receipt, interpolation, motion, arrival or a stopped state.

`palletizing_fetch.py` uses the same topic with a different pose sequence; it is not a
separate endpoint and is not exposed as another capability.  The teleop bridge publishes
a five-joint arm message and a separate one-joint gripper message
(`so101_gazebo_bridge.py:18-31`).

Model review (2026-11-05): the author's claim that "the launched Gazebo path uses
`controllers.yaml`" and that `/gripper_controller` has no controller is not established by
the clone. With `moveit:=follower` the robot description comes from the MoveIt xacro, which
includes `so101.urdf` (a `gazebo_ros2_control/GazeboSystem` system and the Gazebo Classic
plugin loading `controllers.yaml`, `so101.urdf:515-549`) and adds a
`gz_ros2_control/GazeboSimSystem` system with the gz plugin loading `ros2_controllers.yaml`
(`so101_new_calib.urdf.xacro:5-35`), whose `arm_controller` has the five arm joints and whose
separate `gripper_controller` has the gripper (`ros2_controllers.yaml:23-44`). The launch also
starts a standalone `ros2_control_node` with `controllers.yaml` (`so101_gazebo.launch.py:204-211`)
and spawns `gripper_controller`, which `controllers.yaml` does not define (`:271-282`). Which
configuration the running `arm_controller` has is decided by ros2_control at run time; the
six-joint trajectories of `object_detector.py` and of this package match only the six-joint
one, the teleop bridge's five-joint messages only the five-joint one. The MoveIt configuration names `FollowJointTrajectory` with an `action_ns`
(`moveit_controllers.yaml:10-26`) but never writes the resolved action endpoint or the
`control_msgs` type, and `pick_place_test.py` builds a `MoveGroup` goal without sending
it (`pick_place_test.py:20-51`); neither is declared here.

NOT COVERED: the `/d435i/image` image stream (the upstream detector consumes it;
image capture would need the SDK's artifact path), the object detector's autonomous
grasp logic, `/joint_states`, TF, `/clock`, the MoveIt planning/execution actions,
the 20 water-particle models, the container and marking spawns, and the UDP teleop
port.  No image, depth or camera metadata is exposed.

## Limits

The six position bounds are the revolute travel ranges written in the pinned URDF
(`so101.urdf:389-394,410-415,431-436,453-458,474-479,495-500`), in the controller's joint order.  They are the
installed model's ranges, not a measurement of a delivered arm.  The clone states the
upstream script's individual `time_from_start.sec` values (3 through 20) but no
controller or site bound for a `builtin_interfaces/Duration`; `sec` and `nanosec` are
therefore `Limit.operator_required`.  Without an operator overlay every call that sets
them is refused with `MHS.SAFETY.LIMITS_UNSET`.  `site-limits.example.json` supplies
example-only test values; the deployed site supplies its own motion envelope.

## Safety

The device is a robot arm and is declared R2.  No source-backed stop, pause,
cancellation, controller switch or safe-state service or action exists in the pinned
clone.  `So101GazeboBridge.stop` only clears the UDP listener's running flag and closes
its socket (`so101_gazebo_bridge.py:108-110`); it does not stop a trajectory the external
`joint_trajectory_controller` has already accepted.  The Gazebo world-control service
and the controller-manager switch service are outside the clone and are not bridged by
the upstream launch.  The package therefore declares no e-stop or safe-state binding
and makes no stopped-state claim; the runtime software latch only refuses new
publications.  It is blocked rather than presenting that latch or a publication as an
independent stop.

## Fidelity contract

`driver.py` describes the deployed recording fake: engine
`analytic:ROS recording fake (no Gazebo physics)`, level F0, determinism `none`,
`timestep_ms: 0`, `realtime_factor: 0`, reset `none`, no snapshot/restore.  The fake
answers the declared `/arm_controller/joint_trajectory` advertisement and publication
with a recorded message and no controller; it runs no Gazebo, `gz_ros2_control`,
controller manager, MoveIt or ROS graph.  It performs no interpolation, timing,
dynamics, gravity, collision or controller error behavior.

## Tags

`ros`, `ros2`, `gazebo`, `simulation`, `robot-arm`, `trajectory`

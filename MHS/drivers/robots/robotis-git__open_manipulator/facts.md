OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Source facts for gh.robotis-git/open_manipulator

Pinned commit: `d31000d90c679af9c982e73de8b12d777c5ff7dd`. Source declarations and controlled fake evidence do not prove native execution.

| Fact | Source | Reference |
|---|---|---|
| KeyboardController creates a JointTrajectory publisher on /arm_controller/joint_trajectory. | upstream_code | `open_manipulator_teleop/open_manipulator_teleop/omx_f_teleop.py:41-43` |
| KeyboardController creates a GripperCommand action client on /gripper_controller/gripper_cmd. | upstream_code | `open_manipulator_teleop/open_manipulator_teleop/omx_f_teleop.py:46-47` |
| KeyboardController subscribes to /joint_states with sensor_msgs/JointState. | upstream_code | `open_manipulator_teleop/open_manipulator_teleop/omx_f_teleop.py:51-52` |
| KeyboardController uses the five arm joint names joint1 through joint5. | upstream_code | `open_manipulator_teleop/open_manipulator_teleop/omx_f_teleop.py:56-62` |
| The teleop hardcodes demo gripper travel constants gripper_max 1.1 and gripper_min 0.0. | upstream_code | `open_manipulator_teleop/open_manipulator_teleop/omx_f_teleop.py:64-66` |
| The teleop hardcodes demo max_effort 10.0 for the gripper command. | upstream_code | `open_manipulator_teleop/open_manipulator_teleop/omx_f_teleop.py:121` |
| send_arm_command publishes a one-point JointTrajectory and does not wait for controller execution. | upstream_code | `open_manipulator_teleop/open_manipulator_teleop/omx_f_teleop.py:108-116` |
| send_gripper_command sends a GripperCommand goal and waits only for the send future, not the terminal result. | upstream_code | `open_manipulator_teleop/open_manipulator_teleop/omx_f_teleop.py:118-126` |
| The bringup executor imports control_msgs.action.FollowJointTrajectory. | upstream_code | `open_manipulator_bringup/open_manipulator_bringup/joint_trajectory_executor.py:22` |
| The bringup executor defaults action_topic to /arm_controller/follow_joint_trajectory. | upstream_code | `open_manipulator_bringup/open_manipulator_bringup/joint_trajectory_executor.py:44` |
| The bringup executor's goal_response_callback logs a rejected goal and returns without requesting a result. | upstream_code | `open_manipulator_bringup/open_manipulator_bringup/joint_trajectory_executor.py:126-133` |
| shutdown_node requests goal cancellation only when a goal handle exists, does not await it, then destroys the node and exits. | upstream_code | `open_manipulator_bringup/open_manipulator_bringup/joint_trajectory_executor.py:185-190` |
| The omx_f controller manager configures arm_controller as a JointTrajectoryController and gripper_controller as a GripperActionController. | upstream_code | `open_manipulator_bringup/config/omx_f/hardware_controller_manager.yaml:9-13` |
| The arm_controller declares joint1 through joint5 and the gripper_controller declares gripper_joint_1. | upstream_code | `open_manipulator_bringup/config/omx_f/hardware_controller_manager.yaml:18-39` |
| The omx_f arm xacro gives each of joint1 through joint5 the same revolute limit block: velocity 4.8, effort 1000, lower -pi*2.0 and upper pi*2.0. | upstream_code | `open_manipulator_description/urdf/omx_f/omx_f_arm.urdf.xacro:37-177` |
| gripper_joint_1 is revolute and its model limit block gives velocity 4.8, effort 1000, lower -pi*2.0 and upper pi*2.0. | upstream_code | `open_manipulator_description/urdf/omx_f/omx_f_arm.urdf.xacro:207-212` |
| The omx_f ros2_control description starts with disable_torque_at_init=true. | upstream_code | `open_manipulator_description/ros2_control/omx_f.ros2_control.xacro:25` |
| The omx_f ros2_control description names the relative torque service dynamixel_hardware_interface/set_dxl_torque. | upstream_code | `open_manipulator_description/ros2_control/omx_f.ros2_control.xacro:30` |
| QNode::init creates a std_srvs::srv::SetBool client named dynamixel_hardware_interface/set_dxl_torque. | upstream_code | `open_manipulator_gui/src/omx_f/qnode.cpp:75-76` |
| QNode::sendTorqueSrv sets request->data from its checked argument and calls async_send_request, but logs success and returns true without waiting for or checking the service response. | upstream_code | `open_manipulator_gui/src/omx_f/qnode.cpp:302-314` |
| QNode::stopMotion sets a GUI flag and calls MoveGroupInterface::stop locally in the GUI process. | upstream_code | `open_manipulator_gui/src/omx_f/qnode.cpp:280-289` |
| resetStopRequest only clears the GUI's stop_requested_ flag. | upstream_code | `open_manipulator_gui/src/omx_f/qnode.cpp:297-300` |

## Scope, limits and safety

The full five-joint arm action, gripper action, JointState observation and ordinary torque-off request remain. FollowJointTrajectory application error_code!=0 and GripperCommand reached_goal=false are tested after valid transport completion, in addition to the original transport failure controls.

The same arm xacro includes gripper_joint_1 as revolute at207 and a numeric position/velocity/effort block at212: lower -2*pi, upper 2*pi, velocity4.8, effort1000. These are model declarations, not proof of installed gripper travel or controller effort mapping. The gripper keeps stricter operator-required position/effort bounds; teleop 0.0..1.1 and max_effort10.0 remain demo values. The example overlay remains illustrative.

The positions-only arm point has no explicit time_from_start. max_duration_ms is an RPC wait bound, not trajectory timing. The selected bringup executor generates timed position/velocity/acceleration points at joint_trajectory_executor.py:195-244, while teleop topic points use zero time. A separately pinned controller profile and timing/motion-envelope decision remain required; this package makes no universal claim that every controller rejects the current point.

The GUI source proves a SetBool client and immediate local return, not the external dynamixel_hardware_interface server's retirement semantics. Torque disable cannot establish support for a gravity-loaded arm. Torque-off is therefore an ordinary request without safe_state permission or e-stop binding. The full stock gate is deliberately blocked at G3.NO_ESTOP/G3.NO_SAFE_STATE. A fake service flag is not native stop evidence. The GUI's local MoveGroup stop and flag reset are not fabricated as ROS endpoints.

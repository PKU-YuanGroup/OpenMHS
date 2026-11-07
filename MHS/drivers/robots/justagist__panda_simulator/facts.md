OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.justagist/panda_simulator

Every fact cites its source at commit `6cec91dcc739df105a845e2f29e361b6c608bb48`: `vendor_doc` (a
text file of the clone) or `upstream_code` (`path/in/clone:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the driver, not
from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The controllers launch loads the gripper controller configuration and spawns panda_simulator/panda_gripper_controller when load_gripper is true. | upstream_code | panda_sim_controllers/launch/panda_sim_controllers.launch:29-34 |
| The gripper controller configuration uses type panda_sim_controllers/PandaGripperController, the pub_topic /franka_gripper/joint_states and the two finger joints panda_finger_joint1 and panda_finger_joint2. | upstream_code | panda_sim_controllers/config/panda_gripper_controller.yaml:2-12 |
| The controller constructor initializes the homing, stop, move and grasp action servers on /franka_gripper/homing, /franka_gripper/stop, /franka_gripper/move and /franka_gripper/grasp. | upstream_code | panda_sim_controllers/src/panda_gripper_controller.cpp:38-58 |
| init() starts the homing, stop, move and grasp action servers and creates a 0.1 s ROS timer that calls timerUpdate. | upstream_code | panda_sim_controllers/src/panda_gripper_controller.cpp:146-166 |
| The controller includes franka_gripper/GraspAction.h, HomingAction.h, MoveAction.h and StopAction.h. | upstream_code | panda_sim_controllers/src/panda_gripper_controller.cpp:28-31 |
| init() advertises sensor_msgs/JointState with queue size 1 and latch true on the pub_topic parameter through the private node handle when pub_topic is set, and otherwise on the absolute /franka_gripper/joint_states. | upstream_code | panda_sim_controllers/src/panda_gripper_controller.cpp:153-164 |
| timerUpdate copies the two finger positions into the JointState message, sets zero velocities and zero efforts, sets no header field and publishes it. | upstream_code | panda_sim_controllers/src/panda_gripper_controller.cpp:170-185 |
| The move handler clamps width/2 to the main finger joint's URDF lower and upper limits and the speed to plus or minus its URDF velocity limit, writes both command buffers, sets new_command_, then loops without sleeping for up to 5 s of ros::Time until the sum of the two absolute finger positions is within 0.01 of the goal width, and sets the goal succeeded or, on timeout, aborted. | upstream_code | panda_sim_controllers/src/panda_gripper_controller.cpp:228-262 |
| The grasp handler applies the same clamping, command-buffer writes and 5 s ros::Time wait as move, reads only the goal's width and speed (not force or epsilon), and sets the goal succeeded or aborted. | upstream_code | panda_sim_controllers/src/panda_gripper_controller.cpp:292-325 |
| The stop handler sets the position command buffer to half the sum of the two absolute measured finger positions and the speed command buffer to 0.0, sets new_command_, and then sets the goal succeeded with success true without any condition. | upstream_code | panda_sim_controllers/src/panda_gripper_controller.cpp:273-288 |
| update() calls updateCommands() on every fifth call and updates both finger controllers on every call; updateCommands() returns at once unless new_command_ is set, and otherwise applies the buffered position and speed to the main finger and the URDF mimic multiplier and offset to the other finger. | upstream_code | panda_sim_controllers/src/panda_gripper_controller.cpp:187-225 |
| Each finger's JointPositionController computes its effort command on every update from the position error and, when the command carries a velocity, from the difference between that velocity and the joint velocity. | upstream_code | panda_sim_controllers/src/panda_joint_position_controller.cpp:202-253 |
| The homing handler only logs 'Homing not implemented for simulator.' and sets no goal status itself. | upstream_code | panda_sim_controllers/src/panda_gripper_controller.cpp:269-271 |
| The move wait loop compares ros::Time::now() minus its start time with the 5 s timeout and the measured width with the goal width, and contains no is_preempt_requested check. | upstream_code | panda_sim_controllers/src/panda_gripper_controller.cpp:242-258 |
| The grasp wait loop compares ros::Time::now() minus its start time with the 5 s timeout and the measured width with the goal width, and contains no is_preempt_requested check. | upstream_code | panda_sim_controllers/src/panda_gripper_controller.cpp:306-321 |
| The simulator configuration declares default_speed 0.1 m/s and default_grasp_epsilon inner/outer 0.005 m. | upstream_code | panda_gazebo/config/robot_details.yaml:74-81 |
| init() reads the default_speed parameter into a local variable initialized to 0.1 and logs it when the parameter is found. | upstream_code | panda_sim_controllers/src/panda_gripper_controller.cpp:141-144 |
| panda_world.launch declares load_gripper and use_custom_action_servers with default true. | upstream_code | panda_gazebo/launch/panda_world.launch:5-6 |
| panda_world.launch declares use_sim_time with default true. | upstream_code | panda_gazebo/launch/panda_world.launch:12 |
| panda_world.launch starts start_gripper_action_server.py as gripper_action_server_emulator when use_custom_action_servers and load_gripper are true. | upstream_code | panda_gazebo/launch/panda_world.launch:76-81 |
| GripperActionServer serves control_msgs GripperCommandAction on the relative name franka_gripper/gripper_action and creates a franka_interface.GripperInterface for panda_finger_joint1 and panda_finger_joint2. | upstream_code | panda_sim_custom_action_server/src/panda_sim_custom_action_server/gripper_action_server.py:36-57 |
| While a GripperCommand goal runs, its callback calls GripperInterface.move_joints with twice the goal position at a 20 Hz rospy.Rate until the first finger reaches the goal, a preemption is requested or the timeout passes. | upstream_code | panda_sim_custom_action_server/src/panda_sim_custom_action_server/gripper_action_server.py:75-117 |

## Scope

The package serves the simulated Franka Hand gripper through the C++ `PandaGripperController` in
`panda_sim_controllers`: `move`, `grasp` and the fixed `stop` action, plus
`/franka_gripper/joint_states`. The action names are absolute in the constructor
(`panda_gripper_controller.cpp:45-56`), so the declared root endpoints match the upstream strings.

The `homing` action is deliberately not bound: its handler only logs that homing is not implemented
for the simulator and never calls `setSucceeded` or `setAborted` itself (`panda_gripper_controller.cpp:269-271`). The grasp handler ignores the goal's `force` and `epsilon` fields and
performs the same width/speed position move as `move`; the driver sends fixed zero values for those
required goal fields and exposes no force input. The move and grasp wait loops do not check
`is_preempt_requested` (`panda_gripper_controller.cpp:242-258`, `306-321`), so the actions are declared
non-cancellable even though the underlying actionlib servers exist.

The seven-joint arm trajectory server, the arm joint-command topic, the arm state topics and MoveIt are
**NOT COVERED**. The pinned clone exposes no acknowledged arm stop service and no fixed arm stop action.
The arm trajectory server's preempt callback calls `franka_interface`'s `exit_control_mode()` but the SDK
does not accept action cancellation as a safety stop and cannot confirm quiescence; a whole-arm driver
would therefore have to invent a stop path. The gripper is served because its upstream StopAction is an
acknowledged stop of the simulated gripper.

The endpoint names are those of franka_ros's real `franka_gripper` node; franka_ros is listed in
`dependencies.rosinstall` and is not part of the clone. Pointed at a real Franka ROS graph, these bindings
would drive the real hand, including grasps with the fixed zero force and epsilon.

`panda_world.launch` starts, by default, `gripper_action_server_emulator`: a `control_msgs`
`GripperCommandAction` server on `franka_gripper/gripper_action` whose callback re-commands the fingers
through `franka_interface.GripperInterface` at 20 Hz while its goal runs. It is not served; a goal sent to
it by MoveIt or another client keeps commanding the fingers after an MHS stop.

## Limits

The clone clamps the finger command to the URDF joint limits but does not state their numeric values in a
text file; `default_speed` is a configurable ROS parameter, not a device bound. The gripper opening and
speed are therefore `Limit.operator_required`: every move or grasp call is refused
`MHS.SAFETY.LIMITS_UNSET` until the operator supplies `site-limits.json`. `site-limits.example.json` is an
example overlay with example values, not a device fact; a deployment must use its own reviewed bounds.

## Safety

The device is simulated at R2. The fixed, input-free `/franka_gripper/stop` action is both the native
e-stop and the declared safe-state action. Its handler writes a hold into the controller's command
buffers, a position target of half the sum of the two absolute measured finger positions and a speed
target of zero, and sets the goal succeeded with `success=true` without any condition
(`panda_gripper_controller.cpp:273-288`). The controller applies the buffered command on the next
`update()` that runs `updateCommands()` (every fifth control update, `187-225`), and each finger's effort
PID then holds that opening (`panda_joint_position_controller.cpp:202-253`). The acknowledgement therefore
precedes the hold; nothing senses that the fingers stopped. Gazebo keeps running and the arm is not
stopped.

A move or grasp goal that is still running is not interrupted: its callback keeps waiting for up to 5 s of
`ros::Time` (simulated time under the default `use_sim_time`, so without end while Gazebo is paused) and
ignores cancellation. An e-stop during such a goal sends the stop, but the runtime cannot confirm the safe
state while the goal is unresolved: it reports `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held (the
`hold_goals` test case). A later move or grasp goal from any ROS client, including one queued behind a
running goal in the same action server, replaces the hold; the MHS latch fences only this driver. The
action servers keep answering while a controller switch has stopped the gripper controller, when a stop is
acknowledged without effect. This is a stop of the simulated gripper, not a physical emergency stop. After
an e-stop, commands are refused until `mhs.safety.reset` clears the latch. The fake's stop result is
synthesized and does not prove physical quiescence, a hardware run or a ROS graph.

## Fidelity

The fake is an analytic ROS-free stand-in, not a recording of captured traffic. Engine
`analytic:ROS-free rosbridge stand-in (no Gazebo physics)`, level F0, determinism `none`,
`timestep_ms: 0`, `realtime_factor: 0`, reset `none`, no snapshot/restore. It answers the declared
actionlib and joint-state wire traffic but runs no Gazebo, ros_control, franka_interface or physics. Its
finger positions and action results are placeholders; a successful move or grasp sets both placeholder
finger positions to `width/2` immediately, while the upstream handler waits up to 5 s of ROS time and
clamps to the URDF limits. Like the pinned controller, the fake sends no `PREEMPTED` result for a cancel
request; its `hold_goals` switch keeps move and grasp goals running to exercise an e-stop during a goal.
`/franka_gripper/joint_states` is latched and published by a ROS timer that stops while Gazebo is paused;
a reviewer probe with a silent topic showed reads failing `MHS.DEVICE.NOT_READY` after 2 s and each command
waiting that long for the resource read. The arm's interfaces are not served. No ROS graph, Gazebo process, simulator run or
hardware was executed or validated.

## Tags

`ros`, `ros1`, `gazebo`, `franka`, `panda`, `gripper`, `simulation`

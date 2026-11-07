OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of an Anthropic research preview.

# Facts and tags for gh.anhtuduong/ur5legovision

Every fact cites the pinned clone at commit `7cf487fbadcfd42e2fe09f75c7345d24920a1e3d`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| UR5Controller imports MoveJoints and MoveTo from ros_impedance_controller.srv. | upstream_code | motion/ur5_controller.py:72 |
| UR5Controller imports generic_float from ros_impedance_controller.srv. | upstream_code | motion/ur5_controller.py:71 |
| UR5Controller registers the absolute service /ur5/move_joints with the MoveJoints type. | upstream_code | motion/ur5_controller.py:308 |
| UR5Controller registers the absolute service /ur5/move_to with the MoveTo type. | upstream_code | motion/ur5_controller.py:309 |
| UR5Controller registers the absolute service /ur5/move_gripper with the generic_float type. | upstream_code | motion/ur5_controller.py:310 |
| MoveJoints.srv declares request fields dt, v_des and q_des and response field bool success. | upstream_code | locosim/ros_impedance_controller/srv/MoveJoints.srv:1-5 |
| MoveTo.srv declares request fields pose_target, dt and v_des and response field bool success. | upstream_code | locosim/ros_impedance_controller/srv/MoveTo.srv:1-5 |
| generic_float.srv declares request field data and response field bool ack. | upstream_code | locosim/ros_impedance_controller/srv/generic_float.srv:1-3 |
| The move_joints callback gets a MoveIt trajectory and calls move_joints for every trajectory point, returning False when planning fails and True after the loop. | upstream_code | motion/ur5_controller.py:523-542 |
| The move_joints loop advances q_des by dt * v_ref * e / \|\|e\|\| and stops only when \|\|e\|\| is below 0.001; the loop has no cancellation, deadline or operator-stop check. | upstream_code | motion/ur5_controller.py:635-644 |
| The move_gripper callback creates ros.Rate(1/self.dt), then loops, sending the arm reference and sleeping on the rate, until any filtered desired gripper joint is within 0.0001 of the target; a TODO to handle a timeout follows the loop. | upstream_code | motion/ur5_controller.py:589-604 |
| move_joints creates ros.Rate(1/dt) and sleeps on it in every loop iteration. | upstream_code | motion/ur5_controller.py:621-644 |
| UR5Controller creates ServiceProxy objects for /gazebo/pause_physics and /gazebo/unpause_physics with the std_srvs/Empty type. | upstream_code | motion/ur5_controller.py:237-238 |
| UR5Controller imports Empty from std_srvs.srv. | upstream_code | motion/ur5_controller.py:63 |
| UR5Controller subscribes to /ur5/joint_states with the JointState type. | upstream_code | motion/ur5_controller.py:244-246 |
| UR5Controller imports JointState from sensor_msgs.msg. | upstream_code | motion/ur5_controller.py:64 |
| UR5Controller publishes /ur5/ee_pose with the geometry_msgs.msg.Pose type. | upstream_code | motion/ur5_controller.py:302 |
| The configured arm joint order is shoulder_pan_joint, shoulder_lift_joint, elbow_joint, wrist_1_joint, wrist_2_joint, wrist_3_joint. | upstream_code | locosim/robot_control/base_controllers/params.py:17 |
| The UR5e joint_limit_params file states per-joint min_position and max_position for the six arm joints: [-6.14, 6.14], [-3.14, 0], [-3.14, 3.14], [-6.28, 6.28], [-6.28, 6.28], [-6.28, 6.28]. | upstream_code | locosim/robot_descriptions/ur_description/config/ur5e/joint_limits.yaml:10-80 |
| The configured control period dt is 0.001 s. | upstream_code | locosim/robot_control/base_controllers/params.py:12 |
| The simulated motion client sets v_des to 0.6. | upstream_code | motion/main.py:53-56 |
| The controller's simulated v_des branch sets 0.6; the real-robot branch sets 0.2. | upstream_code | motion/ur5_controller.py:108-115 |
| ros_impedance_controller_ur5.launch includes gazebo_ros empty_world.launch with paused default true and use_sim_time default true. | upstream_code | locosim/ros_impedance_controller/launch/ros_impedance_controller_ur5.launch:58-67 |
| ros_impedance_controller_ur5.launch defaults joint_limit_params to the ur5e joint_limits.yaml. | upstream_code | locosim/ros_impedance_controller/launch/ros_impedance_controller_ur5.launch:26 |
| The shipped UR5 parameters set real_robot to False. | upstream_code | locosim/robot_control/base_controllers/params.py:20 |
| startRealRobot kills rviz, gzserver and gzclient, logs STARTING REAL ROBOT and exits unless the ROS master is online and '/' + robot_name + '/ur_hardware_interface' is a running node. | upstream_code | motion/ur5_controller.py:141-164 |
| For the real robot the gripper manager opens a TCP socket to 192.168.0.100 port 30002 to send a gripper script; for the simulated robot it only sets the desired finger joints. | upstream_code | locosim/robot_control/base_controllers/components/gripper_manager.py:64-100 |
| The upstream motion client in motion/main.py creates service clients for /ur5/move_joints, /ur5/move_to and /ur5/move_gripper, after waiting for /ur5/move_joints, /ur5/move_to and the relative move_gripper. | upstream_code | motion/main.py:67-72 |

## Scope

The package is a configuration-only ROS 1 `RosDriver`; the upstream node,
rosbridge, Gazebo and MoveIt are run by the operator. The declared surface is
`/ur5/move_joints`, `/ur5/move_gripper`, `/ur5/joint_states`, `/ur5/ee_pose`,
`/gazebo/pause_physics` and `/gazebo/unpause_physics`. `/ur5/move_to`, the ZED
camera topics, MoveIt planning, force/torque and the other Gazebo model
services are NOT COVERED. The driver does not start or validate a ROS graph.

The joint-position action sends the six-joint array to the service with fixed
`dt` 0.001 s and `v_des` 0.6, the upstream simulated client's configured
values. These are deployment request values, not device limits. The gripper
diameter has no stated mechanical bound, so its input is
`Limit.operator_required`: calls are refused with `MHS.SAFETY.LIMITS_UNSET`
until an operator supplies a reviewed overlay.

The two observation actions are explicit subscriptions; they are deliberately
not automatic resource reads. A paused live topic may go silent, and the
runtime must not block a pause/resume receipt on a held sample. The main
resource snapshot is empty.

## Safety

The device is simulated at R2. The input-free `pause` action and the
`/gazebo/pause_physics` service are the declared stop path. The clone declares
the proxy but never calls it, contains no stop callback, does not cancel the
`/ur5/move_joints` or `/ur5/move_gripper` service loops and publishes no
stopped-state measurement. The acknowledgement therefore proves only that the
simulator service replied; it is not sensed quiescence and not a hardware
emergency stop. Both motion loops sleep on a `ros.Rate` and the shipped launch
sets `use_sim_time`, so a paused world holds an interrupted loop where it is,
and an unpause lets it continue its old motion. After an e-stop the runtime
latches and refuses ordinary commands; `mhs.safety.reset` clears only the latch
and leaves the simulation paused (there is no reset binding, SAFE-042). The
`resume` action is an ordinary command, refused while latched; it unpauses
Gazebo, after which an interrupted motion continues. While paused, a new motion
call waits until a resume or its binding timeout.

The same node also has a real-robot path: with `real_robot` set in the upstream
parameters (the shipped value is `False`) it drives a UR5 through
`ur_robot_driver` and sends gripper scripts over TCP to `192.168.0.100:30002`.
No Gazebo exists there, so this package's e-stop fails with
`MHS.SAFETY.SAFE_STATE_UNREACHED` and the latch held, and nothing upstream
stops the arm; a hardware deployment needs a human review and an independent
physical stop. The upstream motion client (`motion/main.py`) calls the same motion
services; running it beside MHS adds a second commander that the MHS latch does
not fence.

## Fidelity contract

`driver.py` describes the deployed fake: engine `analytic:ROS contract fake (no
physics)`, level F0, determinism `none`, `timestep_ms: 0`, `realtime_factor: 0`,
reset `none`, no snapshot/restore. The fake answers canned observations and
service replies in plain state; it runs no physics, controller or planner, and
it answers motion calls at once even while "paused", where the upstream waits
for a resume. The gaps disclose the missing simulator, the placeholder values,
the untraced Gazebo pause, the wait of paused motion callbacks and the resumed
motion after an unpause, the paused start of the shipped launch, the real-robot
path, the upstream bare-boolean callback mismatch and the explicit observation
choice.

## Tags

`ros`, `ros1`, `ur5`, `robot-arm`, `lego`, `gazebo`, `moveit`, `joint-state`

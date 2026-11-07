OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.caelan/ltamp

Every fact cites the pinned clone at commit `7e0a28dca1156b1dc6d3b9459fed58607249c3ed`. The same facts are in
`driver.py` (`facts = [...]`); the reference file is generated from the driver.

Tags: `pybullet`, `pr2`, `robot arm`, `simulation`, `task and motion planning`.

Author: Claude (claude-opus-5-5, a model and not a human), 2026-11-05, re-authoring the blocked DeepSeek package
(user decision of 2026-11-05: Claude authors, Claude Sonnet reviews). Model-written; `reviewed_by` is null.

## Facts

| fact | source | ref |
|---|---|---|
| ROSWorld(sim_only=True) skips rospy.init_node, connects a PyBullet client, switches real-time simulation off and builds PBPerception and PBController. | upstream_code | plan_tools/ros_world.py:16-38 |
| ROSWorld sets PyBullet's real-time simulation to 0 for its client. | upstream_code | plan_tools/ros_world.py:27 |
| ROSWorld loads the PR2 from the models directory with a fixed base and places its base link at the origin. | upstream_code | plan_tools/ros_world.py:51-60 |
| ROSWorld.stop resets the simulation, removing bodies and constraints, and disconnects the client. | upstream_code | plan_tools/ros_world.py:77-95 |
| PBController starts with execute_motor_control false. | upstream_code | control_tools/pb_controller.py:20-26 |
| execute_motor_control selects motor control in command_torso and rest_for_duration, and is read again for every waypoint of follow_trajectory. | upstream_code | control_tools/pb_controller.py:72-148 |
| get_joint_positions and set_joint_positions read and set the named joints of the robot through pybullet_tools. | upstream_code | control_tools/pb_controller.py:47-56 |
| command_torso always sets the torso lift joint position kinematically, and also calls control_joint with the same position when execute_motor_control is true. | upstream_code | control_tools/pb_controller.py:72-80 |
| follow_trajectory steps the simulation through joint_controller_hold2 for each waypoint when execute_motor_control is true, up to max_sim_duration simulated seconds per waypoint, and otherwise sets the joint positions of each waypoint. | upstream_code | control_tools/pb_controller.py:103-148 |
| command_arm calls command_arm_trajectory with one waypoint and its timeout as the time from start. | upstream_code | control_tools/pb_controller.py:150-162 |
| The upstream executor calls command_arm with timeout=1.0. | upstream_code | control_tools/execution.py:94 |
| Controller defines the seven arm joints of each arm, the four finger joints of each gripper, the torso lift joint and the two head joints. | upstream_code | control_tools/controller.py:8-17 |
| get_arm_positions returns get_joint_positions of the arm's joint names. | upstream_code | control_tools/controller.py:39-40 |
| PR2_JOINT_SAFETY_LIMITS lists the PR2 safety_controller soft limits taken from the PR2 URDF. | upstream_code | control_tools/common.py:11-36 |
| The PR2 URDF declares r_forearm_roll_joint and r_wrist_roll_joint continuous. | upstream_code | models/pr2_description/pr2.urdf:2148-2304 |
| The PR2 URDF declares l_forearm_roll_joint and l_wrist_roll_joint continuous. | upstream_code | models/pr2_description/pr2.urdf:3143-3299 |
| The upstream's simulation runner sets execute_motor_control true and enables gravity before it executes a plan. | upstream_code | plan_tools/run_simulation.py:77-81 |

## Scope

The card's override names `ROSWorld` and `PBController`; this package is a decorated direct `Driver` with
`native = control_tools.pb_controller:PBController` (the card's `PythonObjectDriver` helper cannot declare the
e-stop below; DEVIATION FROM THE CARD in RESULT.json). It replaces the earlier package over the retired real-PR2
`ROSController`.

| capability | upstream | note |
|---|---|---|
| `joint_positions` (state read) | `get_arm_positions("l")`, `get_arm_positions("r")` | 14 angles, left arm then right arm in `Controller.LEFT_ARM`/`RIGHT_ARM` order |
| `torso_position` (state read and write) | `get_joint_positions(["torso_lift_joint"])`, `command_torso(value)` | the write is read back |
| `cap.motion.joint_position.v1` | `command_arm("l", ...)`, then `command_arm("r", ...)` with `timeout=1.0` | `reached` compares the read-back with the command within follow_trajectory's goal tolerance, 5e-3·π rad (pb_controller.py:104) |

Not covered: grippers (`command_gripper` sets four finger joints to one "width" value whose unit the clone does not
state consistently, pb_controller.py:170-175 and controller.py:84-88), head, attachments, perception, planning and
plan execution, `rest_for_duration`, gravity.

## Limits

The ten bounded arm elements carry the PR2 safety-controller soft limits of `control_tools/common.py:19-23` (right
arm) and `26-30` (left arm), which match the `safety_controller` lines of the URDF the world loads
(`models/pr2_description/pr2.urdf`, for example 1976). The forearm-roll and wrist-roll elements (indices 4, 6, 11, 13)
are continuous joints and carry no bound. The torso write is bounded by `common.py:14` (0.0115-0.325 m). A package case
steps each of the ten arm bounds just past it on both sides (refused) and onto it (accepted), with the numbers written
out from `common.py` rather than imported from the driver.

## Safety and stop

R1, simulated, fake-only. The e-stop sets `PBController.execute_motor_control` to false and reads it back after the
runtime latched; every command also refuses to run while that flag is set. With the flag false and real-time
simulation off (ros_world.py:27), the upstream advances nothing outside a call, and each command of this driver sets
joint positions kinematically (pb_controller.py:145-146), so after the latch the simulated PR2 stays where the last
command left it. The flag is the only switch that makes PBController use motor control or step the physics
(command_torso's call of control_joint, pb_controller.py:77-78; the step_simulation loops, 83-101 and 124-143); its
motor-control loops do not check for a stop, which is why commands refuse to run with it set. Each command, the arm
move and the torso write, checks for cancellation and makes its kinematic set under a lock the e-stop also takes, so no
set happens after the e-stop returns (package cases check both).

The stop covers this endpoint's calls only. Any other holder of the same `ROSWorld` or `PBController` in the process can
still set the flag or step the world (the upstream's plan runner sets `execute_motor_control` true and executes a plan,
plan_tools/run_simulation.py:77-81), so a backend that builds the world must keep it private to the endpoint.

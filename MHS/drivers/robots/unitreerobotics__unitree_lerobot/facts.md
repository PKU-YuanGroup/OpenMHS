# Facts and tags for gh.unitreerobotics/unitree_lerobot

Every fact cites the pinned clone at `41c2805742de879ddab2d8d6beaeaf215f876395`; the `ref` is a path from the clone
root and a line or line range. `upstream_code` is code or a comment of the clone; `vendor_doc` is documentation text of
the clone. The reference file is generated from `driver.py`, not from this page.

## Device and transport

| fact | source | ref |
|---|---|---|
| The module defines the topic names rt/lowcmd, rt/arm_sdk and rt/lowstate | upstream_code | unitree_lerobot/eval_robot/robot_control/robot_arm.py:19-21 |
| The controller publishes LowCmd on rt/arm_sdk when motion_mode is true and on rt/lowcmd otherwise | upstream_code | unitree_lerobot/eval_robot/robot_control/robot_arm.py:97-100 |
| The controller subscribes to LowState on rt/lowstate | upstream_code | unitree_lerobot/eval_robot/robot_control/robot_arm.py:102 |
| The constructor joins DDS domain 1 in simulation mode and domain 0 on the real robot | upstream_code | unitree_lerobot/eval_robot/robot_control/robot_arm.py:92-95 |
| After initializing the DDS endpoints and starting the subscriber thread, the constructor blocks until the first LowState message arrives; the loop has no timeout | upstream_code | unitree_lerobot/eval_robot/robot_control/robot_arm.py:101-113 |
| The control period is control_dt = 1/250 s | upstream_code | unitree_lerobot/eval_robot/robot_control/robot_arm.py:85 |
| The clip is current_q + delta / max(motion_scale, 1.0) with motion_scale = max(abs(delta)) / (velocity_limit * control_dt) | upstream_code | unitree_lerobot/eval_robot/robot_control/robot_arm.py:166-171 |
| The constructor starts the publisher thread as a daemon | upstream_code | unitree_lerobot/eval_robot/robot_control/robot_arm.py:147-151 |
| The publisher loops indefinitely, reads the stored arm targets and writes LowCmd at the control period; it does not check for a stop acknowledgement | upstream_code | unitree_lerobot/eval_robot/robot_control/robot_arm.py:173-204 |
| The constructor enables motor modes and position gains for all G1 joints, including the non-arm joints | upstream_code | unitree_lerobot/eval_robot/robot_control/robot_arm.py:127-145 |
| ctrl_dual_arm stores q_target and tauff_target under ctrl_lock and returns nothing; it sends no command of its own | upstream_code | unitree_lerobot/eval_robot/robot_control/robot_arm.py:208-212 |
| G1_29_JointArmIndex lists the left arm joints 15 to 21 and the right arm joints 22 to 28, in that order | upstream_code | unitree_lerobot/eval_robot/robot_control/robot_arm.py:290-307 |
| get_current_dual_arm_q returns the fourteen arm joint positions and get_current_dual_arm_dq their velocities from the subscribed LowState buffer | upstream_code | unitree_lerobot/eval_robot/robot_control/robot_arm.py:222-228 |
| ctrl_dual_arm_go_home sets q_target to zeros and waits up to 100 attempts of 0.05 s for the joints to come within 0.05 rad of zero; it is a move to the home pose, not a stop | upstream_code | unitree_lerobot/eval_robot/robot_control/robot_arm.py:230-249 |
| The class defines no stop, disable, brake or emergency method | upstream_code | unitree_lerobot/eval_robot/robot_control/robot_arm.py:69-287 |
| The controller's arm_velocity_limit starts at 20.0; this is a controller setting, not the joint travel range | upstream_code | unitree_lerobot/eval_robot/robot_control/robot_arm.py:84 |
| speed_instant_max sets arm_velocity_limit to 30.0 | upstream_code | unitree_lerobot/eval_robot/robot_control/robot_arm.py:257-259 |
| The publisher's gradual-speed branch uses a hard-coded 5 s ramp from 20.0 to 30.0 | upstream_code | unitree_lerobot/eval_robot/robot_control/robot_arm.py:197-199 |
| The package imports unitree_sdk2py for the DDS channel, the IDL messages and the CRC | upstream_code | unitree_lerobot/eval_robot/robot_control/robot_arm.py:6-13 |
| pyproject.toml leaves the unitree_sdk2py dependency commented out, so the clone does not install the DDS transport | upstream_code | pyproject.toml:21 |
| EvalRealConfig defaults arm to G1_29 | upstream_code | unitree_lerobot/eval_robot/utils/utils.py:125 |
| setup_robot_interface constructs the selected arm controller with motion_mode and simulation_mode | upstream_code | unitree_lerobot/eval_robot/make_robot.py:94 |
| The README describes eval_robot as the real-machine inference verification of the model | vendor_doc | README.md:49 |

## Limits

| input | rule | reason |
|---|---|---|
| `cap.motion.joint_position.v1` `joint_positions` | `Limit.operator_required` | The clone states no joint travel range for the G1 arms: `q_target` starts at zeros and the range is left to the robot and the deployment (`robot_arm.py:72-73`). The operator supplies the range in `site-limits.json`; `site-limits.example.json` is an example only. |

## Tags

`robot arm`, `humanoid`, `dual arm`, `joint control`, `dds`, `unitree`, `g1`

## Stop and safe state

The upstream setter only stores a target; its daemon publishes it without a stop acknowledgement. The e-stop makes a
best-effort request for the last buffered arm positions with zero feedforward torque, then fails with
`MHS.SAFETY.SAFE_STATE_UNREACHED` and the latch held. The undated LowState buffer may be stale, and the publisher can
already have copied an older target before the request. `hold_position` is an ordinary action, not a safe-state action,
and is refused while latched. This package is blocked on `NO_HARDWARE_FREE_PATH`.

Construction enables motor modes and PD gains for the whole body (`robot_arm.py:127-145`), then starts publishing with
an initially zero arm target (`robot_arm.py:72-73,147-151`). The constructor's DDS wait has no timeout. Neither the
hand entry `Dex3_1_Controller` nor the serial `UnitreeMotorSDK` entry is served by this arm package. The clone documents
no independent physical stop for the selected controller. Only the fake contract was exercised; no robot was run.

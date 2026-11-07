# Facts and tags for gh.tonyzhaozh/aloha

Every fact cites the pinned clone at commit
`06369f03cd8e0a47e16d3a90167853fd33af7557`.  `upstream_code` refs name
`path/in/clone:LINE`; `vendor_doc` refs name a text file of the clone.  The
same facts are written into `driver.py` (`facts = [...]`); `REFERENCE.md` is
generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| RealEnv documents a flat action of six left-arm joint positions, one normalized left-gripper position (0 close, 1 open), six right-arm joint positions and one normalized right-gripper position (0 close, 1 open). | upstream_code | aloha_scripts/real_env.py:21-24 |
| RealEnv.step splits the flat action in half, sends the first six values of each half to the left and right arm set_joint_positions, sends the last value of each half to set_gripper_pose, sleeps DT and returns a dm_env TimeStep. | upstream_code | aloha_scripts/real_env.py:127-140 |
| RealEnv.get_qpos reads six arm positions from each recorder, normalizes the measured gripper position at recorder index 7, and returns left arm, left gripper, right arm and right gripper in that order. | upstream_code | aloha_scripts/real_env.py:57-64 |
| RealEnv.get_qvel and get_effort read the same recorder streams; qvel takes six arm values and the normalized gripper velocity, and get_effort returns the first seven values per side. | upstream_code | aloha_scripts/real_env.py:66-80 |
| RealEnv.get_images returns the ImageRecorder's camera image dictionary. | upstream_code | aloha_scripts/real_env.py:82-83 |
| The README says the launch starts communication with 4 robots and 4 cameras. | vendor_doc | README.md:43-44 |
| The launch file starts usb_cam nodes with image_width 640, image_height 480 and framerate 60. | upstream_code | launch/4arms_teleop.launch:90-140 |
| RealEnv.set_gripper_pose converts each normalized value with PUPPET_GRIPPER_JOINT_UNNORMALIZE_FN and publishes a JointSingleCommand on each puppet. | upstream_code | aloha_scripts/real_env.py:85-92 |
| PUPPET_GRIPPER_POSITION_OPEN is 0.05800 and PUPPET_GRIPPER_POSITION_CLOSE is 0.01844 in the left-finger position constants; the cited lines do not state a unit. | upstream_code | aloha_scripts/constants.py:18-22 |
| PUPPET_GRIPPER_POSITION_NORMALIZE_FN maps a measured gripper position to (x - close) / (open - close). | upstream_code | aloha_scripts/constants.py:33 |
| RealEnv.reset reboots both gripper motors, moves both arms to START_ARM_POSE, and opens then closes both grippers when fake is false. | upstream_code | aloha_scripts/real_env.py:94-125 |
| RealEnv constructs both puppet arms as InterbotixManipulatorXS robot_model vx300s with group arm and gripper gripper. | upstream_code | aloha_scripts/real_env.py:40-44 |
| The puppet mode configs enable torque and set the arm group to position control and the gripper single to linear_position control. | upstream_code | config/puppet_modes_left.yaml:3-17 |
| The Recorder subscribes to /puppet_<side>/joint_states as sensor_msgs/JointState and to /puppet_<side>/commands/joint_group and /puppet_<side>/commands/joint_single as interbotix_xs_msgs JointGroupCommand and JointSingleCommand. | upstream_code | aloha_scripts/robot_utils.py:96-98 |
| The launch file defaults robot_model_master to wx250s and robot_model_puppet to vx300s. | upstream_code | launch/4arms_teleop.launch:3-4 |
| The launch file includes interbotix_xsarm_control for each master and puppet arm. | upstream_code | launch/4arms_teleop.launch:23-62 |
| The README warns that the robot will collapse if motors are torque off because the joints have no automatically engaged brakes. | vendor_doc | README.md:51 |
| The README instructs lowering the robots with sleep.py before cutting off power. | vendor_doc | README.md:177-179 |

## Scope and interface

The upstream entry point is a Python environment object, not a ROS node with
declared services.  `RealEnv` owns two Interbotix `vx300s` puppet arms and
their grippers.  The primary interface is `RealEnv.step(action)`: the flat
action order is six left-arm joint positions, one normalized left-gripper
position, six right-arm joint positions and one normalized right-gripper
position (`aloha_scripts/real_env.py:21-24`, `:127-140`).  The driver exposes
that interface as `x-cap.tonyzhaozh.step.v1`, plus the environment reset as
`x-cap.tonyzhaozh.reset.v1`. The retained `x-cap.tonyzhaozh.hold.v1`
action is explicitly unavailable and always fails without native commands.
This is a blocked attempted control package, not a complete integration.  The joint observation is exposed as resource
reads; the write `gripper_pose` sends the two normalized gripper positions to
`RealEnv.set_gripper_pose`.

The camera images are not carried by this package.  `RealEnv.get_images`
returns four camera arrays, and the launch configures them at 480 by 640
(`aloha_scripts/real_env.py:82-83`, `launch/4arms_teleop.launch:93-94`).  This
package has not implemented an artifact output path for those arrays. Their
omission is an unresolved NEEDS_ARTIFACTS scope gap, not a limitation of the
standard or a completed substitute for the upstream observation.  The fake's 2 x 2 x 3 images are placeholders only.

## Limits

| path | bound | source | ref / reason |
|---|---|---|---|
| `gripper_pose[*]` | 0.0 to 1.0 normalized | upstream_code | aloha_scripts/real_env.py:22 |
| `x-cap.tonyzhaozh.step.v1` `left_gripper` | 0.0 to 1.0 normalized | upstream_code | aloha_scripts/real_env.py:22 |
| `x-cap.tonyzhaozh.step.v1` `right_gripper` | 0.0 to 1.0 normalized | upstream_code | aloha_scripts/real_env.py:24 |
| `x-cap.tonyzhaozh.step.v1` `left_arm[*]` | operator_required | none | the pinned clone states no vx300s joint-travel limits; the installed arm and its Interbotix configuration define them |
| `x-cap.tonyzhaozh.step.v1` `right_arm[*]` | operator_required | none | the pinned clone states no vx300s joint-travel limits; the installed arm and its Interbotix configuration define them |

The normalized gripper range is stated in the clone's action and observation
docstring (`aloha_scripts/real_env.py:22`, `:24`).  The arm joint-travel
bounds are not stated anywhere in the clone: the config files set operating
modes and torque only, the constants file gives the start pose and the
gripper normalization, and the Interbotix model description is outside this
repository.  Those paths therefore use `Limit.operator_required`; without an
operator overlay the runtime refuses every step call with
`MHS.SAFETY.LIMITS_UNSET`.  `site-limits.example.json` contains *example*
operator bounds, not device facts; an operator must replace them with the
installed arm's envelope before a hardware run.

## Safety: BLOCKED

This R2 arm package has no effective native stop and no declared achieved safe
state. The previous cached-position hold has been removed from `@estop` and
from `safe_state=True`. The remaining hold action always raises
`MHS.SAFETY.SAFE_STATE_UNREACHED` without sending a native command. E-stop can
latch new commands in software, but supplies no native stop confirmation.
The SDK serves backend=fake in simulated mode and can report a completed
software-only latch there (including safe_state_achieved=true); that is fake
latch evidence only. The reference has native=null and an empty achieved_by
list. Hardware construction is unavailable, so no hardware stop receipt is
claimed. No hold, torque-off or physical stop success is claimed.

The source publishes left-arm, right-arm, left-gripper and right-gripper
commands sequentially (`aloha_scripts/real_env.py:127-139`, `:85-92`). Its
reset reboots grippers and runs arm/gripper publication loops
(`aloha_scripts/real_env.py:94-125`, `aloha_scripts/robot_utils.py:142-160`).
A check before and after `RealEnv.step` cannot interrupt publications inside
that call; the original reset wrapper had no cancellation check at all.
Controlled events around those source-ordered publications demonstrated that
the old wrapper reported a completed e-stop with `safe_state_achieved=true`
before the running step sent three more commands, or reset sent 248 more
commands. Reset even returned `completed` after being listed as cancelled.
These are deterministic wrapper counterexamples, not live robot measurements.

`RealEnv.get_qpos` reads the recorder caches without testing sample freshness
(`aloha_scripts/real_env.py:57-64`); `Recorder` stores incoming position,
velocity and effort arrays (`aloha_scripts/robot_utils.py:105-111`). The old
hold returned success while the controlled native still reported nonzero
velocities. It neither awaited a fresh measurement nor established stopped
motion. Measured gripper normalization uses finger-position index 7, whereas
commands use joint unnormalization (`real_env.py:62-63`, `:85-92`); feeding the
normalized observation back is not source evidence of exact motor-position
holding. The README warns that torque-off collapses the unbraked arms
(`README.md:51`), so disabling torque is not an acceptable invented repair.

The input-free reset also bypasses the operator-required arm fields of the
step action. It completed without any arm overlay and with a narrow +/-0.1
rad overlay while sending the upstream START_ARM_POSE, including -0.96 and
1.16 rad (`aloha_scripts/constants.py:16`). The original control declarations
remain for fake investigation; this bypass has not been repaired or accepted.

The hardware factory now refuses unconditionally before any upstream import,
ROS initialization or robot construction, including if a human signature is
later supplied. `reviewed_by` remains null and the original DeepSeek model
author is unchanged. To unblock: implement source-backed interruption and
publication ordering against every running command path, confirm stopping
from fresh correlated feedback, constrain every reset trajectory target to
the operator envelope, and add concurrent/negative tests. A signature, a
passing instantaneous fake, or different safety prose cannot supply these
missing mechanisms. The four image outputs also need an artifact path.

The controlled reproduction and full receipts are private audit artifacts:
`work/handoff-runs/mhs-build-20261102/ros-readiness/aloha_stop_repro.py` and
`aloha-stop-repro-results.json` in the same directory. The pre-review package
is preserved under
`work/handoff-runs/ros-wave-first2/reviewer-originals/tonyzhaozh__aloha/`.
No hardware, live ROS, upstream import or upstream execution was used.

## Fake fidelity

The fake is a ROS-free in-memory model at F0.  It has no physics, no ROS
graph, no Interbotix node, no camera and no wall-clock pacing.  Its joint
positions, velocities, efforts and 2 x 2 x 3 camera arrays are placeholders;
the real camera arrays are 480 x 640 x 3 (`launch/4arms_teleop.launch:93-94`).
The fake's `step` assigns the commanded arm and gripper positions immediately
and reports zero velocities; it does not model arm dynamics, collisions,
gripper contact, the `DT` sleep or image capture.  Its `reset` returns the
placeholder start state. It does not model concurrent source-ordered command
publication or stale recorder feedback, so its original idle stop tests did
not establish native stopping. No trajectory or state-hash replay is claimed.

## Source-backed card correction

The original card named `family: ros` and `helper: RosDriver`. The regenerated
card now selects `family: python-object` and `helper: PythonObjectDriver`
through a registry override. The confirmed entry
symbol is the Python class `aloha_scripts.real_env:RealEnv`, not a ROS node
endpoint: the clone's own ROS access is inside `Recorder` and `ImageRecorder`
subscriptions (`aloha_scripts/robot_utils.py:96-98`) and inside the external
Interbotix SDK.  The clone declares no ROS service at all.  A `RosDriver`
would have to invent a stop service or use a zero-velocity publication, which
the ROS helper explicitly does not accept as an acknowledged emergency stop,
and no single rosbridge command can carry the environment's two-arm,
two-gripper step.  This package therefore uses a direct `Driver` over the
upstream class, preserving the attempted `RealEnv.step` scope. Review found
that its software hold did not meet the stop contract; the package remains
blocked. A direct wrapper is valid in principle only after its native safety
semantics are established. Changing the card/helper alone cannot resolve this.

## Tags

`aloha`, `bimanual`, `teleoperation`, `interbotix`, `vx300s`, `ros1`,
`manipulation`

## Installation and identity

No installation was run. The pinned README documents ROS 1 Noetic and
`catkin_make`, not the former generic `pip install .` / `colcon build` hints
(`README.md:24-40`). The lock now leaves installation commands empty. The
external Interbotix SDK and requested edit of its `arm.py` are not pinned by
this repository. The original factory's bare module import and configurable
source path did not verify that the imported modules matched the source pin;
a future hardware factory must resolve that identity and dependency gap too.

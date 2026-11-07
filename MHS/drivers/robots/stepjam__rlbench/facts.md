# Facts and tags for gh.stepjam/rlbench

Every fact cites its source at commit `02720bba4c73fe02eb75df946b8791b806028a9d`: `upstream_code` for code or a
comment of the clone, `vendor_doc` for documentation text.  The same facts are written into `driver.py`
(`facts = [...]`); `reference.json` is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| RLBenchEnv is a Gymnasium environment: class RLBenchEnv(gym.Env) | upstream_code | rlbench/gym.py:20 |
| The state observation mode disables all high-dimensional observations and enables all low-dimensional ones | upstream_code | rlbench/gym.py:31-33 |
| The wrapper constructs the RLBench Environment headless, launches it and gets the requested task environment from it | upstream_code | rlbench/gym.py:44-50 |
| The observation space is a Dict built from the first observation: an rgb member is a Box bounded 0 to 255 and every other member a Box bounded -inf to inf, with the observation's shape and dtype | upstream_code | rlbench/gym.py:61-70 |
| The action space is a Box of action_mode.action_bounds() with the shape of Environment.action_shape | upstream_code | rlbench/gym.py:72-74 |
| The extracted state observation keeps joint_velocities, joint_positions, joint_forces, gripper_open, gripper_pose, gripper_joint_positions, gripper_touch_forces and task_low_dim_state, and wraps a scalar in an array of one | upstream_code | rlbench/gym.py:76-93 |
| reset seeds numpy's global generator, reads options['reset_to_demo'] when present, resets the task environment and returns the extracted observation with the text descriptions | upstream_code | rlbench/gym.py:101-114 |
| step delegates to the task environment and returns (observation, reward, terminated, False, {}) | upstream_code | rlbench/gym.py:116-118 |
| The default action mode is JointPositionActionMode, which uses JointPosition(False) delta joint positions for the arm and absolute GripperJointPosition(True) for the gripper | upstream_code | rlbench/action_modes/action_mode.py:59-61 |
| The default action mode applies the arm and gripper targets, steps the scene once and then re-applies the post-step targets | upstream_code | rlbench/action_modes/action_mode.py:63-71 |
| JointPositionActionMode.action_bounds returns 7 arm deltas in [-0.1, 0.1] and one gripper value in [0.0, 0.04] | upstream_code | rlbench/action_modes/action_mode.py:77-79 |
| The Panda entry of SUPPORTED_ROBOTS has 7 joints | upstream_code | rlbench/const.py:38-39 |
| GripperJointPosition repeats the single gripper action for both joints and uses it as the absolute target | upstream_code | rlbench/action_modes/gripper_action_modes.py:128-136 |
| TaskEnvironment.step returns the scene observation, float(success) as the reward and the task's terminate flag | upstream_code | rlbench/task_environment.py:100-109 |
| ReachTarget's task_low_dim_state is the 3-element target position | upstream_code | rlbench/tasks/reach_target.py:46-48 |
| The Gymnasium ids are built at import time as rlbench/{task_name}-{obs_mode}-v0 with entry point rlbench.gym:RLBenchEnv and nondeterministic=True | upstream_code | rlbench/__init__.py:36-48 |
| Scene.step calls the PyRep simulator step and then the task step | upstream_code | rlbench/backend/scene.py:314-316 |
| RLBench is built around CoppeliaSim v4.1.0 and PyRep | vendor_doc | README.md:64 |
| The optional gym extra installs gymnasium==1.0.0a2 | upstream_code | setup.py:44-46 |

Limits: the driver declares none.  The only numeric inputs are the two `cap.world.*` fields the bridge derives from
the environment: `ticks` (1 to the bridge's `max_ticks`, 10000 by default) and the `action.values` array, whose
per-element bounds come from the environment's action space (the fake's Box mirrors
`rlbench/action_modes/action_mode.py:77-79`: seven arm deltas in [-0.1, 0.1] and one gripper value in [0.0, 0.04]).
The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `rlbench:reach_target-state-v0`, level F0 (kinematic
interface stand-in: no dynamics, contacts, forces, sensors or rendering), determinism `seeded` with `seed_control`
`parameter`, `timestep_ms` 0 (the clone publishes no fixed physics interval and the environment exposes no `dt`),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore.  The gaps say what is not modelled and
that the fake was never compared with the upstream environment.

Safety: simulated R0 device.  The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: rlbench, robot-manipulation, reach-target, reinforcement-learning, simulation, gymnasium

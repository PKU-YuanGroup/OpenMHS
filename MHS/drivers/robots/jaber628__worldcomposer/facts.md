# Facts and tags for gh.jaber628/worldcomposer

Every fact cites its source at commit `c2de3a2c9b3cc0f91e2bf739e5e6a24742988da2`: `upstream_code` (code of the clone)
or `vendor_doc` (a text file of the clone). The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The task is registered as WorldComposer-Tableware-v0 with entry point Tableware:TablewareEnv and TablewareEnvCfg as its environment configuration | upstream_code | source/WorldComposer/WorldComposer/tasks/Task01_Tableware/__init__.py:3-9 |
| TablewareEnv subclasses DirectRLEnv imported from isaaclab.envs, so the Gymnasium base, the action and observation space objects and the episode time limit live in the external Isaac Lab package | upstream_code | source/WorldComposer/WorldComposer/tasks/Task01_Tableware/Tableware.py:9-17 |
| TablewareEnv takes the environment configuration cfg and an optional render_mode | upstream_code | source/WorldComposer/WorldComposer/tasks/Task01_Tableware/Tableware.py:20 |
| The task config sets decimation 1, episode_length_s 60, action_scale 1.0, action_space 6, observation_space 6 and state_space 0 | upstream_code | source/WorldComposer/WorldComposer/tasks/Task01_Tableware/Tableware_cfg.py:17-22 |
| The simulation step is dt = 1/120 s, with render_interval equal to decimation 1 | upstream_code | source/WorldComposer/WorldComposer/tasks/Task01_Tableware/Tableware_cfg.py:25 |
| The robot is an SO101 follower whose default joint positions are shoulder_pan -0.0363, shoulder_lift -1.7135, elbow_flex 1.4979, wrist_flex -1.5, wrist_roll -0.085 and gripper -0.01176 | upstream_code | source/WorldComposer/WorldComposer/tasks/Task01_Tableware/Tableware_cfg.py:27-39 |
| The SO101 action joint order is shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper | upstream_code | source/WorldComposer/WorldComposer/assets/robots/lerobot.py:17-24 |
| _pre_physics_step multiplies the action by action_scale and _apply_action sets it as the robot joint position target | upstream_code | source/WorldComposer/WorldComposer/tasks/Task01_Tableware/Tableware.py:97-101 |
| _get_observations returns a dict with the applied action and the six joint positions under the keys action and observation.state | upstream_code | source/WorldComposer/WorldComposer/tasks/Task01_Tableware/Tableware.py:103-113 |
| _get_rewards returns 0 for the Tableware task | upstream_code | source/WorldComposer/WorldComposer/tasks/Task01_Tableware/Tableware.py:133-135 |
| The episode ends when episode_length_buf reaches max_episode_length - 1, and the same time-out flag is returned as both terminated and truncated | upstream_code | source/WorldComposer/WorldComposer/tasks/Task01_Tableware/Tableware.py:137-139 |
| Camera observations are added only when task_config.teleop.enable_cameras is true: top and wrist RGB and, unless disable_depth is true, depth images | upstream_code | source/WorldComposer/WorldComposer/tasks/Task01_Tableware/Tableware.py:115-129 |
| The wrist and top cameras are configured at 960 x 720 pixels with rgb and depth data types | upstream_code | source/WorldComposer/WorldComposer/tasks/Task01_Tableware/Tableware_cfg.py:42-79 |
| The success check compares the XY distance between objects A and B and requires both distances to be at most 0.035 m | upstream_code | source/WorldComposer/WorldComposer/utils/success_checker.py:97-113 |
| Installation creates a Python 3.11 environment, installs torch 2.7.0, lerobot 0.4.1 and isaacsim[all,extscache], then installs source/WorldComposer in editable mode | vendor_doc | README.md:74-86 |
| The simulation assets are downloaded from the Hugging Face WorldComposer_Assets dataset into Assets/ | vendor_doc | README.md:45-54 |
| The package setup requires Python 3.10 or newer and declares the Apache-2.0 license | upstream_code | source/WorldComposer/setup.py:32-34 |

## Limits

The driver declares no numeric bound of its own. The real action and observation space objects are created by the
external `DirectRLEnv` and were not inspected, so the fake exposes unbounded six-value Boxes and the bridge publishes
no finite action limit; no fake test number enters a Limit. The catalogued `cap.world.step.v1` schema bounds `ticks`
(1 to the bridge's `max_ticks`, 10000) and `cap.world.seed.v1` bounds `seed` to a non-negative integer, both enforced
by the runtime. No field is `operator_required`: the device is simulated R0 and the operator has no device bound to
supply.

## Fidelity

The deployed model is F0 (kinematic/analytic): engine `mhs-fake:WorldComposer-Tableware-v0`, determinism `seeded` with
`seed_control` `parameter`, `timestep_ms` 1000/120 = 8.333 ms (the `sim.dt` 1/120 s of `Tableware_cfg.py:25` with
`decimation` 1 at `:17`), `realtime_factor` 0, clock `lockstep`, reset `full`, `snapshot_restore` false. The gaps in
`driver.py` state what is not modelled, including the absent Isaac Sim physics, the unbounded action Box, the missing
camera keys, the reset randomization, the task success check, the fake's time-limit placeholder, the external assets
and the fact that the upstream stack was never started here.

## Safety

Simulated R0 device. The e-stop is the runtime's software latch: after it, no step or reset is accepted until
`mhs.safety.reset` clears the latch, the fake is not advanced, and the state stays readable. No physical stop exists
and none is claimed.

Tags: worldcomposer, tableware, robot-manipulation, isaac-lab, isaac-sim, reinforcement-learning, simulation, gymnasium

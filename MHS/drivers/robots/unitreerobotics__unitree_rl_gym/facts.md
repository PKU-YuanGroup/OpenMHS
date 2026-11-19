# Facts and tags for gh.unitreerobotics/unitree_rl_gym

Every fact cites its source at commit `276801e46c5d433564f24658bac64f254b7d2d4b`: `vendor_doc`
(README.md) or `upstream_code` (`path/in/clone.py:LINE`).  The same facts are in `driver.py`
(`facts = [Fact(text, source=..., ref=...)]`); `reference.json` is generated from the driver, not
from this page.

| fact | source | ref |
|---|---|---|
| The README describes the repository as a reinforcement learning implementation based on Unitree robots, supporting Go2, H1, H1_2 and G1 | vendor_doc | README.md:9 |
| The go2 task is registered with the LeggedRobot class and the GO2RoughCfg and GO2RoughCfgPPO configs | upstream_code | legged_gym/envs/__init__.py:14 |
| task_registry.make_env constructs the registered task class with cfg, sim_params, physics_engine, sim_device and headless | upstream_code | legged_gym/utils/task_registry.py:68-72 |
| task_registry.make_env applies the config seed with set_seed before it constructs the environment | upstream_code | legged_gym/utils/task_registry.py:64 |
| set_seed seeds Python random, numpy, torch and PYTHONHASHSEED and also the CUDA generators | upstream_code | legged_gym/utils/helpers.py:42-47 |
| BaseTask.reset resets every environment and then calls step with a zero action, returning the observation and the privileged observation | upstream_code | legged_gym/envs/base/base_task.py:82-86 |
| BaseTask takes num_envs, num_obs, num_privileged_obs and num_actions from the config and allocates observation, reward, reset, episode-length and timeout buffers for num_envs environments | upstream_code | legged_gym/envs/base/base_task.py:31-49 |
| LeggedRobot.step clips the actions to plus or minus cfg.normalization.clip_actions, runs cfg.control.decimation physics substeps and then calls post_physics_step | upstream_code | legged_gym/envs/base/legged_robot.py:49-73 |
| LeggedRobot.step returns obs_buf, privileged_obs_buf, rew_buf, reset_buf and extras after clipping the observations | upstream_code | legged_gym/envs/base/legged_robot.py:75-80 |
| post_physics_step increments episode_length_buf and common_step_counter, checks terminations, computes rewards, resets the environments in reset_buf and computes the observations | upstream_code | legged_gym/envs/base/legged_robot.py:90-112 |
| check_termination sets reset_buf from termination contacts and base orientation, sets time_out_buf when episode_length_buf exceeds max_episode_length and ORs the timeout into reset_buf | upstream_code | legged_gym/envs/base/legged_robot.py:118-124 |
| reset_idx resets the DOFs and root states, resamples commands, clears action and episode-length buffers and sets reset_buf to 1 for the selected environments | upstream_code | legged_gym/envs/base/legged_robot.py:139-151 |
| compute_observations concatenates base linear velocity, base angular velocity, projected gravity, commands, the scaled DOF position difference, DOF velocity and the actions | upstream_code | legged_gym/envs/base/legged_robot.py:182-192 |
| _compute_torques scales actions by cfg.control.action_scale and interprets them according to control_type P, V or T, clipping the torques to torque_limits | upstream_code | legged_gym/envs/base/legged_robot.py:308-330 |
| The DOF count and names come from the loaded asset | upstream_code | legged_gym/envs/base/legged_robot.py:548-558 |
| Default joint angles and PD gains are looked up by DOF name | upstream_code | legged_gym/envs/base/legged_robot.py:466-476 |
| LeggedRobot sets self.dt to cfg.control.decimation multiplied by sim_params.dt | upstream_code | legged_gym/envs/base/legged_robot.py:624 |
| The maximum episode length is ceil(episode_length_s / self.dt) | upstream_code | legged_gym/envs/base/legged_robot.py:630-631 |
| The base env config defaults to 4096 environments, 48 observations and 12 actions | upstream_code | legged_gym/envs/base/legged_robot_config.py:5-8 |
| The base control config defaults to decimation 4 | upstream_code | legged_gym/envs/base/legged_robot_config.py:60-68 |
| The base normalization config clips actions to 100.0 | upstream_code | legged_gym/envs/base/legged_robot_config.py:135 |
| The base sim config uses a 0.005 s timestep | upstream_code | legged_gym/envs/base/legged_robot_config.py:154-155 |
| The PPO config default seed is 1 | upstream_code | legged_gym/envs/base/legged_robot_config.py:173-174 |
| GO2RoughCfg extends LeggedRobotCfg and its control section sets control_type P, action_scale 0.25 and decimation 4 | upstream_code | legged_gym/envs/go2/go2_config.py:3-31 |
| GO2RoughCfg lists twelve default joint angles, four for each of the hip, thigh and calf groups | upstream_code | legged_gym/envs/go2/go2_config.py:6-21 |
| GO2RoughCfg loads the Go2 URDF from resources/robots/go2/urdf/go2.urdf | upstream_code | legged_gym/envs/go2/go2_config.py:33-35 |
| setup.py install_requires lists isaacgym, rsl-rl, matplotlib, numpy, tensorboard, mujoco and pyyaml; it names no serial, USB or DDS hardware transport | upstream_code | setup.py:11 |

## Limits

The policy envelope is `Limit.operator_required` on `action.values`: the upstream clip is a configurable policy
setting, not a joint-travel limit. `site-limits.example.json` supplies illustrative fake-scale bounds of -1 to 1.
The runtime applies a scalar bound to every leaf of flat or nested policy vectors and refuses an unfilled policy
input before a native call. An explicit action is required; omitting it cannot bypass the policy envelope. The catalogue owns the `ticks` range (1 to 10000). The driver rejects invalid shapes
and non-finite values and leaves upstream clipping to `LeggedRobot.step`.

## Interface

The package serves the `go2` registration, the one task whose class is the card's
`LeggedRobot` (`legged_gym/envs/__init__.py:14`); H1, H1_2 and G1 are registered with their own
subclasses and are not covered.

`cap.world.step.v1` takes `ticks` (default 1) and a required `action` object.  `action.values`
holds one policy vector per environment in native environment order, each with `num_actions`
values; a flat vector is broadcast to every environment.  Each tick calls `LeggedRobot.step` once,
so `ticks` counts control transitions, not the four physics substeps inside one transition.  For one
environment the receipt carries the scalar `reward`, `terminated` and `truncated`; for several
environments those per-agent values stay in the `observation` document because the catalogue output
has one reward and one terminal flag.  `terminated` is `reset_buf and not time_out_buf`;
`truncated` is `time_out_buf` (`legged_gym/envs/base/legged_robot.py:118-124`).

`cap.world.reset.v1` calls `LeggedRobot.reset` (`BaseTask.reset`, one zero-action step after the
reset of every environment) and returns the resulting observation.  It accepts `options` and ignores
it, as the upstream reset takes none.  It returns `seed: 0` because the environment has no
post-construction integer seed.

## Safety

Simulated R0 device.  The runtime owns a software e-stop latch: after an e-stop no step or reset is
accepted until `mhs.safety.reset`; the last observation, tick and episode counters stay readable.
There is no hardware stop and no native stop call, so the package declares no `@estop` and no
`estop_physical_ref`.  No `@reset` hook, no re-enable and no safe-state action are needed.

## Fidelity

`driver.py` `fidelity = {...}`: engine `analytic:unitree_rl_gym-go2-stand-in`, level F0,
determinism `none` with `seed_control` `none`, `timestep_ms` 20.0 (one control period: decimation 4
times the 0.005 s sim timestep), `realtime_factor` 0, clock `lockstep`, reset `full`, no
snapshot/restore.  The gaps say that the fake runs no PhysX, URDF, contact, terrain, command, PD or
reward computation, that it clips the action to a placeholder 100.0 rather than the configured
`cfg.normalization.clip_actions`, that the fake's default is 1 environment while the base config
default is 4096, that its 48-value observation and 12-action vector are placeholder shapes, and that
the sim backend was not run.

## Tags

unitree, go2, quadruped, reinforcement-learning, isaac-gym, simulation

## Production adapter review

The adapter constructs action tensors using the native floating observation buffer's dtype and device before
`LeggedRobot.step`, whose `torch.clip` requires a tensor (`legged_robot.py:53-57`, `base_task.py:41`). Its simulator
factory passes the sim config itself to `gymutil.parse_sim_config`, matching `helpers.py:63-65`, and refuses
`headless=False` before importing upstream: `BaseTask.render` can exit the host when a viewer closes
(`base_task.py:91-100`). The simulator profile is F1 and the analytic fake profile is F0. No live simulator was run.
Construction acquires Isaac Gym and changes process-wide torch JIT flags (`base_task.py:12,36-56`); the package
provides no simulator teardown. Native physics calls may block and one control transition may finish after e-stop.
Upstream constructor output needs isolation when hosting over stdio. `deploy/deploy_real` is a separate hardware
runner and is not served by this package.

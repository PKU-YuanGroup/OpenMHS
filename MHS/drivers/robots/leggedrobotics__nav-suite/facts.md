# Facts and tags for gh.leggedrobotics/nav-suite

Every fact cites its source at commit `648ba3b28dac61aec48e150a507c2a8507646ea2`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The suite registers three Gymnasium task ids whose entry point is isaaclab.envs:ManagerBasedRLEnv | upstream_code | exts/nav_tasks/nav_tasks/configs/__init__.py:10-32 |
| The DEV task id NavTasks-DepthImgNavigation-PPO-Anymal-D-DEV uses NavTasksDepthNavEnvCfg_DEV | upstream_code | exts/nav_tasks/nav_tasks/configs/__init__.py:10-17 |
| NavTasksDepthNavEnvCfg is a ManagerBasedRLEnvCfg subclass | upstream_code | exts/nav_tasks/nav_tasks/configs/env_cfg_base.py:393-394 |
| The scene robot is ANYMAL_D_CFG at the prim path {ENV_REGEX_NS}/Robot | upstream_code | exts/nav_tasks/nav_tasks/configs/env_cfg_base.py:72-73 |
| The high-level action term velocity_command is a NavigationSE2ActionCfg | upstream_code | exts/nav_tasks/nav_tasks/configs/env_cfg_base.py:128-134 |
| NavigationSE2ActionCfg has action_dim 3 (vx, vy, omega) and clip_mode none, so the action is not clipped | upstream_code | exts/nav_tasks/nav_tasks/mdp/actions/navigation_actions_cfg.py:44-52 |
| The simulation timestep is 0.005 s | upstream_code | exts/nav_tasks/nav_tasks/configs/env_cfg_base.py:417 |
| The high-level planner runs at 10 Hz and decimation is int(200 / 10) = 20, so one environment step advances 0.1 s | upstream_code | exts/nav_tasks/nav_tasks/configs/env_cfg_base.py:424-428 |
| The episode length is 20 s | upstream_code | exts/nav_tasks/nav_tasks/configs/env_cfg_base.py:422 |
| The reset event randomizes the base yaw over (-3.0, 3.0) | upstream_code | exts/nav_tasks/nav_tasks/configs/env_cfg_base.py:194-200 |
| The reset event sets the joint position and velocity ranges to (0.0, 0.0) | upstream_code | exts/nav_tasks/nav_tasks/configs/env_cfg_base.py:202-209 |
| The timeout termination uses max_speed 1.0 and safety_factor 4.0 | upstream_code | exts/nav_tasks/nav_tasks/configs/env_cfg_base.py:286-293 |
| The goal_reached termination requires 2.0 s within distance 0.5, angle 0.3 and speed 0.6 | upstream_code | exts/nav_tasks/nav_tasks/configs/env_cfg_base.py:295-304 |
| Contact of the base or of a thigh, hip or shank with the environment terminates the episode | upstream_code | exts/nav_tasks/nav_tasks/configs/env_cfg_base.py:306-322 |
| The policy observation group concatenates base linear and angular velocity, joint positions and velocities, goal commands and an embedded depth image, with corruption disabled | upstream_code | exts/nav_tasks/nav_tasks/configs/env_cfg_base.py:170-183 |

Limits: the driver declares none. The action space is unbounded: `NavigationSE2ActionCfg` has `clip_mode` `"none"`
and no `scale` or `offset` is set by `ActionsCfg`, so the bridge derives no `action.values` limit and nothing is
`operator_required`. `ticks` is bounded by the family bridge (1 to `max_ticks`, 10000 by default), not by a device
bound. The fake's action space is therefore a `Box` with infinite bounds, not an invented finite range.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine
`isaaclab:NavTasks-DepthImgNavigation-PPO-Anymal-D-DEV (fake: analytic kinematics)`, level F0 (the fake is kinematic
and has no dynamics or contacts), determinism `seeded` with `seed_control` `parameter`, timestep 100 ms (0.005 s times
decimation 20, `env_cfg_base.py:417` and `:424-428`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot
and restore. The gaps say what is not modelled, including the absent Isaac Lab physics, the reduced observation, the
unbatched fake and the unmodelled reward and termination terms.

Safety: simulated R0 device (`cap.world.*` classes are R0). The e-stop is the runtime's software latch (no native stop
exists); after it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: navigation, depth, anymal, isaac-lab, reinforcement-learning, simulation, gymnasium

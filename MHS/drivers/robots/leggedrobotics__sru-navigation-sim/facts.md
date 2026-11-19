# Facts and tags for gh.leggedrobotics/sru-navigation-sim

Every fact cites its source at commit `80f6c01c2d9f171374c9f9dba289abd38bcf0c6c`: `upstream_code` (a code file of
the clone) or `vendor_doc` (a text file of the clone such as `docs/README.md`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| NavigationEnv subclasses Isaac Lab's ManagerBasedRLEnv and creates an ObservationDelayManager before the other managers are loaded | upstream_code | isaaclab_nav_task/navigation/navigation_env.py:19-44 |
| Isaac-Nav-MDPO-AoW-D-v0 is registered with entry point isaaclab_nav_task.navigation:NavigationEnv and the AowDNavigationEnvCfg configuration | upstream_code | isaaclab_nav_task/navigation/config/aow_d/__init__.py:17-25 |
| The task is hierarchical: a high-level policy emits SE2 velocity commands (vx, vy, omega) at 5 Hz and a pre-trained low-level locomotion policy converts them to joint actions at 50 Hz | vendor_doc | docs/README.md:18-20 |
| The action term has action_dim 3 for [vx, vy, omega] | upstream_code | isaaclab_nav_task/navigation/mdp/navigation/actions/navigation_se2_actions.py:41-42 |
| The configured action path uses use_raw_actions=True, policy_scaling [1.5, 1.0, 1.0] and policy_distr_type 'gaussian' | upstream_code | isaaclab_nav_task/navigation/navigation_env_cfg.py:150-166 |
| With use_raw_actions=True the raw action is kept; gaussian processing applies tanh, adds the observed speed norm times policy_bias, then multiplies by policy_scaling | upstream_code | isaaclab_nav_task/navigation/mdp/navigation/actions/navigation_se2_actions.py:157-182 |
| PLANNING_FREQ is 5.0 Hz | upstream_code | isaaclab_nav_task/navigation/navigation_env_cfg.py:48 |
| The environment sets sim.dt = 0.005 s, decimation = int((1 / sim.dt) / PLANNING_FREQ), episode_length_s = 60.0 s and is_finite_horizon = True | upstream_code | isaaclab_nav_task/navigation/navigation_env_cfg.py:421-428 |
| The robot goal command is resampled only on episode reset: resampling_time_range is (1e9, 1e9) | upstream_code | isaaclab_nav_task/navigation/navigation_env_cfg.py:137-142 |
| The reset event samples the base yaw uniformly from (-pi, pi) and randomizes joint positions by scale 0.5 to 1.5 | upstream_code | isaaclab_nav_task/navigation/navigation_env_cfg.py:271-283 |
| The termination terms are time_out, base_contact (threshold 1.0), large_pitch_angle (threshold 40), early_termination at_goal (distance_threshold 0.5) and terrain_fall (fall_height_threshold -2.0) | upstream_code | isaaclab_nav_task/navigation/navigation_env_cfg.py:370-386 |
| time_out_navigation increments time_at_goal whenever the XY goal distance is below distance_threshold | upstream_code | isaaclab_nav_task/navigation/mdp/terminations.py:61-64 |
| at_goal_navigation counts the current goal entry or any earlier entry with time_at_goal > 0, and terminates when the counter exceeds required_time_at_goal_in_steps | upstream_code | isaaclab_nav_task/navigation/mdp/terminations.py:152-166 |
| required_steps_at_goal is 4.0 / env.step_dt | upstream_code | isaaclab_nav_task/navigation/mdp/navigation/goal_commands.py:378 |
| The observation groups are metrics, policy, critic and low_level_policy | upstream_code | isaaclab_nav_task/navigation/navigation_env_cfg.py:247-251 |
| The raycast camera is downsampled from 192x120 to 64x40 and has max_distance 11.0 | upstream_code | isaaclab_nav_task/navigation/navigation_env_cfg.py:85-105 |
| The simulator prerequisites are Isaac Lab v2.1.1, Isaac Sim 4.5.0, Python 3.10 and PyTorch >= 2.5.1 | vendor_doc | docs/README.md:64-69 |
| The repository excludes the rsl_rl learning module and the PPO/MDPO training algorithms | vendor_doc | docs/README.md:6-16 |
| The two robot platforms are B2W (bipedal wheeled) and AoW-D (Anymal on Wheels) | vendor_doc | docs/README.md:54-56 |

Limits: the driver declares none. The only bounds are the `cap.world.step.v1` inputs derived from the fake
environment's spaces: `ticks` (1 to the bridge's `max_ticks`, 10000 by default) and the three `action.values`
elements. The fake's action box is `[-1, 1]` per element; its bounds are placeholders because the real action space is
built by the external Isaac Lab `ManagerBasedRLEnv` and is not defined in the clone. The derived limits therefore carry
the bridge's `ref` naming the fake backend and no `upstream_code` source, and the fidelity `gaps` say so. The device is
simulated (R0), so no limit is `operator_required` and no site overlay is needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic`, level F0, determinism `seeded` with
`seed_control` `parameter`, timestep 200 ms (one environment step: `sim.dt = 0.005` and `decimation = 40`,
`navigation_env_cfg.py:421-428`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The
gaps say that this is an analytic stand-in with no dynamics, contacts, locomotion policy, depth sensor, observation
delay, domain randomization or Isaac Sim run, and that its action bounds and observation sizes are placeholders. No
comparison with the upstream environment was made.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable. This stops the declared analytic fake only; there is no pause or stop of an external Isaac Sim
application. Fake evidence does not establish an Isaac Sim, ROS or hardware run.

The upstream goal logic starts a counter on the first radius entry and continues counting after the robot leaves
(`mdp/terminations.py:62-65, 158-166`); the fake follows this behavior. Four seconds is the counter threshold,
not a requirement to remain inside the radius. The fake omits the speed-dependent policy bias and filtering of
the upstream controller. The only declared backend is fake; the generic `gymnasium.make` fallback lacks the
application bootstrap, configuration, registration and vectorized torch adaptation used by
`scripts/train.py:35-103`, and is not a supported live adapter.

The two additional card entries, `B2WNavigationEnvCfg` and `AowDNavigationEnvCfg`, are configuration classes;
`NavigationEnv` is the environment. The fake covers the AoW-D task and does not implement B2W-specific assets
or controller configuration. A decision-file proposal removes those two configuration-only entry symbols.

Tags: navigation, isaac-lab, isaac-sim, reinforcement-learning, simulation, gymnasium, aow-d

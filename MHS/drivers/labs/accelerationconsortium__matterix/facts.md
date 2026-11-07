# Facts and tags for gh.accelerationconsortium/matterix

Every fact cites its source at commit `687e2cef294f00e86dbb32173fefd93b50e5107f`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Matterix describes itself as a multi-scale, GPU-accelerated robotic simulation framework for digital twins of chemistry labs | vendor_doc | README.md:13 |
| The documented setup installs isaaclab[isaacsim,all]==3.0.0b2.post1, so Isaac Sim and Isaac Lab are external dependencies of the simulator stack | vendor_doc | README.md:39 |
| The project builds the environment configuration with parse_env_cfg and then calls gym.make(task, cfg=env_cfg), so a bare gym.make(env_id) has no cfg | upstream_code | scripts/random_agent.py:60-64 |
| MatterixBaseEnv derives from ManagerBasedEnv and gym.Env | upstream_code | source/matterix/matterix/envs/matterix_base_env.py:48 |
| The environment is vectorized: is_vector_env is True | upstream_code | source/matterix/matterix/envs/matterix_base_env.py:78 |
| step applies the action, advances cfg.decimation physics steps, updates the semantic manager, computes terminations and rewards, resets terminated environments and returns observations, rewards, terminated, truncated and extras | upstream_code | source/matterix/matterix/envs/matterix_base_env.py:215-317 |
| reset accepts seed, env_ids and options, sets the seed when given, resets the requested environments and returns the observations and extras | upstream_code | source/matterix/matterix/envs/matterix_base_env.py:501-556 |
| The observation space is a gym.spaces.Dict of Box spaces with infinite bounds built from the observation terms, the action space is Box(low=-inf, high=inf, shape=(action_dim,)), and both are batched for num_envs | upstream_code | source/matterix/matterix/envs/matterix_base_env.py:415-441 |
| The maximum episode length is ceil(episode_length_s / step_dt) environment steps | upstream_code | source/matterix/matterix/envs/matterix_base_env.py:161-163 |
| The default control decimation is 5 action updates per policy step | upstream_code | source/matterix/matterix/envs/matterix_base_env_cfg.py:95-96 |
| The default physics timestep is 1/60 s | upstream_code | source/matterix/matterix/envs/matterix_base_env_cfg.py:244 |
| The default episode_length_s is 30.0 s | upstream_code | source/matterix/matterix/envs/matterix_base_env_cfg.py:165 |
| Matterix-Test-Beakers-Franka-v1 is registered with entry point matterix.envs:MatterixBaseEnv | upstream_code | source/matterix_tasks/matterix_tasks/test_dev_tasks/__init__.py:15-22 |
| The Beakers test task declares a non-concatenated policy observation group with the terms ee_pos_robot and ee_pos_robot2, both computed by mdp.ee_env_pos | upstream_code | source/matterix_tasks/matterix_tasks/test_dev_tasks/test_franka_beakers.py:29-34 |
| ee_env_pos returns the end-effector position in the environment frame as three coordinates | upstream_code | source/matterix/matterix/envs/mdp/observations.py:49-53 |
| The Beakers test task configures two Franka arms, robot (joint position control) and robot2 (differential IK control) | upstream_code | source/matterix_tasks/matterix_tasks/test_dev_tasks/test_franka_beakers.py:57-62 |

## Limits

The driver declares no Limit. The only bounds of the served contract are the bridge's own: `cap.world.step.v1`
`ticks` is an integer from 1 to the bridge's `max_ticks` (10000 by default), and `cap.world.step.v1` `action` is the
environment's action space. Matterix builds that space as `Box(low=-inf, high=inf, shape=(action_dim,))`
(matterix_base_env.py:437), so it states no per-element bound and the bridge derives none; the driver must not invent
one. `cap.world.reset.v1` and `cap.world.seed.v1` inputs are bounded by their catalogue classes. The device is
simulated at R0, so no bound is `operator_required` and there is no site-limits overlay.

## Fidelity contract

`driver.py` `fidelity`: engine `matterix:isaaclab`, level F1 (PhysX rigid-body dynamics with contacts), determinism
`seeded` with `seed_control` `parameter`, `timestep_ms` 16.67 (the 1/60 s physics step), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore. One bridge tick is one Matterix `env.step`, i.e. one control update
of `decimation` 5 physics steps = 83.33 ms; the physics timestep is what `timestep_ms` names (spec FID-015). The gaps
say what is not modelled and that the fake was never compared with the upstream environment.

## Safety

Simulated R0 device. There is no hardware transport and no native stop; the e-stop is the runtime's software latch.
After an e-stop every step and reset is refused until `mhs.safety.reset` clears the latch (a simulator needs no
operator for that), and the last observation and tick stay readable. The upstream environment exposes no
`get_state`/`set_state`, so a snapshot is not offered.

## Tags

matterix, isaac-lab, isaac-sim, robotics, chemistry, simulation, gymnasium

# Facts and tags for gh.gepetto/constraints-as-terminations

Every fact cites its source at commit `5fc729b789a27d39bf95df1b58fbc32b794106ff`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository registers Isaac-Velocity-CaT-Flat-Solo12-v0 and Isaac-Velocity-CaT-Flat-Solo12-Play-v0 with entry_point=CaTEnv | upstream_code | exts/cat_envs/cat_envs/tasks/locomotion/velocity/config/solo12/__init__.py:16-31 |
| CaTEnv subclasses ManagerBasedRLEnv imported from isaaclab.envs.manager_based_rl_env | upstream_code | exts/cat_envs/cat_envs/tasks/utils/cat/cat_env.py:13-17 |
| CaTEnv.step takes an action whose shape is (num_envs, action_dim) | upstream_code | exts/cat_envs/cat_envs/tasks/utils/cat/cat_env.py:56 |
| CaTEnv.step performs cfg.decimation simulation steps with self.sim.step(render=False) | upstream_code | exts/cat_envs/cat_envs/tasks/utils/cat/cat_env.py:71-78 |
| CaTEnv records the termination manager's terminated and time_outs flags as reset_terminated and reset_time_outs before computing the constraint probabilities | upstream_code | exts/cat_envs/cat_envs/tasks/utils/cat/cat_env.py:94-97 |
| The third value CaTEnv.step returns is a constraint probability (dones = cstr_prob.clone()); it is not a termination flag | upstream_code | exts/cat_envs/cat_envs/tasks/utils/cat/cat_env.py:99-107 |
| CaTEnv.step returns observations, rewards, the constraint probabilities, self.reset_time_outs and self.extras | upstream_code | exts/cat_envs/cat_envs/tasks/utils/cat/cat_env.py:146-147 |
| The action term is a joint position action over the twelve named HAA, HFE and KFE joints with scale 0.5 and use_default_offset=True | upstream_code | exts/cat_envs/cat_envs/tasks/locomotion/velocity/config/solo12/cat_flat_env_cfg.py:114-133 |
| The policy observation group concatenates the base angular velocity, velocity commands, projected gravity, joint positions, joint velocities and last actions terms | upstream_code | exts/cat_envs/cat_envs/tasks/locomotion/velocity/config/solo12/cat_flat_env_cfg.py:145-176 |
| The configuration sets decimation 4, episode_length_s 10.0 and the physics step sim.dt 0.005 s | upstream_code | exts/cat_envs/cat_envs/tasks/locomotion/velocity/config/solo12/cat_flat_env_cfg.py:479-484 |
| The time_out termination term is configured with time_out=True | upstream_code | exts/cat_envs/cat_envs/tasks/locomotion/velocity/config/solo12/cat_flat_env_cfg.py:362 |
| The default scene config sets num_envs=4096 | upstream_code | exts/cat_envs/cat_envs/tasks/locomotion/velocity/config/solo12/cat_flat_env_cfg.py:464 |
| The Play variant sets scene.num_envs to 50 | upstream_code | exts/cat_envs/cat_envs/tasks/locomotion/velocity/config/solo12/cat_flat_env_cfg.py:505 |
| The constraints config sets joint_torque limit 3.0, joint_velocity limit 16.0, joint_acceleration limit 800.0 and action_rate limit 80.0 | upstream_code | exts/cat_envs/cat_envs/tasks/locomotion/velocity/config/solo12/cat_flat_env_cfg.py:262-285 |
| The constraints config also sets foot_contact_force limit 50.0, front_hfe_position limit 1.3 and upsidedown limit 0.0 | upstream_code | exts/cat_envs/cat_envs/tasks/locomotion/velocity/config/solo12/cat_flat_env_cfg.py:295-312 |
| The README states the code relies on IsaacLab version 2.1.0 | vendor_doc | README.md:15 |
| The installation installs Isaac Lab first and then runs pip install -e exts/cat_envs | vendor_doc | README.md:40-45 |
| The CleanRL training script sets env_cfg.seed = agent_cfg.seed before gym.make | upstream_code | scripts/clean_rl/train.py:109-111 |
| The CleanRL training script creates the environment with gym.make(task, cfg=env_cfg, render_mode=...) | upstream_code | scripts/clean_rl/train.py:130-131 |
| The CleanRL play script reads env.reset()[0]['policy'], so reset returns an observation mapping with a policy member | upstream_code | scripts/clean_rl/play.py:115 |
| The CleanRL loop unpacks envs.step(action) into next_obs, reward, next_done, timeouts and info, then reads next_obs['policy'] and stores timeouts as the true done | upstream_code | exts/cat_envs/cat_envs/tasks/utils/cleanrl/ppo.py:215-226 |
| The CleanRL loop reads envs.unwrapped.num_envs, single_observation_space['policy'].shape and single_action_space.shape | upstream_code | exts/cat_envs/cat_envs/tasks/utils/cleanrl/ppo.py:158-161 |

Limits: the driver declares no Limit. The only structural bounds are the twelve values of the action and the
class's `ticks` bounds, which the served `cap.world.step.v1` schema enforces; there is no sourced numeric safety
envelope on the joint-position action. The device is simulated (R0), so no bound is `operator_required` and no
operator overlay is needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `custom:cat-solo12-kinematic-stand-in`, level F0 (the
fake is a kinematic stand-in, no physics or contacts), determinism `none` with seed control `none` because the
upstream seed is an `env_cfg` field set before `gym.make`, timestep 5 ms (the physics step `sim.dt`), one
`cap.world.step.v1` tick is one `CaTEnv.step` = four physics steps = 20 ms (decimation 4, `cat_flat_env_cfg.py:479-484`),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled,
including the vectorized upstream and the constraint-probability slot. `cap.world.reset.v1` only records a supplied
seed in its receipt: the upstream seed is an `env_cfg` field set before `gym.make`, and the fake reset is
deterministic.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the world state stays readable.

Tags: constraints-as-terminations, cat, solo12, isaac-lab, locomotion, reinforcement-learning, simulation

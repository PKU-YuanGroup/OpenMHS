# Facts and scope for gh.sharpa-robotics/sharpa-rl-lab

Facts cite the read-only source at commit `95ccda3d948801bb5da4cb7ffea766e03067a63b`. The table matches the Fact declarations in driver.py and the generated reference.json.

| Fact | Source | Ref |
|---|---|---|
| The environment id Isaac-Inhand-Rotate-Sharpa-Wave-v0 is registered with entry point rl_isaaclab.tasks.inhand_rotate.sharpa_wave_env:SharpaWaveInhandRotateEnv and config SharpaWaveEnvCfg | upstream_code | `rl_isaaclab/tasks/inhand_rotate/__init__.py:9-17` |
| The environment class subclasses DirectRLEnv imported from isaaclab.envs | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env.py:19-28` |
| The task config sets episode_length_s 20.0, action_space 22 and observation_space 192 | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env_cfg.py:41-43` |
| The control loop decimates 12 physics steps of dt 1/240 s per control step, 0.05 s | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env_cfg.py:49-56` |
| The config sets clip_actions to 1.0 and action_scale to 1/24 | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env_cfg.py:51-52` |
| _pre_physics_step saturates actions to plus or minus cfg.clip_actions, adds cfg.action_scale times the action to prev_targets and saturates targets to the hand joint limits | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env.py:177-185` |
| The environment uses torque control | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env_cfg.py:53` |
| The hand joint limits are read from the articulation and multiplied by cfg.dof_limits_scale | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env.py:86-89` |
| The config sets dof_limits_scale to 0.9 | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env_cfg.py:292` |
| The grasp cache filename combines cfg.grasp_cache_path, the two scale endpoints and the scale count | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env.py:112-115` |
| The configured grasp_cache_path is cache/sharpa_grasp_linspace | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env_cfg.py:278` |
| A reset raises RuntimeError('No saved grasping states found') when no grasp cache is loaded | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env.py:292-300` |
| The policy observation is the last three frames of a 64-value history: 22 scaled joint positions, 22 joint targets, 5 contact values and 15 contact positions per frame | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env.py:421-445` |
| The config sets angvel_clip_min to -0.5, angvel_clip_max to 0.5 and rotate_reward_scale to 2.5 | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env_cfg.py:269-271` |
| The total reward adds the six terms rotate_reward, object_linvel_penalty, pos_diff_penalty, torque_penalty, work_penalty and object_pos_diff, each multiplied by its configured scale | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env.py:487-493` |
| The five remaining reward scales are -0.3, -0.4, -0.1, -0.5 and 0.003 | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env_cfg.py:272-276` |
| The episode truncates when episode_length_buf reaches max_episode_length - 1 and terminates when the object height leaves the reset band | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env.py:250-266` |
| The reset height band is 0.59906 to 0.63906 m | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env_cfg.py:263-264` |
| The configured scene has 16384 environments | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env_cfg.py:259` |
| Tactile contact observations are enabled and contact positions are disabled by default | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env_cfg.py:282-284` |
| The repository tells the user to install IsaacLab from its official guide before this package | vendor_doc | `README.md:9-13` |
| SharpaWaveEnvCfg subclasses DirectRLEnvCfg and is decorated with configclass | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_env_cfg.py:38-39` |
| The hardware deploy environment imports SharpaWaveManager, ControlMode, ControlSource and SharpaWaveConfig from sharpa | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_deploy_env.py:18-23` |
| The hardware deploy step converts its current targets and calls hand.set_joint_position(command) | upstream_code | `rl_isaaclab/tasks/inhand_rotate/sharpa_wave_deploy_env.py:227-228` |

## Served contract and limits

Only the analytic fake for the in-hand rotation task is declared. SharpaWaveEnvCfg is configuration, not a
reset/step device entry; the model decision proposes removing it from the card's entry symbols. The separate
SharpaWaveInhandRotateDeployEnv imports the external sharpa SDK and commands a real hand; it is outside this
R0 simulation package and the software stop makes no claim about that hand.

The external DirectRLEnv builds the actual action space, so the fake has no action_space_ref. Its unbounded
22-value Box has no finite derived input envelope; internal saturation at clip_actions is a separate operation.
No device bound is invented. The fake's action and policy-observation spaces are unbatched and match its flat
returns; the real environment uses batched Torch arrays, rewards and done flags.

## Fidelity and safety

The fake is analytic F0, seeded and lockstep with a derived 50 ms control period. It models one environment,
not 16384, omits priv_info and proprio_hist, supplies zero tactile channels and uses placeholder reset poses,
joint limits and PD gains. Its counter truncates at max_episode_length - 1, matching the in-clone predicate;
the external base's automatic reset lifecycle is omitted. Its reward terms use proxy state, not Isaac physics.

No usable live factory is declared. The implicit gym.make fallback does not supply the required cfg or initialize
the Isaac application. Upstream train.py:31-32 starts AppLauncher and :89 supplies cfg; a live adapter would also
need batch conversion, application lifecycle isolation and the grasp cache. Construction can call exit()
(sharpa_wave_env.py:105-108), and the gravity curriculum prints to stdout (:265). None of this executes in the fake.
The runtime latch freezes the fake once in-flight work settles; step, reset and seed are refused until a safety
reset, and the last observation remains readable. No native Isaac stop or hardware stop is claimed.

The repository LICENSE declares Apache-2.0. No upstream simulator, real hand or hardware execution was performed.

Tags: sharpa-wave, in-hand-rotation, dexterous-manipulation, isaaclab, reinforcement-learning, simulation, gymnasium

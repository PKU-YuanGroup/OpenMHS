# Facts and tags for gh.cai23sbp/isaaclab_parkour

Every fact cites its source at commit `d6766d8883cffe427f2d4c087717d4eca1f23d8c`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The teacher task is registered as gym id Isaac-Extreme-Parkour-Teacher-Unitree-Go2-v0 with entry_point parkour_isaaclab.envs:ParkourManagerBasedRLEnv and the UnitreeGo2TeacherParkourEnvCfg configuration | upstream_code | parkour_tasks/parkour_tasks/extreme_parkour_task/config/go2/__init__.py:18-24 |
| ParkourManagerBasedRLEnv is a vectorized Gymnasium environment: it sets is_vector_env = True | upstream_code | parkour_isaaclab/envs/parkour_manager_based_rl_env.py:22-23 |
| The teacher scene configures 6144 environments with an environment spacing of 1.0 | upstream_code | parkour_tasks/parkour_tasks/extreme_parkour_task/config/go2/parkour_teacher_cfg.py:34 |
| The teacher config sets decimation 4, an episode length of 20.0 s, a simulation timestep of 0.005 s and a render interval equal to the decimation | upstream_code | parkour_tasks/parkour_tasks/extreme_parkour_task/config/go2/parkour_teacher_cfg.py:48-52 |
| The shared ActionsCfg drives every robot joint (joint_names ['.*']) with scale 0.25 and the default joint offset, action_delay_steps [1, 1], an action history of 8 and a per-joint clip of (-4.8, 4.8) | upstream_code | parkour_tasks/parkour_tasks/extreme_parkour_task/config/go2/parkour_mdp_cfg.py:339-350 |
| The teacher configuration overrides joint_pos.use_delay to False and joint_pos.history_length to 1 | upstream_code | parkour_tasks/parkour_tasks/extreme_parkour_task/config/go2/parkour_teacher_cfg.py:59-60 |
| The action term applies processed_actions as joint position targets | upstream_code | parkour_isaaclab/envs/mdp/parkour_actions/joint_actions.py:33-35 |
| The action term clips raw actions then computes processed_actions as raw_actions * scale + offset | upstream_code | parkour_isaaclab/envs/mdp/parkour_actions/joint_actions.py:50-54 |
| The policy configuration counts 53 proprioceptive values, 132 height scans, 9 privileged explicit values, 29 privileged latent values (4 + 1 + 12 + 12) and a history of 10 | upstream_code | parkour_tasks/parkour_tasks/extreme_parkour_task/config/go2/agents/parkour_rl_cfg.py:24-28 |
| ExtremeParkourObservations concatenates the 53-value proprioceptive vector, the 132 measured heights, the 9 privileged explicit values, the 29 privileged latent values and the flattened history buffer | upstream_code | parkour_isaaclab/envs/mdp/observations.py:85-90 |
| The single action space is a Box(low=-inf, high=inf, shape=(action_dim,)) where action_dim is the sum of the action term dimensions; the environment then batches the observation and action spaces over num_envs | upstream_code | parkour_isaaclab/envs/parkour_manager_based_rl_env.py:239-244 |
| The single observation space is a Dict of Box(low=-inf, high=inf) spaces shaped by the observation manager groups, batched over num_envs | upstream_code | parkour_isaaclab/envs/parkour_manager_based_rl_env.py:224-243 |
| step processes the action, applies it over the configured decimation physics steps, computes terminations, rewards and resets, and returns (obs_buf, reward_buf, reset_terminated, reset_time_outs, extras) | upstream_code | parkour_isaaclab/envs/parkour_manager_based_rl_env.py:95-165 |
| The terminate_episode function ORs roll/pitch cutoffs above 1.5 rad, a base-height cutoff below -0.25 m, episode-length exhaustion and goal-count exhaustion into reset_buf | upstream_code | parkour_isaaclab/envs/mdp/terminations.py:32-42 |
| TerminationsCfg declares terminate_episode as a time_out=True term | upstream_code | parkour_tasks/parkour_tasks/extreme_parkour_task/config/go2/parkour_mdp_cfg.py:247-253 |
| The reset signature takes seed, env_ids and options and returns (observations, extras) | upstream_code | parkour_isaaclab/envs/parkour_manager_based_env.py:152-184 |
| The demo launches the Omniverse application with AppLauncher and later constructs ParkourManagerBasedRLEnv(cfg=env_cfg) | upstream_code | scripts/rsl_rl/demo.py:38-89 |
| The README installs the package inside an external IsaacLab checkout with pip3 install -e . | upstream_code | README.md:13-25 |
| The repository LICENSE names GNU General Public License version 3 | vendor_doc | LICENSE:1-2 |
| The environment module carries an Isaac Lab Project Developers copyright and a BSD-3-Clause SPDX header | upstream_code | parkour_isaaclab/envs/parkour_manager_based_rl_env.py:1-4 |

Limits: the fake's Box restricts every `action.values` element to -4.8 through 4.8, matching the raw-action clip
in `parkour_mdp_cfg.py:349`. This is a narrower fake contract than the upstream unbounded Gym space, and the
generated bounds identify the fake backend without claiming an upstream `action_space_ref`. The endpoint rejects
larger inputs before stepping, whereas upstream would clip them internally before applying scale 0.25 and its
default-pose offset (`parkour_actions/joint_actions.py:33-54`). The teacher disables delay and
sets action history length to one (`parkour_teacher_cfg.py:59-60`). The fake uses absolute position targets with
placeholder zero default offsets and instantaneous tracking. No limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine
"analytic:single-environment parkour contract fake (no Isaac Sim/PhysX)", level F0 (no physics, contacts, terrain, sensors or
manager computation), determinism `seeded` with `seed_control` `parameter`, timestep 20 ms (`sim.dt` 0.005 s times
decimation 4, `parkour_teacher_cfg.py:48-52`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and
restore. The gaps say what the fake does not model and that the `sim` backend (Isaac Lab) was not run.

Space sizes and placeholders: the fake's action space has 12 values and its observation vector has 753 values. The
observation count is the sourced composition above (53 + 132 + 9 + 29 + 10 * 53 = 753). The action dimension 12 is a
placeholder: the action term drives every joint of the Unitree Go2 and the clone never states the joint count; 12 is
inferred from the 12 joint stiffness and 12 joint damping terms counted in `parkour_rl_cfg.py:25`. The fake presents
one environment of the 6144 upstream environments because the SDK Gymnasium bridge drives one environment, and keeps
the batched space shapes for `num_envs = 1`. The fake returns scalar rewards and flags, omits automatic resets,
and models no roll, pitch, height or goal cutoff; the episode-length cutoff alone is reproduced.

Safety: simulated R0 fake-only contract. Its software latch refuses steps and resets until `mhs.safety.reset`
clears it, with the cached state readable. No native Isaac timeline pause/read-back or process isolation exists;
an independently running simulator is not stopped by refusing new MHS steps.

Live integration is not supplied: the implicit `gymnasium.make` route lacks the required cfg construction,
device-tensor actions, vector reward/flag adaptation and per-environment auto-reset handling. Native construction
creates or reuses a global SimulationContext, builds a scene/managers, can start the timeline and prints to stdout
(`parkour_manager_based_env.py:40-141`); reset may wait for assets without a timeout (`:180-182`). No live simulator
was run. Repository licensing is GPL-3.0 (`LICENSE:1-2`), while the environment modules retain BSD-3-Clause Isaac Lab
headers (`parkour_manager_based_rl_env.py:1-4`); no upstream code or assets are copied here.

Tags: unitree-go2, quadruped, parkour, locomotion, isaac-lab, physx, simulation, gymnasium

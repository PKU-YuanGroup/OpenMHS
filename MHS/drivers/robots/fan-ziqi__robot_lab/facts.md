# Facts and tags for gh.fan-ziqi/robot_lab

Every fact cites its source at commit `500399ed75f510aeaff28705a8ce736c514dbec3` (`upstream_code`: a code line or
comment of the clone). The same facts are written into `driver.py` (`facts = [...]`); `reference.json` and
`REFERENCE.md` are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| RobotLab-Isaac-G1-AMP-Dance-Direct-v0 is registered with entry point robot_lab.tasks.direct.g1_amp.g1_amp_env:G1AmpEnv and env_cfg_entry_point robot_lab.tasks.direct.g1_amp.g1_amp_env_cfg:G1AmpDanceEnvCfg | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/__init__.py:21-29 |
| G1AmpEnv extends DirectRLEnv | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env.py:28 |
| G1AmpEnv defines the DirectRLEnv hooks _pre_physics_step, _apply_action, _get_observations, _get_rewards, _get_dones and _reset_idx | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env.py:99-253 |
| The action offset and scale are the midpoint and the width of the soft joint-position limits | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env.py:35-38 |
| Each action is written as a joint-position target: action_offset + action_scale * actions | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env.py:102-104 |
| The config declares observation_space = 71 + 3 * (8 + 5) - 6 + 1 and action_space = 29 | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env_cfg.py:53-54 |
| The episode length is 10.0 s, decimation is 1 and the simulation timestep is 1/60 s | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env_cfg.py:48-50 |
| The policy observation is the dict {'policy': obs} | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env.py:134 |
| compute_obs concatenates joint positions, joint velocities, root height, the root quaternion tangent and normal, the key-body positions relative to the root and the episode progress | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env.py:369-382 |
| The 13 key bodies are the shoulder yaw, elbow, rubber hand, ankle roll, torso, hip yaw and knee links | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env.py:45-59 |
| The AMP observation history has num_amp_observations = 3 and amp_observation_space = 71 + 3 * (8 + 5) - 6 + 1 | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env_cfg.py:56-57 |
| The reward combines joint-position, joint-velocity, root-position and root-orientation imitation terms with the basic reward terms termination, action L2, joint-position limits, joint-acceleration L2 and joint-velocity L2 | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env.py:159-204 |
| The basic action L2 reward is rew_action_l2 times the sum of squared actions | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env.py:400 |
| rew_action_l2 is -0.1 | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env_cfg.py:33 |
| The episode truncates when episode_length_buf >= max_episode_length - 1 | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env.py:242 |
| With early_termination enabled, the episode terminates when the reference body's world z is below termination_height | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env.py:243-247 |
| early_termination is True and termination_height is 0.5 | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env_cfg.py:59-60 |
| The motion file is g1_dance1_subject2_30.npz, the reference body is the pelvis and the reset strategy is random-start | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env_cfg.py:62-64 |
| The config documents random-start as sampling motion at time zero | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env_cfg.py:64-71 |
| The reset writes the root pose, root velocity and joint state to the simulation | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env.py:263-265 |
| The scene is configured with num_envs=4096 and env spacing 4.0 | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env_cfg.py:83 |
| SimulationCfg sets dt=dt, render_interval=decimation and physx=PhysxCfg | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env_cfg.py:73-80 |
| The robot is UNITREE_G1_29DOF_CFG at prim path /World/envs/env_.*/Robot | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env_cfg.py:86 |
| The extension declares isaaclab, isaaclab_assets, isaaclab_mimic, isaaclab_rl and isaaclab_tasks as dependencies | upstream_code | source/robot_lab/config/extension.toml:17-22 |
| The setup requires psutil, colorama, xacrodoc, numpy, pandas, pinocchio and cusrl[all]; it names no serial, VISA, USB, socket or ROS client | upstream_code | source/robot_lab/setup.py:16-28 |
| The README says running a policy in Gazebo or on a real robot is deferred to the separate rl_sar project | upstream_code | README.md:44-45 |
| The README installs Isaac Lab first and then the extension with python -m pip install -e source/robot_lab | upstream_code | README.md:59-73 |
| The environment source carries Apache-2.0 and BSD-3-Clause copyright notices | upstream_code | source/robot_lab/robot_lab/tasks/direct/g1_amp/g1_amp_env.py:1-11 |

Limits: the driver declares none. The bridge derives the action bound from the fake environment's Box and bounds
`ticks` to 1..`max_ticks` (10000 by default). The fake uses a placeholder Box of 29 values in -1..1; the clone states
only `action_space = 29` (`g1_amp_env_cfg.py:54`), and the exact Box bounds are provided by Isaac Lab outside the
clone, so `action_space_ref` is not set and the derived limits carry no source. There is no writable state field, so
the package ships no `site-limits.example.json`; the action bounds are test data until the real environment is
observed. The device is simulated R0, so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `isaaclab:RobotLab-Isaac-G1-AMP-Dance-Direct-v0`, level F0
(contract stand-in, no rigid-body physics), determinism `seeded` with `seed_control` `parameter`, timestep
`1000/60` ms (the config's `dt = 1/60` with `decimation = 1`), `realtime_factor` 0, clock `lockstep`, reset `full`,
no snapshot and restore. The gaps say what is not modelled (dynamics, contacts, the motion file, the AMP history and
the imitation reward) and that the fake was never compared with the upstream environment.

Safety: simulated R0 fake-only contract. The software latch refuses step, reset and seed until `mhs.safety.reset`;
cached world state stays readable. Releasing the latch does not advance it. No native stop of Isaac Sim is
established. Live construction needs AppLauncher, registration imports and a resolved cfg; vectorized tensor
batching, automatic resets and the external DirectRLEnv lifecycle were not executed. The fake mirrors the cited
timeout predicate at counter 599 for a nominal max_episode_length of 600. No physical robot is modelled; the README defers real-robot and Gazebo execution to the separate
`rl_sar` project (`README.md:44-45`), so this package has no hardware backend and no physical e-stop.

Tags: humanoid, unitree-g1, amp, motion-imitation, isaac-lab, isaac-sim, reinforcement-learning, simulation,
gymnasium.

The environment source carries Apache-2.0 and BSD-3-Clause notices (g1_amp_env.py:1-11); preserve the applicable notices.

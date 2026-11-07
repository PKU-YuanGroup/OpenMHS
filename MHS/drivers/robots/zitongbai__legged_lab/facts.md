# Facts and tags for gh.zitongbai/legged_lab

Every fact cites its source at commit `69b7f73d912a9d5695a60b5bed41d0785c8b302e`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository is an extension for legged-robot reinforcement learning based on Isaac Lab | vendor_doc | README.md:29 |
| The README badge lists Isaac Sim 5.1.0 and Isaac Lab 2.3.2 | vendor_doc | README.md:3-4 |
| Isaac Lab v2.3.2 must be installed before this package | vendor_doc | README.md:64 |
| Git LFS is required, and git lfs install followed by git lfs pull downloads the USD models and motion data | vendor_doc | README.md:83-89 |
| The package is installed with python -m pip install -e source/legged_lab | vendor_doc | README.md:95 |
| Training uses a customized rsl_rl cloned from the feature/amp branch | vendor_doc | README.md:98-107 |
| The extension declares isaaclab, isaaclab_assets, isaaclab_mimic, isaaclab_rl and isaaclab_tasks as dependencies | upstream_code | source/legged_lab/config/extension.toml:17-22 |
| LeggedLab-Isaac-AMP-G1-v0 is registered with gymnasium.register and its entry point is legged_lab.envs:ManagerBasedAmpEnv | upstream_code | source/legged_lab/legged_lab/tasks/locomotion/amp/config/g1/__init__.py:7-15 |
| LeggedLab-Isaac-AMP-G1-Play-v0 is registered with the same entry point and the play configuration | upstream_code | source/legged_lab/legged_lab/tasks/locomotion/amp/config/g1/__init__.py:17-25 |
| ManagerBasedAmpEnv subclasses ManagerBasedAnimationEnv | upstream_code | source/legged_lab/legged_lab/envs/manager_based_amp_env.py:21 |
| ManagerBasedAnimationEnv subclasses Isaac Lab's ManagerBasedRLEnv, imported from isaaclab.envs | upstream_code | source/legged_lab/legged_lab/envs/manager_based_animation_env.py:6 |
| ManagerBasedAmpEnv.load_managers builds the managers and then calls self._configure_gym_env_spaces() | upstream_code | source/legged_lab/legged_lab/envs/manager_based_amp_env.py:75-100 |
| ManagerBasedAmpEnv.step takes an action of shape (num_envs, action_dim) and returns observations, rewards, terminated, truncated and extras | upstream_code | source/legged_lab/legged_lab/envs/manager_based_amp_env.py:105-208 |
| The action term is a JointPositionAction over every joint (joint_names ['.*']) with scale 0.25 and use_default_offset=True | upstream_code | source/legged_lab/legged_lab/tasks/locomotion/amp/amp_env_cfg.py:92 |
| The policy observation group concatenates base_ang_vel, root_local_rot_tan_norm, velocity_commands, joint_pos, joint_vel and actions, with history_length 5, corruption enabled and terms concatenated | upstream_code | source/legged_lab/legged_lab/tasks/locomotion/amp/amp_env_cfg.py:113-129 |
| root_local_rot_tan_norm returns the tangent and normal vectors of the local rotation matrix, six values in total | upstream_code | source/legged_lab/legged_lab/tasks/locomotion/amp/mdp/observations.py:25-29 |
| The decimation is 4, the episode length is 20.0 s and the simulation timestep is 0.005 s | upstream_code | source/legged_lab/legged_lab/tasks/locomotion/amp/amp_env_cfg.py:394-397 |
| The termination terms are a time-out, an illegal contact, a base height below 0.2 m and a bad orientation above 60 degrees | upstream_code | source/legged_lab/legged_lab/tasks/locomotion/amp/amp_env_cfg.py:313-323 |
| G1AmpEnvCfg disables the base_contact termination | upstream_code | source/legged_lab/legged_lab/tasks/locomotion/amp/config/g1/g1_amp_env_cfg.py:223 |
| G1AmpEnvCfg replaces the scene robot with UNITREE_G1_29DOF_CFG | upstream_code | source/legged_lab/legged_lab/tasks/locomotion/amp/config/g1/g1_amp_env_cfg.py:117 |
| The G1 asset lists 29 joint_sdk_names, from left_hip_pitch_joint to right_wrist_yaw_joint | upstream_code | source/legged_lab/legged_lab/assets/unitree.py:167-197 |
| The G1 initial joint positions set the hip pitch to -0.1, the knee to 0.3, the ankle pitch to -0.2, the shoulder pitch to 0.3, the shoulder roll to +-0.25, the elbow to 0.97 and the wrist roll to +-0.15 | upstream_code | source/legged_lab/legged_lab/assets/unitree.py:94-105 |
| The G1 AMP command ranges are -0.5 to 3.0 for lin_vel_x, -0.5 to 0.5 for lin_vel_y, -1.0 to 1.0 for ang_vel_z and -pi to pi for heading | upstream_code | source/legged_lab/legged_lab/tasks/locomotion/amp/config/g1/g1_amp_env_cfg.py:209-212 |
| The G1 AMP reset event samples the reference animation with a height offset of 0.1 | upstream_code | source/legged_lab/legged_lab/tasks/locomotion/amp/config/g1/g1_amp_env_cfg.py:200 |
| The animation term enables random_initialize and random_fetch, so a reset draws a random reference motion | upstream_code | source/legged_lab/legged_lab/tasks/locomotion/amp/amp_env_cfg.py:359-361 |

Limits: the driver declares none. The action space is the manager-based Isaac Lab joint-position Box; the clone
states the action term and its scale (`amp_env_cfg.py:92`) but no numeric action bound, so the fake publishes an
unbounded 29-value Box rather than inventing one. `ticks` is bounded by the bridge (1 to `max_ticks`, 10000 by
default), and the device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:LeggedLab-Isaac-AMP-G1-v0`, level F0 (the
checked fake is kinematic; the Isaac Lab engine is F1 but was not run), determinism `seeded` with `seed_control`
`parameter` for the fake only, timestep 20 ms (4 x 0.005 s, `amp_env_cfg.py:394` and `:397`), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled, including the full policy
observation group, the reward terms and the physical terminations, and that the fake was not compared with Isaac Sim.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the last
observation stays readable.

Tags: unitree, g1, humanoid, locomotion, amp, motion-imitation, isaac-sim, isaac-lab, reinforcement-learning,
simulation, gymnasium

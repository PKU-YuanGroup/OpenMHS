# Facts and tags for gh.hybridrobotics/isaac_berkeley_humanoid

Every fact cites its source at commit `ffc7b2692917fdaf7cd87da53ada778e989dae35`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository shows the training code for Berkeley Humanoid with IsaacLab | vendor_doc | README.md:10 |
| The installation guide asks for Isaac Lab v1.0.0 with Isaac Sim 4.0.0 | vendor_doc | README.md:25-27 |
| The extension is installed from exts/berkeley_humanoid with python -m pip install -e . after Isaac Lab is installed | vendor_doc | README.md:29-34 |
| The documented training command runs scripts/rsl_rl/train.py with --task Velocity-Rough-Berkeley-Humanoid-v0; the play command uses Velocity-Rough-Berkeley-Humanoid-Play-v0 | vendor_doc | README.md:38-44 |
| Velocity-Rough-Berkeley-Humanoid-v0 is registered with entry point omni.isaac.lab.envs:ManagerBasedRLEnv and env_cfg_entry_point rough_env_cfg.BerkeleyHumanoidRoughEnvCfg | upstream_code | exts/berkeley_humanoid/berkeley_humanoid/tasks/locomotion/velocity/config/berkeley_humanoid/__init__.py:34-42 |
| Velocity-Flat-Berkeley-Humanoid-v0 is registered with the same ManagerBasedRLEnv entry point and flat_env_cfg.BerkeleyHumanoidFlatEnvCfg as its environment configuration | upstream_code | exts/berkeley_humanoid/berkeley_humanoid/tasks/locomotion/velocity/config/berkeley_humanoid/__init__.py:14-22 |
| Velocity-Rough-Berkeley-Humanoid-Play-v0 registers rough_env_cfg.BerkeleyHumanoidRoughEnvCfg_PLAY | upstream_code | exts/berkeley_humanoid/berkeley_humanoid/tasks/locomotion/velocity/config/berkeley_humanoid/__init__.py:44-52 |
| BerkeleyHumanoidRoughEnvCfg subclasses LocomotionVelocityRoughEnvCfg and installs BERKELEY_HUMANOID_CFG as the scene robot | upstream_code | exts/berkeley_humanoid/berkeley_humanoid/tasks/locomotion/velocity/config/berkeley_humanoid/rough_env_cfg.py:17-22 |
| The rough configuration removes the height_scan observation term and the height scanner | upstream_code | exts/berkeley_humanoid/berkeley_humanoid/tasks/locomotion/velocity/config/berkeley_humanoid/rough_env_cfg.py:26-27 |
| BerkeleyHumanoidFlatEnvCfg subclasses BerkeleyHumanoidRoughEnvCfg and changes the terrain to a plane without a terrain generator | upstream_code | exts/berkeley_humanoid/berkeley_humanoid/tasks/locomotion/velocity/config/berkeley_humanoid/flat_env_cfg.py:11-23 |
| LocomotionVelocityRoughEnvCfg subclasses ManagerBasedRLEnvCfg and defines the scene, observations, actions, commands, rewards, terminations, randomization and curriculum | upstream_code | exts/berkeley_humanoid/berkeley_humanoid/tasks/locomotion/velocity/velocity_env_cfg.py:342-356 |
| The action is a joint-position target over every joint with scale 0.5 and use_default_offset=True | upstream_code | exts/berkeley_humanoid/berkeley_humanoid/tasks/locomotion/velocity/velocity_env_cfg.py:115 |
| The policy observation group concatenates base_lin_vel, base_ang_vel, projected_gravity, velocity_commands, hip_pos, kfe_pos, ffe_pos, faa_pos, joint_vel and actions | upstream_code | exts/berkeley_humanoid/berkeley_humanoid/tasks/locomotion/velocity/velocity_env_cfg.py:126-143 |
| The policy group sets enable_corruption=True and concatenate_terms=True | upstream_code | exts/berkeley_humanoid/berkeley_humanoid/tasks/locomotion/velocity/velocity_env_cfg.py:152-154 |
| The hip-position term selects joints matching .*HR, .*HAA and .*HFE; the knee term .*KFE, the foot-roll term .*FFE, the foot-yaw term .*FAA, and the joint-velocity and last-action terms cover the whole joint set | upstream_code | exts/berkeley_humanoid/berkeley_humanoid/tasks/locomotion/velocity/velocity_env_cfg.py:134-143 |
| The asset init_state declares 12 joints: LL_HR, LR_HR, LL_HAA, LR_HAA, LL_HFE, LR_HFE, LL_KFE, LR_KFE, LL_FFE, LR_FFE, LL_FAA and LR_FAA | upstream_code | exts/berkeley_humanoid/berkeley_humanoid/assets/berkeley_humanoid.py:96-109 |
| The environment sets decimation 4, episode_length_s 20.0 and sim.dt 0.005 s, so one control step is 4 * 0.005 = 0.02 s | upstream_code | exts/berkeley_humanoid/berkeley_humanoid/tasks/locomotion/velocity/velocity_env_cfg.py:361-364 |
| The command ranges are lin_vel_x and lin_vel_y from -1.0 to 1.0, ang_vel_z from -1.0 to 1.0 and heading from -pi to pi, resampled every 10.0 s | upstream_code | exts/berkeley_humanoid/berkeley_humanoid/tasks/locomotion/velocity/velocity_env_cfg.py:97-107 |
| The reset events sample the base pose x and y from -0.5 to 0.5 and yaw from -3.14 to 3.14, the base velocities from -0.5 to 0.5 and the joint-position scale from 0.5 to 1.5 | upstream_code | exts/berkeley_humanoid/berkeley_humanoid/tasks/locomotion/velocity/velocity_env_cfg.py:223-246 |
| The termination terms are a time-out and an illegal contact of the torso with threshold 1.0 | upstream_code | exts/berkeley_humanoid/berkeley_humanoid/tasks/locomotion/velocity/velocity_env_cfg.py:315-318 |
| The training script launches the Isaac Sim application with AppLauncher | upstream_code | scripts/rsl_rl/train.py:39-40 |
| The training script imports berkeley_humanoid.tasks so the gym.register calls run | upstream_code | scripts/rsl_rl/train.py:51-52 |
| The training script creates the environment with gym.make(task, cfg=env_cfg, render_mode=...) | upstream_code | scripts/rsl_rl/train.py:88-89 |
| The training script calls env.seed(agent_cfg.seed) | upstream_code | scripts/rsl_rl/train.py:115-117 |
| setup.py declares python_requires >=3.10 and an Isaac Sim 4.0.0 classifier | upstream_code | exts/berkeley_humanoid/setup.py:39-44 |
| The LICENCE file states SPDX-License-Identifier: BSD-3-Clause | upstream_code | LICENCE:5 |

Limits: the driver declares none. The action space is created by the external Isaac Lab `ManagerBasedRLEnv`; the clone
states the joint-position action and its 0.5 scale (`velocity_env_cfg.py:115`) but no numeric action bound, so the fake
publishes an unbounded 12-value Box rather than inventing one. `ticks` is bounded by the bridge (1 to `max_ticks`,
10000 by default), and the device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mhs-fake:Velocity-Rough-Berkeley-Humanoid-v0`, level F0
(interface stand-in, no dynamics), determinism `seeded` with `seed_control` `parameter` for the fake only, timestep
20 ms (4 x 0.005 s, `velocity_env_cfg.py:361-364`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot
and restore. The gaps say what is not modelled: physics, contacts, actuators, sensors, terrain, reward, the 4096
environment default (`velocity_env_cfg.py:347`), the other nine policy observation terms, the reset randomizations and
the configured terminations, and that the fake was not compared with Isaac Sim.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the last world state stays readable.

Tags: berkeley-humanoid, humanoid, legged-locomotion, velocity-tracking, isaac-lab, isaac-sim,
reinforcement-learning, simulation, gymnasium

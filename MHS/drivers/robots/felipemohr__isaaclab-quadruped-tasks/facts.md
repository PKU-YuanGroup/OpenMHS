# Facts and tags for gh.felipemohr/isaaclab-quadruped-tasks

Every fact cites its source at commit `6d2f0b39c162330f9697db132238b64855cb6ae3`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository is an Isaac Lab extension with tasks for training quadruped robots using reinforcement learning | upstream_code | README.md:15 |
| Five task types train three quadruped robots, ANYmal D, Go2 and Spot | upstream_code | README.md:17-23 |
| The installation begins by installing NVIDIA Isaac Sim and Isaac Lab separately | upstream_code | README.md:26 |
| The extension is installed with pip install -e exts/omni.isaac.lab_quadruped_tasks | upstream_code | README.md:33 |
| The task registrations import gymnasium as gym | upstream_code | exts/omni.isaac.lab_quadruped_tasks/omni/isaac/lab_quadruped_tasks/robots/anymal_d/__init__.py:6 |
| Isaac-Quadruped-AnymalD-Blind-Flat-v0 is registered with entry_point omni.isaac.lab.envs:ManagerBasedRLEnv and env_cfg_entry_point AnymalDBlindFlatEnvCfg | upstream_code | exts/omni.isaac.lab_quadruped_tasks/omni/isaac/lab_quadruped_tasks/robots/anymal_d/__init__.py:43-50 |
| AnymalDBlindFlatEnvCfg is defined in the clone and extends AnymalDBaseEnvCfg | upstream_code | exts/omni.isaac.lab_quadruped_tasks/omni/isaac/lab_quadruped_tasks/robots/anymal_d/anymal_d_env_cfg.py:65 |
| The blind flat task disables the height scanner, the height-map observation, the velocity-command event and the terrain-level curriculum | upstream_code | exts/omni.isaac.lab_quadruped_tasks/omni/isaac/lab_quadruped_tasks/robots/anymal_d/anymal_d_env_cfg.py:69-73 |
| The action term is JointPositionActionCfg with asset_name 'robot', joint_names ['.*'], scale 0.5 and use_default_offset True | upstream_code | exts/omni.isaac.lab_quadruped_tasks/omni/isaac/lab_quadruped_tasks/cfg/quadruped_env_cfg.py:118 |
| The policy observation terms are the velocity command, base linear velocity, base angular velocity, projected gravity, joint positions, joint velocities, last action and, when enabled, a clipped height map; the base and joint measurements carry Gaussian noise | upstream_code | exts/omni.isaac.lab_quadruped_tasks/omni/isaac/lab_quadruped_tasks/cfg/quadruped_env_cfg.py:130-150 |
| The policy observation group concatenates its terms and enables corruption by default | upstream_code | exts/omni.isaac.lab_quadruped_tasks/omni/isaac/lab_quadruped_tasks/cfg/quadruped_env_cfg.py:152-155 |
| The environment applies decimation 4 with sim.dt 1/200 s, episode_length_s 20.0 and seed 42 | upstream_code | exts/omni.isaac.lab_quadruped_tasks/omni/isaac/lab_quadruped_tasks/cfg/quadruped_env_cfg.py:300-306 |
| INSTALL_REQUIRES lists numpy, torch 2.4.0, torchvision, protobuf, h5py, tensorboard and moviepy | upstream_code | exts/omni.isaac.lab_quadruped_tasks/setup.py:15-29 |
| The extension package requires Python 3.10 or newer | upstream_code | exts/omni.isaac.lab_quadruped_tasks/setup.py:58 |

Limits: the driver declares none. The only bounds are the bridge-derived action space and `ticks` (1 to `max_ticks`,
10000 by default). The fake's action-space values are placeholders, not device limits; the configured task's action
space is created by Isaac Lab from the external robot asset and is not stated in the clone. The device is simulated
(R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:Isaac-Quadruped-AnymalD-Blind-Flat-v0`, level
F0 (analytic kinematics, no rigid-body dynamics, contacts, actuators, sensors or noise), determinism `seeded` with
`seed_control` `parameter`, physics timestep 5 ms (1/200 s, `quadruped_env_cfg.py:305`) with one environment step
covering decimation 4 (`:300`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The
gaps state what is not modelled and that the fake was never compared with the registered environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: quadruped, anymal-d, reinforcement-learning, isaac-lab, simulation, gymnasium

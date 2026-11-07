# Facts and tags for gh.enactic/openarm_isaac_lab

Every fact cites its source at commit `cb7ff7547bdb81f290591edb9302b4845b1d49a7`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository provides simulation and learning environments for the OpenArm robotic platform, built on NVIDIA Isaac Sim and Isaac Lab | vendor_doc | README.md:11 |
| Isaac Lab training environments cover reach, lift a cube and open a drawer | vendor_doc | README.md:16 |
| The repository has been tested with Ubuntu 22.04, Isaac Sim v5.1.0, Isaac Lab v2.3.0 and Python 3.11 | vendor_doc | README.md:19-23 |
| The package is installed with python -m pip install -e source/openarm | vendor_doc | README.md:81 |
| Teleoperation and sim-to-sim/sim-to-real transfer pipelines are under development | vendor_doc | README.md:17 |
| The unimanual reach task is registered with the gym id Isaac-Reach-OpenArm-v0 | upstream_code | source/openarm/openarm/tasks/manager_based/openarm_manipulation/unimanual/reach/config/__init__.py:21 |
| The entry_point of Isaac-Reach-OpenArm-v0 is isaaclab.envs:ManagerBasedRLEnv, a class outside this repository | upstream_code | source/openarm/openarm/tasks/manager_based/openarm_manipulation/unimanual/reach/config/__init__.py:22 |
| The env_cfg_entry_point of Isaac-Reach-OpenArm-v0 is joint_pos_env_cfg:OpenArmReachEnvCfg | upstream_code | source/openarm/openarm/tasks/manager_based/openarm_manipulation/unimanual/reach/config/__init__.py:25 |
| OpenArmReachEnvCfg subclasses ReachEnvCfg and switches the scene robot to the unimanual OpenArm configuration | upstream_code | source/openarm/openarm/tasks/manager_based/openarm_manipulation/unimanual/reach/config/joint_pos_env_cfg.py:27-44 |
| The reach configuration sets a JointPositionActionCfg over openarm_joint.* with scale 0.5 and use_default_offset True as its arm action | upstream_code | source/openarm/openarm/tasks/manager_based/openarm_manipulation/unimanual/reach/config/joint_pos_env_cfg.py:66-73 |
| The reach control step is two physics steps (decimation 2) and the physics timestep is 1/60 s | upstream_code | source/openarm/openarm/tasks/manager_based/openarm_manipulation/unimanual/reach/reach_env_cfg.py:268-273 |
| The reach episode is 12.0 s long | upstream_code | source/openarm/openarm/tasks/manager_based/openarm_manipulation/unimanual/reach/reach_env_cfg.py:270 |
| The policy observation group concatenates the joint_pos, joint_vel, pose_command and actions terms | upstream_code | source/openarm/openarm/tasks/manager_based/openarm_manipulation/unimanual/reach/reach_env_cfg.py:117-154 |
| The joint_pos and joint_vel observation terms read the seven joints openarm_joint1 to openarm_joint7 | upstream_code | source/openarm/openarm/tasks/manager_based/openarm_manipulation/unimanual/reach/reach_env_cfg.py:117-146 |
| The pose command is sampled in pos_x 0.25 to 0.35, pos_y -0.2 to 0.2, pos_z 0.3 to 0.4, roll -pi/6 to pi/6, pitch pi/2 and yaw -pi/9 to pi/9 | upstream_code | source/openarm/openarm/tasks/manager_based/openarm_manipulation/unimanual/reach/reach_env_cfg.py:84-96 |
| The pose command is resampled every 4 s | upstream_code | source/openarm/openarm/tasks/manager_based/openarm_manipulation/unimanual/reach/reach_env_cfg.py:87 |
| The joint_pos and joint_vel observations add uniform noise between -0.01 and 0.01 | upstream_code | source/openarm/openarm/tasks/manager_based/openarm_manipulation/unimanual/reach/reach_env_cfg.py:130-145 |
| The default scene holds 4096 parallel environments | upstream_code | source/openarm/openarm/tasks/manager_based/openarm_manipulation/unimanual/reach/reach_env_cfg.py:254 |
| The robot asset declares velocity limits 2.175 for openarm_joint1 to openarm_joint4 and 2.61 for openarm_joint5 to openarm_joint7, and effort limits 40.0, 27.0 and 7.0 by joint group | upstream_code | source/openarm/openarm/tasks/manager_based/openarm_manipulation/assets/openarm_unimanual.py:51-63 |

Limits: the driver declares none. The only bounds the gateway enforces are `ticks` (1 to `max_ticks`, 10000 by
default) and whatever the environment's action space bounds are; the fake's action space is deliberately unbounded
because the upstream action envelope is built by Isaac Lab outside the clone. The device is simulated (R0), so no
limit is `operator_required` and no action is a machine hazard.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `isaaclab:Isaac-Reach-OpenArm-v0`, level F0 (an interface
stand-in, no physics), determinism `seeded` with `seed_control` `parameter`, timestep 33.33 ms (decimation 2 at a
1/60 s physics step, `reach_env_cfg.py:268-273`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and
restore. The gaps say what is not modelled and that the package's fake was never compared with an Isaac Lab run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable. The package never runs the robot: it is a simulation-environment driver, so the R2 floor of a
physical arm does not apply to it.

Tags: openarm, isaac-lab, isaac-sim, reinforcement-learning, simulation, gymnasium, reach

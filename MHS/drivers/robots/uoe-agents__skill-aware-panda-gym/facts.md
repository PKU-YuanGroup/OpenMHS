# Facts and tags for gh.uoe-agents/skill-aware-panda-gym

Every fact cites its source at commit `4910d3733da4df60991d5cd82e839e5eb16e6b74`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The project is the modified Panda-gym benchmark for evaluating skill-aware reinforcement-learning algorithms | vendor_doc | README.md:2 |
| The documented use is gym.make('PandaSkillAware-v3', render_mode='rgb_array', friction=1.0, mass=1.0) followed by reset() and step(action), which returns observation, reward, terminated, truncated and info | vendor_doc | README.md:20-26 |
| info['state'] is one of push, roll, pick and down | vendor_doc | README.md:27 |
| PandaSkillAware-v3 is registered with entry point skill_aware_panda_gym.envs:PandaPushEnv and max_episode_steps=50 | upstream_code | skill_aware_panda_gym/__init__.py:7-11 |
| PandaPushEnv is a RobotTaskEnv task environment | upstream_code | skill_aware_panda_gym/envs/__init__.py:70 |
| PandaPushEnv builds PyBullet with the requested render mode and renderer and a Panda robot in that simulation, with block_gripper=False and base_position [-0.6, 0.0, 0.0] | upstream_code | skill_aware_panda_gym/envs/__init__.py:107-108 |
| control_type selects end-effector control ('ee', the default) or joint control ('joints') | upstream_code | skill_aware_panda_gym/envs/__init__.py:76-77 |
| friction and mass are constructor arguments that default to 1.0 | upstream_code | skill_aware_panda_gym/envs/__init__.py:104-105 |
| set_obs_friction_mass writes the mass to the object body with changeDynamics and the lateral friction to the table body | upstream_code | skill_aware_panda_gym/envs/__init__.py:125-130 |
| The task wrapper's defaults are distance_threshold 0.05, goal_xy_range 0.3, goal_z_range 0.11, obj_xy_range 0.3 and object_height 1.0 | upstream_code | skill_aware_panda_gym/envs/__init__.py:24-28 |
| The environment constructs the task with the requested object_height and goal_z_range=0.0 | upstream_code | skill_aware_panda_gym/envs/__init__.py:109 |
| get_state labels the object 'pick' when it is above 0.021 with no table contact and both finger contacts, 'roll' when it is above 0.021 otherwise, 'push' when it is between 0.019 and 0.21, and 'down' otherwise | upstream_code | skill_aware_panda_gym/envs/__init__.py:141-153 |
| PandaPushEnv.step applies the action, advances the simulation once, sets truncated=False, and returns the five-value Gymnasium result with info['state'] | upstream_code | skill_aware_panda_gym/envs/__init__.py:155-166 |
| The installation requirements are gymnasium>=0.26, pybullet, numpy, scipy and panda-gym, with no serial, VISA or vendor-SDK dependency | upstream_code | setup.py:23 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box` with per-element bounds; the class's `action.values` limit has no source and the derived ref
`action_space of the fake backend .fake:FakePandaPushEnv`). The clone does not state that space: it is built by
panda-gym's `Panda` class in the external dependency, so this page does not claim it as a sourced limit, and the fake's
Box is test data (`fake.py` marks it `# placeholder`). The device is simulated (R0), so no limit is `operator_required`
and no site-limits overlay exists.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `python:skill_aware_panda_gym.fake:FakePandaPushEnv`, level
F0 (analytic kinematics, no dynamics), determinism `seeded` with `seed_control` `parameter`, `timestep_ms` 0 because
the clone states no timestep, `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps
say what is not modelled, that the action and observation shapes come from the external panda-gym and are test data
in the fake, and that the fake was never compared with an installed upstream or a PyBullet run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (the upstream environment exposes no native
stop); after it no step or reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no
operator for that), and the state stays readable.

Tags: panda, franka, push, pybullet, reinforcement-learning, simulation, gymnasium, skill-aware

# Facts and tags for gh.ianyangchina/pybullet_multigoal_gym

Every fact cites its source at commit `54b50b8de3d2d58f88f8d4036aafc0858ed3d1e5`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The package is a PyBullet implementation of the OpenAI Gym multi-goal robotics environment and uses a Kuka iiwa14 7DoF arm with a robotiq85 or a parallel jaw gripper | vendor_doc | README.md:9-11 |
| Observation is a dictionary containing the state, desired goal, achieved goal and other sensory data | vendor_doc | README.md:60 |
| The documented way to create an environment is the make_env(...) method | vendor_doc | README.md:62 |
| Importing pybullet_multigoal_gym imports register, make and registry from the legacy gym.envs.registration and defines make_env; the module body contains no register call | upstream_code | pybullet_multigoal_gym/__init__.py:1-11 |
| make_env registers the id only when it is called, inside the block that checks whether the id is already in registry.env_specs | upstream_code | pybullet_multigoal_gym/__init__.py:85-132 |
| make_env maps task 'block_stack' to the entry point pybullet_multigoal_gym.envs.task_envs.kuka_multi_step_envs:KukaBlockStackEnv | upstream_code | pybullet_multigoal_gym/__init__.py:33-35 |
| make_env builds the environment id from the task tag, gripper, render, reward, joint-control and image flags and appends -v0 | upstream_code | pybullet_multigoal_gym/__init__.py:56-83 |
| make_env registers the multi-block tasks with the task constructor kwargs and the caller's max_episode_steps | upstream_code | pybullet_multigoal_gym/__init__.py:107-131 |
| make_env returns gym.make(env_id) | upstream_code | pybullet_multigoal_gym/__init__.py:178 |
| make_env defaults render to False | upstream_code | pybullet_multigoal_gym/__init__.py:4 |
| make_env passes render into the block-stack registration kwargs | upstream_code | pybullet_multigoal_gym/__init__.py:113 |
| KukaBlockStackEnv's own constructor defaults render to True | upstream_code | pybullet_multigoal_gym/envs/task_envs/kuka_multi_step_envs.py:7 |
| The README says to make the environment with render=False for a headless experiment | vendor_doc | README.md:64 |
| make_env defaults max_episode_steps to 50 | upstream_code | pybullet_multigoal_gym/__init__.py:6 |
| KukaBlockStackEnv defaults distance_threshold to 0.05 and num_block to 5 | upstream_code | pybullet_multigoal_gym/envs/task_envs/kuka_multi_step_envs.py:7-10 |
| KukaBlockStackEnv passes grasping=True, joint_control=False, end_effector_start_on_table=False, obj_range=0.15 and target_range=0.15 to its multi-block base class | upstream_code | pybullet_multigoal_gym/envs/task_envs/kuka_multi_step_envs.py:23-32 |
| BaseBulletMGEnv is a gym.Env | upstream_code | pybullet_multigoal_gym/envs/base_envs/base_env.py:10 |
| The base environment's constructor defaults are seed 0, gravity 9.81, timestep 0.002 s and frame_skip 20, and it seeds itself with seed 0 | upstream_code | pybullet_multigoal_gym/envs/base_envs/base_env.py:15-24 |
| dt is timestep * frame_skip; the comment gives 0.002 * 20 = 0.04 seconds at the defaults | upstream_code | pybullet_multigoal_gym/envs/base_envs/base_env.py:112-118 |
| seed delegates to gym.utils.seeding.np_random and returns [seed] | upstream_code | pybullet_multigoal_gym/envs/base_envs/base_env.py:120-122 |
| reset(test=False) resets the robot and the task and returns the observation | upstream_code | pybullet_multigoal_gym/envs/base_envs/base_env.py:124-128 |
| step applies the action, computes the reward from the achieved and desired goals, and returns (obs, reward, False, info) with info['goal_achieved'] | upstream_code | pybullet_multigoal_gym/envs/base_envs/base_env.py:130-138 |
| The environment owns an in-process PyBullet BulletClient (DIRECT by default, GUI when render=True) and sets gravity, fixedTimeStep = timestep * frame_skip, solver iterations and substeps; real-time simulation is off | upstream_code | pybullet_multigoal_gym/envs/base_envs/base_env.py:203-220 |
| The action space is the robot's action space | upstream_code | pybullet_multigoal_gym/envs/base_envs/base_env.py:84-85 |
| For non-image observations the observation space is a Dict of four Box(-inf, inf) float32 members named state, policy_state, achieved_goal and desired_goal | upstream_code | pybullet_multigoal_gym/envs/base_envs/base_env.py:86-92 |
| With grasping True, joint_control False and no primitive or end-effector rotation control, Kuka.action_space is Box(-1, 1) with 4 elements | upstream_code | pybullet_multigoal_gym/robots/kuka.py:108-113 |
| Each block contributes world position, relative position to the gripper, world euler orientation, and relative linear and angular velocities to the state, and its relative position to the policy state | upstream_code | pybullet_multigoal_gym/envs/base_envs/kuka_multi_step_base_env.py:264-280 |
| state is the gripper xyz, finger closeness, gripper velocity and finger velocity followed by the block states; policy_state is the gripper xyz, finger closeness and the relative block positions | upstream_code | pybullet_multigoal_gym/envs/base_envs/kuka_multi_step_base_env.py:282-283 |
| state and policy_state are clipped to [-5, 5] | upstream_code | pybullet_multigoal_gym/envs/base_envs/kuka_multi_step_base_env.py:306-307 |
| The observation dict has keys observation, policy_state, achieved_goal and desired_goal | upstream_code | pybullet_multigoal_gym/envs/base_envs/kuka_multi_step_base_env.py:317-320 |
| The sparse reward is -not_achieved and the dense reward is -distance, where distance is the Euclidean norm of the achieved minus desired goal and not_achieved is distance > distance_threshold | upstream_code | pybullet_multigoal_gym/envs/base_envs/kuka_multi_step_base_env.py:338-345 |
| setup.py declares the package, its URDF/STL/DAE package_data and no install_requires | upstream_code | setup.py:10-28 |
| The runtime dependencies are setuptools~=50.3.0, pybullet~=3.0.6, gym~=0.17.3, numpy~=1.19.4, numba and numpy-quaternion~=2020.11.2.17.0.49 | upstream_code | requirements.txt:1-6 |

Limits: the driver declares none. The only bound is the environment's action space, which the Gymnasium bridge
derives from `Box(-1, 1)` (`action.values` per element, with the source `upstream_code` and the ref
`pybullet_multigoal_gym/robots/kuka.py:113`), and `ticks` (1 to `max_ticks`, 10000 by default). The
device is simulated (R1, simulation stepping), so no limit is `operator_required` and no `site-limits.example.json`
is needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): the default (fake) backend's engine is
`pybullet:KukaBlockStackParallelGripSparseReward-v0 (kinematic fake stand-in)`, level F0 (placeholder kinematic
transitions, no PyBullet, contacts, actuators or sensors), determinism `seeded` with `seed_control` `parameter`,
timestep 40 ms (`dt = timestep * frame_skip = 0.002 * 20`, `base_env.py:112-118`), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled and that the fake was not
compared with the upstream environment. The `sim` backend runs the real PyBullet environment, which this F0 contract
does not describe; the gaps say so and no sim trajectory was measured here.

The `sim` backend is `_build_sim_env` in `driver.py`: it calls the upstream's documented
`make_env(task='block_stack')` (`README.md:62`, `pybullet_multigoal_gym/__init__.py:4-11,178`). Importing
`pybullet_multigoal_gym` only defines `make_env`; its `register(...)` calls run when it is called
(`__init__.py:85-132`), so there is no import-time registration for `env_module` to name. `make_env` selects
`KukaBlockStackEnv` (`:33-35`), registers `KukaBlockStackParallelGripSparseReward-v0` with the task kwargs and
`max_episode_steps=50` (`:56-83`, `:107-131`) and returns `gym.make(env_id)` (`:178`); `render` defaults to False
(`:4`), the headless path the README documents (`README.md:64`). No upstream class, module, method or object is
patched or replaced.

Safety: simulated R1 device (simulation stepping, MHS/spec/04-safety.md section 2.1). The e-stop is the runtime's
software latch (no native stop exists); after it no step or reset is accepted until `mhs.safety.reset` clears the
latch (a simulator needs no operator for that), and the state stays readable. There is no hardware backend, no
physical e-stop and no hardware run.

Tags: kuka, iiwa14, block-stack, manipulation, pybullet, reinforcement-learning, simulation, gym

## Observation lengths for the deployed configuration

The default configuration has five blocks (`kuka_multi_step_envs.py:10`). The state is the eight gripper values
(`kuka_multi_step_base_env.py:282-283`) plus 15 values per block (`:264-280`), the policy state is four gripper
values plus three values per block, and each goal is three values per block. With five blocks those are 83, 19, 15
and 15 values. The driver's fake returns lists of exactly those lengths; the numbers are an arithmetic consequence
of the cited composition and were not measured in a PyBullet run.

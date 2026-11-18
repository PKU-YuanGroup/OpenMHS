# Facts and tags for gh.cooper-group-uol-robotics/panda_chemistry_gym

Every fact cites its source at commit `10e82317010f662f5f8f0602e068447d170d9bb0` (`upstream_code`: code or a comment
of the clone). The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the
driver, not from this page.

| fact | source | ref |
|---|---|---|
| Capping_Env builds a PyBullet simulation and a Panda robot with the gripper enabled, base position [-0.6, 0, 0], ee control and the Capping task | upstream_code | custom_envs/envs/Insertion_PandaTasks/Capping/Capping_PandaTask.py:15-19 |
| Capping_Env is registered as Capping{}{}-v1 in both control and reward variants, with max_episode_steps=100; the ee/sparse instance is Capping-v1 | upstream_code | custom_envs/__init__.py:8-19 |
| Importing custom_envs runs its module-level registration: line 6 imports register from gym.envs.registration and lines 14-19 register Capping-v1 in the legacy gym registry | upstream_code | custom_envs/__init__.py:6-19 |
| Capping._create_scene builds the cap mesh paths as os.getcwd()+'/Objects/...', so the upstream constructor resolves those meshes relative to the process working directory | upstream_code | custom_envs/envs/Insertion_Tasks/Capping/Capping_Task.py:50-51 |
| In ee control the Panda action space is Box(-1.0, 1.0) with four values: three displacement values and one gripper value (3 + 1 because the gripper is not blocked) | upstream_code | custom_envs/envs/robots/panda.py:22-24 |
| Panda.set_action clips the action to the action space low and high before using it | upstream_code | custom_envs/envs/robots/panda.py:44-46 |
| In ee control the first three action values are an end-effector displacement scaled by 0.05 | upstream_code | custom_envs/envs/robots/panda.py:64-68 |
| The gripper action value is scaled by 0.2 and added to the current finger width | upstream_code | custom_envs/envs/robots/panda.py:56-59 |
| The Panda observation is seven values: end-effector position (3), end-effector velocity (3) and finger width (1) | upstream_code | custom_envs/envs/robots/panda.py:83-93 |
| The Capping task observation is nine values: cap base position (3), rotation (3) and velocity (3) | upstream_code | custom_envs/envs/Insertion_Tasks/Capping/Capping_Task.py:152-159 |
| RobotTaskEnv._get_obs concatenates the robot and task observations and returns a dict with the keys observation, achieved_goal and desired_goal | upstream_code | panda_chemistry_gym/core.py:258-267 |
| The observation space is a Dict of three float32 Boxes bounded -200.0 to 200.0, for observation, desired_goal and achieved_goal; the action space is a Box(-1.0, 1.0) with the robot action shape | upstream_code | panda_chemistry_gym/core.py:245-253 |
| The achieved goal is six values: cap position (3) and end-effector position (3) | upstream_code | custom_envs/envs/Insertion_Tasks/Capping/Capping_Task.py:162-166 |
| The desired goal is six values: cap target position (3) and vial end-effector position (3) | upstream_code | custom_envs/envs/Insertion_Tasks/Capping/Capping_Task.py:191-195 |
| Capping.reset adds random xy offsets in [0, 0.05) to the cap and cap holder, to the vial and vial holder, and twice to the goal | upstream_code | custom_envs/envs/Insertion_Tasks/Capping/Capping_Task.py:169-188 |
| The Capping task draws those placement offsets from Python's global random module, not from a seeded numpy generator | upstream_code | custom_envs/envs/Insertion_Tasks/Capping/Capping_Task.py:172-173 |
| RobotTaskEnv.reset(seed) seeds the task's np_random generator, resets the robot and task, and returns the observation instead of an (observation, info) pair | upstream_code | panda_chemistry_gym/core.py:269-274 |
| The Capping task distance_threshold defaults to 0.015 | upstream_code | custom_envs/envs/Insertion_Tasks/Capping/Capping_Task.py:21 |
| is_success returns True when distance(achieved_goal, desired_goal) is below the task's distance_threshold | upstream_code | custom_envs/envs/Insertion_Tasks/Capping/Capping_Task.py:198-201 |
| The reward is -1.2 while the cap touches the cap holder, otherwise -distance to the goal, and 1.0 when the task is already successful | upstream_code | custom_envs/envs/Insertion_Tasks/Capping/Capping_Task.py:204-222 |
| RobotTaskEnv.step applies the robot action, advances the simulation, and returns (observation, reward, done, info) with done always False; success is only info['is_success'] | upstream_code | panda_chemistry_gym/core.py:289-298 |
| The PyBullet wrapper defaults to 50 substeps, sets a 1/500 s physics timestep, gravity -9.81 m/s^2, and runs one physics step per substep | upstream_code | panda_chemistry_gym/pybullet.py:25-54 |
| One PyBullet.step() therefore advances 50 * (1/500) = 0.1 s of simulated time, the control interval | upstream_code | panda_chemistry_gym/pybullet.py:46-54 |
| The environment is simulated only: close() disconnects the PyBullet client and no hardware transport exists | upstream_code | panda_chemistry_gym/pybullet.py:56-58 |

Limits: the driver declares none of its own. The only bound is the action space, which the bridge derives from the
environment (`Box(-1.0, 1.0)` with four elements: `action.values`, with no source and the ref
`action_space of the fake backend .fake:FakeCappingEnv`). `ticks` is bounded by the bridge (1 to `max_ticks`, 10000 by
default). The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `pybullet:panda_chemistry_gym/Capping-v1`, level F1
(PyBullet rigid-body dynamics with contacts in the upstream model), determinism `seeded` with `seed_control`
`parameter` on the fake (the upstream task draws its offsets from Python's global random, `Capping_Task.py:172-173`),
physics timestep 2 ms with 50 substeps (100 ms control interval, `pybullet.py:25-54`), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore. The gaps say what the fake does not model and that it was not
compared with the upstream environment.

Sim path (`driver.py`): `env_module = "custom_envs"` names the module whose import runs the module-level
registration at `custom_envs/__init__.py:6-19` (the id is looked up in legacy `gym`). The `sim` backend
`_build_sim_capping` imports `custom_envs`, computes the clone root from `custom_envs.__file__`, and enters that
root while the upstream `Capping._create_scene` resolves
its `os.getcwd()+'/Objects/...'` mesh paths (`Capping_Task.py:50-51,73-74,98-99,129-130`), calls the registration's
own `gym.make("Capping-v1")` (the real `Capping_Env` of `Capping_PandaTask.py:15-19` with the registration's
`reward_type="sparse"` and `control_type="ee"` kwargs and 100-step limit, `custom_envs/__init__.py:8-19`), and
restores the working directory. Object meshes are resolved from that checkout. Install `gym==0.23.1`,
`gym-robotics==0.1.0`, `pybullet==3.2.7` and `numpy<2`: the upstream imports gym and gym_robotics
(`panda_chemistry_gym/core.py:4-8`) and PyBullet (`panda_chemistry_gym/pybullet.py:8-10`), and documents its legacy
gym stack at `README.md:171-181`. The clone has no packaging metadata, so its pinned root must be on `PYTHONPATH`.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable. The upstream `close()` only disconnects PyBullet.

Tags: panda, pybullet, capping, insertion, reinforcement-learning, simulation, gymnasium

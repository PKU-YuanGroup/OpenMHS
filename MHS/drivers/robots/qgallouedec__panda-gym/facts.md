# Facts and tags for gh.qgallouedec/panda-gym

Every fact cites its source at commit `10c4d8adaab07d8a29b2f8dc0aa85f8edd8532ae`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.rst) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| panda-gym is a set of robotic environments based on the PyBullet physics engine and gymnasium | vendor_doc | README.md:3 |
| The documented use is gym.make('PandaReach-v3', render_mode='human') followed by reset() and step(action) | vendor_doc | docs/guide/quick_start.rst:6-19 |
| PandaReach-v3 is registered with entry point panda_gym.envs:PandaReachEnv, kwargs reward_type='sparse' and control_type='ee', and max_episode_steps=50 (100 only for Stack) | upstream_code | panda_gym/__init__.py:10-21 |
| PandaReachEnv builds the Panda robot with block_gripper=True, so the gripper is not part of the action | upstream_code | panda_gym/envs/panda_tasks.py:202 |
| Panda's action space is Box(-1.0, 1.0, shape=(n_action,)) in float32, with n_action 3 for end-effector control and 7 for joint control, plus one for the gripper when it is not blocked | upstream_code | panda_gym/envs/robots/panda.py:31-33 |
| An end-effector action moves the target by at most 0.05 per step and the target height is clipped to 0 or above | upstream_code | panda_gym/envs/robots/panda.py:81-86 |
| The Reach distance_threshold defaults to 0.05 and goal_range to 0.3 | upstream_code | panda_gym/envs/tasks/reach.py:15-16 |
| The Reach goal is drawn uniformly from goal_range_low [-0.15, -0.15, 0] to goal_range_high [0.15, 0.15, 0.3] | upstream_code | panda_gym/envs/tasks/reach.py:22-23 |
| distance is the Euclidean norm rounded to 6 decimals | upstream_code | panda_gym/utils.py:15-17 |
| Reach.is_success returns True when the distance is below the threshold | upstream_code | panda_gym/envs/tasks/reach.py:55-57 |
| The sparse Reach reward is -1 outside the threshold and 0 inside it; the dense reward is minus the distance | upstream_code | panda_gym/envs/tasks/reach.py:59-64 |
| Panda.get_obs returns the end-effector position and velocity, and omits the finger width when the gripper is blocked | upstream_code | panda_gym/envs/robots/panda.py:109-119 |
| Reach has no task-specific observation and its achieved goal is the end-effector position | upstream_code | panda_gym/envs/tasks/reach.py:39-44 |
| RobotTaskEnv concatenates the robot and task observations and adds the achieved and desired goals | upstream_code | panda_gym/envs/core.py:265-274 |
| The RobotTaskEnv observation space is a Dict of three Box(-10.0, 10.0) members | upstream_code | panda_gym/envs/core.py:237-243 |
| RobotTaskEnv.reset seeds gym.Env, gives the task the same generator, resets the robot and the task, and returns is_success | upstream_code | panda_gym/envs/core.py:276-286 |
| Panda.reset sets the neutral joint values | upstream_code | panda_gym/envs/robots/panda.py:121-126 |
| Reach.reset samples a new goal and places the target there | upstream_code | panda_gym/envs/tasks/reach.py:46-53 |
| RobotTaskEnv.step applies the action, advances the simulation once, terminates on task success, sets truncated=False and computes the reward | upstream_code | panda_gym/envs/core.py:316-325 |
| PyBullet sets the physics timestep to 1/500 s and exposes dt as timestep * n_substeps | upstream_code | panda_gym/pybullet.py:53-64 |
| n_substeps defaults to 20 | upstream_code | panda_gym/pybullet.py:28 |
| PyBullet.step advances n_substeps physics steps per call | upstream_code | panda_gym/pybullet.py:66-70 |
| The runtime dependencies are gymnasium>=0.26, pybullet, numpy<2 and scipy | upstream_code | setup.py:23 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box(-1.0, 1.0, shape=(3,))`: `action.values` from -1.0 to 1.0 per element, with the source `upstream_code` and the
ref `panda_gym/envs/robots/panda.py:31-33`), and `ticks` (1 to `max_ticks`, 10000 by default). The device is simulated
(R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:PandaReach-v3`, level F1 (a PyBullet rigid-body
model, no contact, actuator or sensor model validated for this package), determinism `seeded` with `seed_control`
`parameter`, timestep 40 ms (`1/500` s times the default `n_substeps` 20, `pybullet.py:53-64`), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled, that the fake applies the
50-step TimeLimit of the registration, that it draws goals with Python's random generator instead of numpy's, and that
its start position is test data that was never compared with a PyBullet run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: panda, franka, reach, pybullet, reinforcement-learning, simulation, gymnasium

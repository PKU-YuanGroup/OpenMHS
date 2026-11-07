# Facts and tags for gh.edvardsz/ur5_gym

Every fact cites its source at commit `d059332a01d320a48617d5a46edb9856f3a4c86d`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The README describes a deep reinforcement learning environment in Ignition Gazebo for a UR5 arm with an RG2 gripper | vendor_doc | README.md:2 |
| The README tells the user to install Ignition Gazebo before installing the package | vendor_doc | README.md:5 |
| setup.cfg install_requires lists gym-ignition and numpy | upstream_code | setup.cfg:22-24 |
| requirements.txt pins gym~=0.21.0, numpy~=1.22.3 and scipy~=1.8.0 | upstream_code | requirements.txt:1-3 |
| The package imports register from gym.envs.registration, the legacy Gym 0.21 API | upstream_code | src/gym_ur5/__init__.py:2 |
| ReachUR5-v0 is registered with entry_point gym_ignition.runtimes.gazebo_runtime:GazeboRuntime, max_episode_steps 100, agent_rate 2.5, physics_rate 100.0 and real_time_factor max_float | upstream_code | src/gym_ur5/__init__.py:8-18 |
| ReachDictUR5-v0 and PickAndPlaceUR5-v0 are also registered with max_episode_steps 50 and different task classes; this package serves ReachUR5-v0 only | upstream_code | src/gym_ur5/__init__.py:20-44 |
| gym_ur5.tasks.reach defines Reach(task.Task, abc.ABC) | upstream_code | src/gym_ur5/tasks/reach.py:22 |
| The workspace centre is [0.50143738, 0.15, 1.36] and the workspace volume is [0.4, 0.4, 0.4] | upstream_code | src/gym_ur5/tasks/reach.py:31-32 |
| The action space is Box(-1.0, 1.0, shape=(3,), float32) and the observation space is Box(-inf, inf, shape=(6,), float32) | upstream_code | src/gym_ur5/tasks/reach.py:37-49 |
| set_action adds action * 0.1 to the end-effector position and clamps every coordinate to the workspace centre +- half the volume | upstream_code | src/gym_ur5/tasks/reach.py:50-74 |
| get_observation returns the end-effector position concatenated with the target position, six values | upstream_code | src/gym_ur5/tasks/reach.py:76-81 |
| get_reward returns +1.0 when the distance to the target is below 0.05 and -1.0 otherwise | upstream_code | src/gym_ur5/tasks/reach.py:83-90 |
| get_info returns is_success True when the distance to the target is at most 0.05 | upstream_code | src/gym_ur5/tasks/reach.py:92-98 |
| is_done returns the task's _is_done flag | upstream_code | src/gym_ur5/tasks/reach.py:99-101 |
| reset_task clears _is_done and sets the eight joint position targets to the fixed configuration [1.47838380, -2.15699582, -0.000081469105, -2.52916159, 1.56735617, -0.0925439234, 0, 0] | upstream_code | src/gym_ur5/tasks/reach.py:103-111 |
| get_joints returns the six arm joints and the two RG2 finger joints | upstream_code | src/gym_ur5/tasks/reach.py:113-121 |
| get_target_position returns the base position of the RedPoint model | upstream_code | src/gym_ur5/tasks/reach.py:163-165 |
| get_ee_position returns the world position of the model's tool0 link | upstream_code | src/gym_ur5/tasks/reach.py:173-175 |
| The randomizer inserts the UR5RG2 model at [0.5, 0.5, 1.02] when the scene has no ur5_rg2 model | upstream_code | src/gym_ur5/randomizers/ur5_rg2_no_rand.py:59 |
| The workspace random target is drawn uniformly from the workspace box with numpy's global generator | upstream_code | src/gym_ur5/tasks/reach.py:167-171 |
| The UR5 has six arm joints with limits +-6.28319 rad and the RG2 two finger joints with limits 0 to 0.52359878 rad | upstream_code | src/gym_ur5/models/robots/ur5_rg2.py:104-113 |

Limits: the only declared bound is `action.values`, from -1.0 to 1.0, because the task's action space is
`Box(-1.0, 1.0, shape=(3,))` (`src/gym_ur5/tasks/reach.py:39-42`). The class contract also bounds `ticks` from 1 to
10000; that is catalogue metadata, not an upstream statement, so the driver does not re-declare it and the class
schema supplies it. The episode length is 100 (`src/gym_ur5/__init__.py:11`), replicated by `step`. The device is
simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gym-ignition:ReachUR5-v0` (Ignition Gazebo; this package
serves the task class with a kinematic fake), level F0 (the fake models the task's position arithmetic directly and
has no dynamics), determinism `seeded` with `seed_control` `parameter`, timestep 400 ms (one agent step at
agent_rate 2.5, `src/gym_ur5/__init__.py:14`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and
restore. The gaps state that the fake is not Gazebo, that its start and target are placeholder test data, that a seed
does not change the fake's scene, that the upstream Gym wrappers are replicated in the driver, and that
ReachDictUR5-v0 and PickAndPlaceUR5-v0 are NOT COVERED.

Defaults and warnings: the driver's declared default seed is 0 until a reset or `cap.world.seed.v1` supplies one, and
the state's reward is 0.0 before the first step (the bridge's default too). `cap.world.seed.v1` only records the seed
of the next reset and makes no native call, because the task class has no seed method; the gate reports that as
`G6.NO_NATIVE_CALL`, which is the expected warning for a simulator seed (PLAYBOOK.md section 8).

Safety: simulated R0 device. No physical UR5 or RG2 is driven. The e-stop is the runtime's software latch (no native
stop exists); after it no step, reset or seed is accepted until `mhs.safety.reset` clears the latch, and the world
state stays readable. This package is model-authored and unreviewed (`driver.lock.json` `reviewed_by` is null) and no
hardware was attached or run.

Tags: gripper, ignition-gazebo, reinforcement-learning, robot, rg2, simulation, ur5

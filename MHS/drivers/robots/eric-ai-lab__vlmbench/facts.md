# Facts and tags for gh.eric-ai-lab/vlmbench

Every fact cites its source at commit `479bd17b7d80645002af74f142a29dfe8b428876`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

The card's entry symbol is `amsolver.gym.vlmbench_env:VLMBenchEnv` at `amsolver/gym/vlmbench_env.py:14`; it is
confirmed in the clone. The driver serves the state environment registered as `drop_pen_color-state-v0`
(amsolver/gym/__init__.py:10-26). It is a simulated Gymnasium environment, so the `GymnasiumDriver` family expresses
the interface (`cap.world.step.v1`, `cap.world.reset.v1`, `cap.world.seed.v1`); no direct driver or `native.py` is
needed.

| fact | source | ref |
|---|---|---|
| VLMBenchEnv is a gymnasium.Env: the class is declared as `class VLMBenchEnv(gym.Env)` | upstream_code | amsolver/gym/vlmbench_env.py:14 |
| VLMBenchEnv takes a task class and an observation_mode of 'state' or 'vision'; any other mode raises ValueError | upstream_code | amsolver/gym/vlmbench_env.py:19-31 |
| The wrapper builds an amsolver Environment with ArmActionMode.ABS_JOINT_VELOCITY, launches it headlessly and gets the task from it | upstream_code | amsolver/gym/vlmbench_env.py:32-36 |
| The action space is Box(low=-1.0, high=1.0, shape=(Environment.action_size,)) | upstream_code | amsolver/gym/vlmbench_env.py:40-41 |
| The supported-robot table gives the panda 7 arm joints | upstream_code | amsolver/environment.py:41-47 |
| Action_size is the arm action size plus one gripper value, and for ABS_JOINT_VELOCITY the arm action size is the supported arm's joint count | upstream_code | amsolver/environment.py:188-207 |
| The state observation space is Box(-inf, inf, shape=obs.get_low_dim_data().shape) | upstream_code | amsolver/gym/vlmbench_env.py:43-45 |
| Vision mode is a Dict of the state plus left_shoulder_rgb, right_shoulder_rgb, wrist_rgb and front_rgb images | upstream_code | amsolver/gym/vlmbench_env.py:46-59 |
| VLMBenchEnv.reset calls task.reset() and returns the extracted observation with the descriptions list added | upstream_code | amsolver/gym/vlmbench_env.py:95-99 |
| VLMBenchEnv.step calls task.step(action) and returns (observation, reward, terminate, {}) | upstream_code | amsolver/gym/vlmbench_env.py:101-103 |
| TaskEnvironment.step treats the last action value as the gripper command and the rest as the arm action | upstream_code | amsolver/task_environment.py:239-241 |
| The arm action length must equal the number of arm joints | upstream_code | amsolver/task_environment.py:259-260 |
| The gripper command is open above 0.5 and closed below 0.5; exactly 0.5 keeps the current state | upstream_code | amsolver/task_environment.py:251-254 |
| TaskEnvironment.step returns float(success) as the reward and the task's terminate flag, with 1.0 when a success occurred along a path and 0.5 for a grasp success | upstream_code | amsolver/task_environment.py:422-430 |
| Observation.get_low_dim_data concatenates gripper_open first, then the non-None joint velocities, joint positions, joint forces, gripper pose, gripper joint positions, gripper touch forces and task low-dimensional state | upstream_code | amsolver/backend/observation.py:72-84 |
| The scene fills joint velocities, joint positions, gripper_open (1.0 when the gripper opening is above 0.9), gripper_pose (the tip pose), gripper joint positions and the task state | upstream_code | amsolver/backend/scene.py:287-314 |
| amsolver.gym registers every task file under vlm/tasks as <task>-state-v0 and <task>-vision-v0 with entry point amsolver.gym:VLMBenchEnv | upstream_code | amsolver/gym/__init__.py:10-26 |
| TASKS_PATH is ../../vlm/tasks relative to the amsolver/backend package, so the task classes are read from the clone tree | upstream_code | amsolver/backend/task.py:25 |
| Environment.launch creates a PyRep and launches task_design.ttt headlessly | upstream_code | amsolver/environment.py:136-138 |
| TaskEnvironment declares a module constant _DT = 0.05 | upstream_code | amsolver/task_environment.py:27 |
| The registration calls set no max_episode_steps, so a state environment has no truncation wrapper | upstream_code | amsolver/gym/__init__.py:13-26 |
| The documented Gymnasium example makes drop_pen_color-vision-v0, the vision id of the same task | vendor_doc | examples/gym_test.py:42 |
| The AMSolver install instructions require CoppeliaSim 4.1.0 and PyRep | vendor_doc | README.md:20 |

Limits: the driver declares none. The only numeric bound is the action values, which the family bridge derives from the
environment's action space (`Box(-1.0, 1.0, (8,))` at `amsolver/gym/vlmbench_env.py:40-41` and
`amsolver/environment.py:41-47`, `:188-207`); the step input `ticks` is bounded by the bridge's configured
`max_ticks`. The device is simulated (R0), so no limit is `operator_required` and there is no
`site-limits.example.json`. The panda's 7 joints and the one gripper value give the 8-element action; the clone's
`SUPPORTED_ROBOTS` table gives other arms 6 or 7 joints, so the bound belongs to the configured environment and is
not hard-coded as a driver Limit.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:drop_pen_color-state-v0
(AMSolver/CoppeliaSim)`, level F0 (a kinematic joint integration, no contacts, dynamics, actuator, sensor or noise
model), determinism `seeded` with `seed_control` `parameter`, timestep 50 ms (the fake's step uses the clone's
`_DT = 0.05`, `amsolver/task_environment.py:27`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot
and restore. The gaps say what is not modelled, that the upstream step is stored in the binary `task_design.ttt`, that
the fake's 29-element state is only the prefix of the real vector, that vision images are 1x1 placeholders, and that
the fake was never compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: vlmbench, manipulation, benchmark, reinforcement-learning, simulation, gymnasium

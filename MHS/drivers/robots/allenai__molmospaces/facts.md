# Facts and tags for gh.allenai/molmospaces

Every fact cites its source at commit `713fd12ab593c3bbb4abfaa76622e14249aa36b3`: `upstream_code` is a Python
file of the clone and `vendor_doc` is a text file of the clone (`docs/`). The same facts are written into
`driver.py` (`facts = [...]`); the generated reference file reads them from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| GymEnv is the molmospaces gymnasium environment class; it subclasses gymnasium.Env | upstream_code | molmo_spaces/tasks/gym_env.py:48 |
| GymEnv wraps a MolmoSpaces task sampler and keeps the current episode's task on env.task | upstream_code | molmo_spaces/tasks/gym_env.py:49-53 |
| The env id namespace is MolmoSpaces | upstream_code | molmo_spaces/tasks/gym_env.py:42 |
| An environment id is NAMESPACE/<ConfigName>-v<version> | upstream_code | molmo_spaces/tasks/gym_env.py:210 |
| The upstream gym compatibility guide builds the Franka pick environment with the id MolmoSpaces/FrankaPickDroidDataGenConfig-v0 | vendor_doc | docs/gym_compatibility.md:21 |
| FrankaPickDroidDataGenConfig is registered in the data generation config registry | upstream_code | molmo_spaces/data_generation/config/object_manipulation_datagen_configs.py:71 |
| GymEnv deliberately declares no action_space: actions are dicts keyed by move group (arm, gripper, etc.) | upstream_code | molmo_spaces/tasks/gym_env.py:74-76 |
| GymEnv deliberately declares no observation_space: observations are list[dict], one per batch element | upstream_code | molmo_spaces/tasks/gym_env.py:76-78 |
| The gym compatibility guide states observations are list[dict], one per batch element, and the key set can change between resets | vendor_doc | docs/gym_compatibility.md:84-86 |
| Only n_batch == 1 is supported; a larger batch is refused | upstream_code | molmo_spaces/tasks/gym_env.py:165-171 |
| The only reset options are house_index and force_advance_scene | upstream_code | molmo_spaces/tasks/gym_env.py:44-45 |
| reset(seed, options) samples a new task and returns task.reset() | upstream_code | molmo_spaces/tasks/gym_env.py:144-178 |
| reset closes the previous task before sampling the next one | upstream_code | molmo_spaces/tasks/gym_env.py:155-161 |
| step delegates to the current task's step with the action dict | upstream_code | molmo_spaces/tasks/gym_env.py:181-184 |
| A reset with a seed calls task_sampler.seed_task_sampling(seed) | upstream_code | molmo_spaces/tasks/gym_env.py:144-146 |
| seed_task_sampling seeds random, numpy and torch globally | upstream_code | molmo_spaces/tasks/task_sampler.py:428-431 |
| The PickBaseConfig control timestep is 2.0 ms and its task horizon is 500 steps | upstream_code | molmo_spaces/configs/base_pick_config.py:39-42 |
| A task is truncated when episode_step_count reaches the task horizon | upstream_code | molmo_spaces/tasks/task.py:423-424 |
| A task step returns observation, reward, terminated, truncated and info | upstream_code | molmo_spaces/tasks/task.py:379 |
| The task info carries cumulative_reward and num_steps_taken per batch element | upstream_code | molmo_spaces/tasks/task.py:463-472 |
| RobotJointPositionSensor returns the robot joint positions as a dict keyed by move group | upstream_code | molmo_spaces/env/sensors.py:344-361 |
| The pick task sensor suite registers the qpos sensor with uuid qpos and max_joints 9 | upstream_code | molmo_spaces/env/sensors.py:1017 |
| Franka's initial qpos has 7 arm joints and 2 gripper joints | upstream_code | molmo_spaces/configs/robot_configs.py:150-153 |
| register_configs registers every config with entry point molmo_spaces.tasks.gym_env:GymEnv and max_episode_steps None | upstream_code | molmo_spaces/tasks/gym_env.py:227-233 |
| Registration passes order_enforce=False so gymnasium.make returns the GymEnv itself | upstream_code | molmo_spaces/tasks/gym_env.py:237-241 |
| render returns an RGB array and does not require render_mode to be set | upstream_code | molmo_spaces/tasks/gym_env.py:186-198 |
| close closes the current task and closes the sampler only when the env built it | upstream_code | molmo_spaces/tasks/gym_env.py:199-205 |
| A reset samples an episode and can load a scene and compile a MuJoCo model, which takes seconds | vendor_doc | docs/gym_compatibility.md:88-90 |

## Limits

The driver declares no `Limit`. MolmoSpaces publishes no action space, so the bridge serves `cap.world.step.v1`
with an open `action` object and no action bound; `ticks` keeps the family schema bound (1 to `max_ticks`, 10000)
and `cap.world.seed.v1` keeps its non-negative integer schema. The device is simulated R0, so no numeric input
needs an operator-required bound. The `timestep_ms` of the fidelity contract is the selected config's control
timestep (2.0 ms, `base_pick_config.py:39`), not a write limit.

## Fidelity contract

`driver.py` declares level F0 because the served fake is a kinematic/analytic episode model: one tick is one
2 ms control step, `realtime_factor` is 0, the clock is `lockstep`, reset is full, and no snapshot/restore is
offered because `GymEnv` exposes no state get/set. Determinism is `seeded` with `seed_control` `parameter`: the
fake re-seeds its own `random.Random` on a seeded reset, while upstream's `seed_task_sampling` reseeds Python's
`random`, numpy and torch globally. The `gaps` state that no MuJoCo dynamics, contacts, actuators, sensors,
cameras or object interaction are modelled and that the observation is reduced to the qpos sensor. The fake was
not compared with a real MuJoCo run and no physical device was involved.

## Safety

The device is simulated (R0) and has no hardware backend. An e-stop is the runtime's software latch (no native
stop exists): after it, no step, reset or seed is accepted until `mhs.safety.reset` clears the latch, and the
world state stays readable. There is no `estop_physical_ref` because there is no physical stop to cite.

## Evidence

The package is model-authored and unreviewed (`driver.lock.json` `authored_by` kind `model`, `reviewed_by`
null). Its evidence is `contract_checked`; it is checked on the fake backend only and no hardware or real
simulator run is claimed.

Tags: molmospaces, gymnasium, simulation, reinforcement-learning, franka, mujoco

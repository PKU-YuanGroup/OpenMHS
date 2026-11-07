# Facts and tags for gh.seohongpark/ocbench

Every fact cites its source at commit `6939a1e84f7ce9dbdd20c9f80d4cf335e8f83b49`: `vendor_doc` (a text file of the
clone, here README.md) or `upstream_code` (`path/in/clone:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The README's quick-start example makes block-cpu-single-task1-v0 and steps it with an action sampled from its action space | vendor_doc | README.md:62-70 |
| block-cpu-single-task1-v0 is registered with entry point ocbench.envs.block_env:BlockEnv, max_episode_steps=1250 and kwargs env_type='single', task_id=1 | upstream_code | ocbench/__init__.py:74-79 |
| ocbench.make returns gymnasium.make(env_name, **kwargs) for CPU environments | upstream_code | ocbench/__init__.py:35-44 |
| BlockEnv subclasses ManipulationEnv and the single env_type installs one cube | upstream_code | ocbench/envs/block_env.py:9-21 |
| The single task is named move and its goal position is [0.425, 0.0, 0.03] | upstream_code | ocbench/envs/block_env.py:58-65 |
| The action space is a Box of seven float32 values from -1 to 1 | upstream_code | ocbench/envs/manipulation_env.py:107-114 |
| The per-joint action deltas are 0.18, 0.18, 0.18, 0.36, 0.36, 0.36 and 0.12 times action_delta_scale | upstream_code | ocbench/envs/manipulation_env.py:79-82 |
| unnormalize_action clips every action value to [-1, 1] and multiplies it by the joint action deltas | upstream_code | ocbench/envs/manipulation_env.py:120-122 |
| ManipulationEnv defaults physics_timestep to 0.002 s and control_timestep to 0.02 s | upstream_code | ocbench/envs/manipulation_env.py:13-25 |
| set_timesteps sets the number of physics steps per control step to control_timestep divided by physics_timestep | upstream_code | ocbench/envs/env.py:271-288 |
| CustomMuJoCoEnv.step applies the action, steps the model nstep times, computes the flags, observation and reward, and returns the five-tuple | upstream_code | ocbench/envs/env.py:222-244 |
| The state observation concatenates joint positions, joint velocities, the scaled effector position, cos and sin of the effector yaw, the scaled gripper opening and gripper contact | upstream_code | ocbench/envs/manipulation_env.py:374-393 |
| BlockEnv appends every cube's three positions, four quaternion values, cos yaw and sin yaw to the observation | upstream_code | ocbench/envs/block_env.py:326-333 |
| The observation space is a Box from -inf to +inf with the observation shape | upstream_code | ocbench/envs/manipulation_env.py:95-105 |
| The reward is 1.0 when success is true, failure is false and the state is healthy; otherwise 0.0 | upstream_code | ocbench/envs/manipulation_env.py:395-396 |
| A cube is successful when its distance to the target mocap is at most 0.04 | upstream_code | ocbench/envs/block_env.py:244-255 |
| The episode terminates when terminate_at_success and success, or failure, or the state is not healthy | upstream_code | ocbench/envs/manipulation_env.py:409-410 |
| terminate_at_success defaults to True | upstream_code | ocbench/envs/manipulation_env.py:18 |
| CustomMuJoCoEnv.truncate_episode returns False, so the environment itself never truncates | upstream_code | ocbench/envs/env.py:118-123 |
| A reset calls Gymnasium's reset(seed=seed, options=options), initializes the episode and returns the observation and info | upstream_code | ocbench/envs/env.py:184-211 |

For the single-cube task the observation is 28 values, read from the two cited composition rules: 6 joint positions,
6 joint velocities, 3 scaled effector positions, cos and sin of the effector yaw (2), scaled gripper opening (1),
gripper contact (1), and the cube record (3 positions + 4 quaternion values + cos yaw + sin yaw = 9). This total is
derived from the code, not a separately declared constant.

Limits: the driver declares none of its own. The only bound is the action space, which the Gymnasium bridge derives
from the environment's `Box(-1, 1)` of shape (7) (`ocbench/envs/manipulation_env.py:107-114`) with no source and the
ref `action_space of the fake backend .fake:FakeBlockEnv`, plus the bridge's `ticks` bound (1 to 10000). The device is
simulated (R0), so no limit is `operator_required`; the operator overlay is not needed.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:block-cpu-single-task1-v0`, level F1 (MuJoCo
rigid-body dynamics with contacts, not validated), determinism `seeded` with `seed_control` `parameter`, timestep
20 ms (the 0.02 s control step of `ocbench/envs/manipulation_env.py:17`, applied as ten 0.002 s physics steps by
`ocbench/envs/env.py:271-288`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps
say what the package's fake does not model and that it was never compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the last
world state stays readable.

Tags: ocbench, mujoco, manipulation, block, reinforcement-learning, simulation, gymnasium

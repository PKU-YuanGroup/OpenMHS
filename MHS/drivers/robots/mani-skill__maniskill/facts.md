# Facts and tags for gh.mani-skill/maniskill

Every fact cites its source at commit `62ff3a5896b4d5b4cf0ac4c8d79afe600c9404a3`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or
`upstream_code` (`path/in/clone.py:LINE`). The same facts are in `facts = [Fact(text, source=..., ref=...)]` in
`driver.py`; `reference.json` and `REFERENCE.md` are generated from the driver, not from this page.

Tags: `mani-skill`, `trifinger`, `rotate-cube`, `reinforcement-learning`, `simulation`, `gymnasium`.

| fact | source | ref |
|---|---|---|
| TriFingerRotateCubeLevel0-v1 is registered with max_episode_steps=250 | upstream_code | `mani_skill/envs/tasks/rotate_cube.py:351` |
| The task's default robot is "trifingerpro" | upstream_code | `mani_skill/envs/tasks/rotate_cube.py:57` |
| TriFingerPro's active joint list names the nine finger joints: base-to-upper, upper-to-middle and middle-to-lower for each of the 0, 120 and 240 degree fingers | upstream_code | `mani_skill/agents/robots/trifingerpro/trifingerpro.py:42-56` |
| The controller configs list pd_joint_delta_pos first | upstream_code | `mani_skill/agents/robots/trifingerpro/trifingerpro.py:144-145` |
| A control_mode of None selects the first supported control mode | upstream_code | `mani_skill/agents/base_agent.py:106-109` |
| The pd_joint_delta_pos controller bounds each joint delta to -0.1 to 0.1 and applies it as a delta | upstream_code | `mani_skill/agents/robots/trifingerpro/trifingerpro.py:103-110` |
| PDJointPosControllerConfig normalises the action space by default | upstream_code | `mani_skill/agents/controllers/pd_joint_pos.py:131` |
| A normalised action space is Box(-1, 1) with the shape of the controller's joint action space | upstream_code | `mani_skill/utils/gym_utils.py:110-112` |
| The environment's action space is the agent controller's action space and the single action space is its unbatched form | upstream_code | `mani_skill/agents/base_agent.py:298-320` |
| The task's size parameter is 0.065 m and its goal_radius is 0.02 m | upstream_code | `mani_skill/envs/tasks/rotate_cube.py:39-44` |
| Success requires the object-to-goal position distance below 0.02 m and the quaternion difference below 0.1 rad | upstream_code | `mani_skill/envs/tasks/rotate_cube.py:224-230` |
| The dense reward is clamped to -15 to 15 and set to 15 on success | upstream_code | `mani_skill/envs/tasks/rotate_cube.py:340-341` |
| The normalised dense reward is dense/(2*15)+0.5, so it lies in 0 to 1 | upstream_code | `mani_skill/envs/tasks/rotate_cube.py:344-347` |
| The supported reward modes are normalized_dense, dense, sparse and none, in that order | upstream_code | `mani_skill/envs/sapien_env.py:128` |
| A reward_mode of None selects the first supported reward mode | upstream_code | `mani_skill/envs/sapien_env.py:298-300` |
| The simulation runs at sim_freq 100 Hz and control_freq 20 Hz; every control step contains sim_freq/control_freq simulation steps | upstream_code | `mani_skill/utils/structs/types.py:83-86` |
| The control timestep is 1/control_freq and the simulation timestep is 1/sim_freq | upstream_code | `mani_skill/envs/sapien_env.py:474-482` |
| The supported observation modes start with state | upstream_code | `mani_skill/envs/sapien_env.py:124` |
| An obs_mode of None selects the first supported observation mode | upstream_code | `mani_skill/envs/sapien_env.py:284-286` |
| A state observation is the agent's proprioception plus the task's extra observations | upstream_code | `mani_skill/envs/sapien_env.py:547-552` |
| The default proprioception is the robot's qpos and qvel, plus a controller state when it is non-empty | upstream_code | `mani_skill/agents/base_agent.py:339-347` |
| The RotateCube task adds goal_pos, goal_q, obj_p and obj_q to the extra observation | upstream_code | `mani_skill/envs/tasks/rotate_cube.py:253-263` |
| A state observation is flattened with flatten_state_dict before it is returned | upstream_code | `mani_skill/envs/sapien_env.py:536-539` |

## What is served and what is not

The driver is `TriFingerRotateCube(GymnasiumDriver)` with `env_id = "TriFingerRotateCubeLevel0-v1"` and
`native = "mani_skill.envs.tasks.rotate_cube:RotateCubeEnvLevel0"`. The action space derived for the default
controller is `Box(-1, 1, shape=(9,))`; a step takes `{ticks, action: {values: [9 numbers]}}`, a reset takes
`{seed, options}` and the seed capability sets the seed of the next reset.

Only the fake backend is available in this package: `fake.py` is a pure-Python kinematic stand-in (fidelity F0) with
the upstream class's `reset`, `step` and `close` surface. It moves the nine joints by the scaled action deltas and the
cube by a placeholder drift, computes the success test and the normalised reward from the cited thresholds, and
truncates at 250 steps. The 32-value flat observation has the layout of the default state observation (9 qpos, 9 qvel,
3 goal_pos, 4 goal_q, 3 obj_p, 4 obj_q), but every value is produced by the stand-in.

Not covered: rigid-body dynamics, contacts, friction, actuators, constraints, rendering, cameras, sensor data and the
visual observation modes; the upstream `sim` path (`gymnasium.make(env_id)`, which needs SAPIEN/PhysX and the upstream
package) was not run. Snapshot and restore are not offered because the env exposes no `get_state`/`set_state` pair.
The fake has never been compared with a run of the upstream environment, and this package claims no such comparison.

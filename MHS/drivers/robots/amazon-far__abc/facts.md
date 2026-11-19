# Facts and tags for gh.amazon-far/abc

Every fact cites its source at commit `d0832d12651d1b260a652861a14648dc5f3660c7`: `upstream_code` is a code or
comment line of the clone, `vendor_doc` is documentation text of the clone. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| MuJoCoYAMEnv is a Gymnasium environment (gym.Env) for a bimanual YAM robot whose actions and observations use the 14D policy-space order [left_j1..6, left_gripper, right_j1..6, right_gripper] | upstream_code | abc_sim/env.py:72-77 |
| The per-step action space is a Box over 14 elements with low -1.0 and high 1.0 | upstream_code | abc_sim/env.py:124-179 |
| single_timestep_action_dim is 7 times the number of configured robots, 14 in the base configuration | upstream_code | abc_sim/env.py:124-126 |
| The observation is a Dict with per-camera (3, camera_height, camera_width) uint8 images, a 14-element float32 state, per-camera Discrete(2) masks, a prompt Text and per-camera float64 timestamps | upstream_code | abc_sim/env.py:124-173 |
| project_policy_state maps MuJoCo qpos into the 14D policy state and clips each gripper element to qpos/_GRIPPER_CTRL_MAX in [0, 1] | upstream_code | abc_sim/env.py:31-47 |
| The base configuration defines three cameras (top, left, right) and two robots (left, right), each robot with seven init_q values | upstream_code | abc_sim/config.py:69-123 |
| get_i2rt_sim_config builds the base configuration, marks every follower as simulation and may override each robot's init_q from the DEPLOY_INIT_Q environment variable | upstream_code | abc_sim/config.py:133-145 |
| reset calls mj_resetData and then restores the arm pose returned by _get_reset_arm_state | upstream_code | abc_sim/env.py:304-315 |
| reset passes options['randomization'] to the task randomizer and may adopt a prompt from the randomization metadata | upstream_code | abc_sim/env.py:319-336 |
| reset puts the native randomization outcome into info['randomization'] when it exists | upstream_code | abc_sim/env.py:374-378 |
| RandomizationState.to_dict returns seed, object_states, scale_states and metadata | upstream_code | abc_sim/randomization/core.py:65-72 |
| _get_reset_arm_state returns the current 14D arm pose when the arm state is initialized and otherwise the concatenated init_q; forget_arm_state clears the initialized flag | upstream_code | abc_sim/env.py:498-510 |
| step applies one 14D action and returns the Gymnasium 5-tuple; step_chunk stops at the first terminated or truncated step | upstream_code | abc_sim/env.py:380-417 |
| _step_single writes the 14D action into the actuator controls and advance_physics runs control_decimation mj_step calls | upstream_code | abc_sim/env.py:512-533 |
| The default physics_dt is 0.002 s and control_decimation is 17, about 0.034 s per control transition | upstream_code | abc_sim/env.py:89-90 |
| terminated is true only when terminate_on_success is set and the task evaluator reports success; truncated is true when cur_step reaches max_episode_steps and the episode is not terminated | upstream_code | abc_sim/env.py:461-468 |
| The reward is the task evaluator's scalar reward, or 0.0 when no evaluator is attached | upstream_code | abc_sim/env.py:451-453 |
| make_env is the public task-to-environment factory; its default task is 'bottles' and it returns MuJoCoYAMEnv | upstream_code | abc_sim/__init__.py:125-140 |
| get_obs returns images, masks, state, prompt and camera_timestamps; the masks are all True and the timestamps are the simulation time | upstream_code | abc_sim/env.py:594-618 |
| close closes the camera backend | upstream_code | abc_sim/env.py:485-486 |
| capture_state returns copies of qpos, qvel and the simulated time | upstream_code | abc_sim/env.py:476-483 |
| The runtime dependencies include mujoco~=3.8.0 and gymnasium>=1.1 | upstream_code | pyproject.toml:11-21 |
| The README documents the stable API: reset(seed, randomize), step(action_14d), step_chunk(action_chunk), action_space shape (14,) and the observation keys | vendor_doc | abc_sim/README.md:86-106 |

## Limits

The driver declares no `Limit`. The only bound on a step is the action space the bridge derives from the environment:
`action.values` per element from -1.0 to 1.0, with source `upstream_code` and the ref `abc_sim/env.py:175-179` that
defines the space (`action_space_ref`). `ticks` is the bridge's own 1 to 10000 bound (`max_ticks`), not a device fact.
The device is simulated (R0), so no bound is `operator_required` and there is no `site-limits.example.json`.

The fake copies the upstream action space, so the derived bound is a real upstream bound; the fake's initial state,
image pixels, image size 3x4x4 and prompt are placeholders, not facts, and are not used in any Fact or Limit.

## Fidelity contract

`driver.py` declares the deployed fake as level F0 (`analytic:abc_sim fake kinematic stand-in`, timestep 34 ms,
determinism `seeded` with `seed_control` parameter, `realtime_factor` 0, `clock` lockstep, reset `partial`, no
snapshot/restore). The gaps state that it has no rigid-body dynamics, contacts, actuators, evaluator or randomizer;
that its 14D state is the last commanded action and does not clip and normalize the gripper like
`project_policy_state` (`abc_sim/env.py:31-47`); that it ignores reset options and its seed has no random draw
(`abc_sim/env.py:319-336`); that its images are 3x4x4 placeholders while the upstream default is 3x480x640 per camera
(`abc_sim/env.py:87-88`); that reset preserves the arm pose unless `forget_arm_state()` is called; that there is no
wall-clock pacing and no `set_state()`; and that it was never compared with the upstream environment.

Both backends pass through `sim.py`'s `ResetInfoAdapter`. It uses the upstream
`RandomizationState.to_dict()` method (`abc_sim/randomization/core.py:65-72`) to retain reset randomization
metadata as JSON. Unconverted, the Gymnasium bridge drops the resource's info when it cannot serialize that
object. The fake supplies a placeholder object with that interface, without sampling or randomizing a scene.
Its image dimensions follow the constructor options, and its chunk method accepts the upstream two-dimensional
action layout as well as the equivalent flat layout.

The declared `backends["sim"]` factory wraps upstream `abc_sim.make_env`, whose fidelity is declared per backend as
F1 `mujoco:abc_sim` (rigid-body MuJoCo, contacts and actuators). That route needs the upstream dependencies and the
downloaded simulator assets (`pyproject.toml:10-21`, `abc_sim/README.md:181-185`) and was not run here.

## Safety

Simulated R0 device. There is no hardware backend and no physical device. The e-stop is the runtime's software latch:
after it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the last observation stays
readable. No `estop_physical_ref` and no `@action(safe_state=True)` are declared because there is no physical hazard.

## Tags

abc, yam, bimanual, mujoco, reinforcement-learning, simulation, gymnasium

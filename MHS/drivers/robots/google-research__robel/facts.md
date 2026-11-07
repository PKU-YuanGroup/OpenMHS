# Facts and tags for gh.google-research/robel

Every fact cites its source at commit `5b0fd3704629931712c6e0f7268ace1c2154dc83`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| DClawPoseFixed-v0 is registered with the entry point robel.dclaw.pose:DClawPoseFixed and max_episode_steps 80 | upstream_code | robel/dclaw/__init__.py:23-29 |
| The DCLAW3_ASSET_PATH constant of a pose task is robel-scenes/dclaw/dclaw3xh.xml | upstream_code | robel/dclaw/pose.py:46 |
| The pose episode counts 80 steps of 20 simulation steps at 2.5 ms each (4 s) | upstream_code | robel/dclaw/__init__.py:24 |
| An environment step skips 20 simulation steps by default | upstream_code | robel/dclaw/pose.py:52-56 |
| The DClaw group covers nine joints with position ranges -0.48 to 0.48 rad, -PI/3 to PI/3 rad and -PI/2 to PI/2 rad repeated three times, and a velocity range -2*PI/3 to 2*PI/3 rad/s | upstream_code | robel/dclaw/base_env.py:98-106 |
| The normalized action space is a Box from -1.0 to 1.0 with one element per joint position | upstream_code | robel/dclaw/base_env.py:118-121 |
| An action is clipped to -1.0 to 1.0 before it is applied | upstream_code | robel/robot_env.py:476-486 |
| The denormalization center is the mean of the actuator range and its range is half the span of that range | upstream_code | robel/components/robot/group_config.py:160-166 |
| A normalized action is clipped to -1.0 to 1.0 and denormalized with the actuator center and range | upstream_code | robel/components/robot/robot.py:218-228 |
| A joint-position command is clipped to the qpos range and then its velocity is clipped to the qvel range | upstream_code | robel/components/robot/robot.py:242-261 |
| The default observation keys are qpos, last_action and qpos_error | upstream_code | robel/dclaw/pose.py:33-38 |
| get_obs_dict returns qpos, qvel, last_action and qpos_error, where qpos_error is the desired pose minus the current qpos | upstream_code | robel/dclaw/pose.py:98-105 |
| The flat observation is the concatenation of the selected observation arrays | upstream_code | robel/robot_env.py:511-517 |
| The observation space is a Box from -inf to +inf with the observation shape | upstream_code | robel/robot_env.py:425-438 |
| A reset sets last_action to None | upstream_code | robel/robot_env.py:216 |
| When no action has been taken, the last-action observation is a zero array | upstream_code | robel/robot_env.py:470-474 |
| DClawPoseFixed resets to a random initial pose and a random desired pose | upstream_code | robel/dclaw/pose.py:168-172 |
| A random pose clamps the upper bound of the middle joints at indices 1, 4 and 7 to 0 | upstream_code | robel/dclaw/pose.py:148-156 |
| The pose reward is the negative norm of qpos_error minus 0.1 times the norm of the qvel entries whose absolute value is at least pi | upstream_code | robel/dclaw/pose.py:112-126 |
| The default get_done returns an all-false array, so the pose environment does not terminate by itself | upstream_code | robel/robot_env.py:395-412 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the
environment (`Box(-1.0, 1.0)` over nine elements, with the source `upstream_code` and the ref
`robel/dclaw/base_env.py:121`), and `ticks` (1 to `max_ticks`, 10000 by default). The device is simulated (R0),
so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:dclaw3xh`, level F1 (MuJoCo
rigid-body dynamics with contacts, no validation against hardware), determinism `seeded` with `seed_control`
`parameter`, timestep 50 ms (0.0025 s model timestep times the default frame_skip 20), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore. The gaps say what the kinematic fake does not model (contacts,
actuator forces, the upstream numpy random stream, the registered 80-step TimeLimit, rendering and safety scores)
and that nothing was validated against hardware.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step
or reset is accepted until `mhs.safety.reset` clears the latch, and the last world state stays readable.

Tags: dclaw, pose, manipulation, mujoco, reinforcement-learning, simulation, gymnasium

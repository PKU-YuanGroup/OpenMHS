# Facts and tags for gh.soltanilara/gym_av_aloha

Every fact cites its source in the clone at commit `3e8edfdf5e2ff9cfc6e330ab9f970417e0e2a77d`, either
`upstream_code` (`path/in/clone.py:LINE`) or `vendor_doc` (a text file of the clone; a PDF would be cited
`docs/manual.pdf:PAGE`). The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| cube-transfer-v1 is registered with entry point gym_av_aloha.env.tasks.cube_transfer_env:CubeTransferEnv | upstream_code | gym_av_aloha/__init__.py:19-21 |
| The registration marks cube-transfer-v1 nondeterministic=True because rendered observations differ even after seeding | upstream_code | gym_av_aloha/__init__.py:22-24 |
| The default camera set has six cameras, each rendered at 480x640 pixels | upstream_code | gym_av_aloha/env/sim_config.py:7-14 |
| AVAlohaEnv adds a pixels observation only when len(cameras) > 0 | upstream_code | gym_av_aloha/env/sim_env.py:151-163 |
| AV_STATE_DIM is 21 and AV_ACTION_DIM is 21; STATE_DIM and ACTION_DIM are 14 | upstream_code | gym_av_aloha/env/sim_config.py:25-28 |
| With enable_av=True the action space is a Box with low -inf, high inf and shape (action_dim,) | upstream_code | gym_av_aloha/env/sim_env.py:167-172 |
| The agent_pos observation is a Box with low -inf, high inf and shape (state_dim,), and the observation space is a Dict | upstream_code | gym_av_aloha/env/sim_env.py:144-165 |
| With enable_av=True get_obs builds agent_pos from the left joint positions, left gripper, right joint positions, right gripper and middle joint positions | upstream_code | gym_av_aloha/env/sim_env.py:179-197 |
| CubeTransferEnv adds an environment_state Box with shape (ENV_STATE_DIM,) to the observation and rebuilds the observation space as a Dict | upstream_code | gym_av_aloha/env/tasks/cube_transfer_env.py:39-45 |
| ENV_STATE_DIM is 7 | upstream_code | gym_av_aloha/env/tasks/cube_transfer_env.py:15 |
| CubeTransferEnv.get_obs sets environment_state to the bound cube joint qpos, a 7-value pose | upstream_code | gym_av_aloha/env/tasks/cube_transfer_env.py:47-50 |
| CubeTransferEnv sets max_reward to 4 | upstream_code | gym_av_aloha/env/tasks/cube_transfer_env.py:25 |
| CubeTransferEnv.get_reward returns a reward from 0 to 4 from cube, gripper and table contacts | upstream_code | gym_av_aloha/env/tasks/cube_transfer_env.py:57-92 |
| reset(seed, options) passes seed and options to gym.Env.reset, resets the physics, optionally randomizes the light and prompt, restores the fixed arm poses and returns observation and info | upstream_code | gym_av_aloha/env/sim_env.py:307-344 |
| CubeTransferEnv.reset draws the cube position uniformly from x [-0.05, 0.05], y [0.05, 0.15], z 0 with the global np.random generator | upstream_code | gym_av_aloha/env/tasks/cube_transfer_env.py:94-105 |
| step applies the action as control over n_ctrl_steps, each advancing SIM_PHYSICS_ENV_STEP_RATIO physics steps, and returns observation, reward, terminated, truncated and info | upstream_code | gym_av_aloha/env/sim_env.py:269-288 |
| terminated is reward == max_reward and info is_success is the same comparison | upstream_code | gym_av_aloha/env/sim_env.py:282-286 |
| SIM_PHYSICS_DT is 0.002 s and SIM_DT is 0.04 s from 20 physics steps | upstream_code | gym_av_aloha/env/sim_config.py:19-22 |
| The default fps is 25 | upstream_code | gym_av_aloha/env/sim_env.py:38 |
| step_dt is 1/fps and n_ctrl_steps is round(step_dt/SIM_DT) | upstream_code | gym_av_aloha/env/sim_env.py:66-67 |
| SimRobotArm.set_joint_ctrl clips joint control to the actuator ctrlrange | upstream_code | gym_av_aloha/env/robot.py:91-94 |
| The environment's render_fps is 1/SIM_DT and its only render mode is rgb_array | upstream_code | gym_av_aloha/env/sim_env.py:27 |
| The upstream package requires Python ^3.10 and mujoco 3.3.3, dm-control ^1.0.31 and datasets 3.3.2 | upstream_code | pyproject.toml:9-12 |

Limits: the driver declares none. The only action bound is the environment's own `action_space`, an unbounded
`Box(-inf, inf, (21,))` (`sim_env.py:167-172`), so the bridge derives no finite action limits. The class bound on
`cap.world.step.v1`'s `ticks` (1 to 10000) is the catalogue class's own count and is not a device fact. The device is
simulated (R0), so there is no operator-required bound and no site-limits overlay.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco`, level F1 (rigid-body dynamics with contacts),
determinism `seeded` with `seed_control` `parameter`, timestep 40 ms (`SIM_DT = 0.04` s, `sim_config.py:19-22`),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled:
the fake is kinematic, the six 480x640 camera frames are NOT COVERED (the driver configures `cameras={}`), the fake
returns reward 0 and never terminates, action clipping and reset options are not modelled, and the fake was not
compared with a real MuJoCo run.

Safety: simulated R0 device with no hardware backend. The e-stop is the runtime's software latch; after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable. No physical e-stop is
claimed and no hardware run was made.

Tags: aloha, bimanual, mujoco, simulation, reinforcement-learning, gymnasium

# Facts and tags for gh.lachlanhurst/so100-mujoco-rl

Every fact cites its source at commit `057ccecbb5c2bb06aa526714f300e801c19d3cf7`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Env01 is registered as Env01-v1 with max_episode_steps=4000 and reward_threshold=6000 | upstream_code | src/so100_mujoco_rl/__init__.py:5-10 |
| Env01 extends So100BaseEnv | upstream_code | src/so100_mujoco_rl/envs/env01_v1.py:10 |
| So100BaseEnv extends MujocoEnv and gymnasium.utils.EzPickle | upstream_code | src/so100_mujoco_rl/envs/env_base_01.py:25 |
| The action space is a Box of six floats, each from -1.0 to 1.0 | upstream_code | src/so100_mujoco_rl/envs/env_base_01.py:77-83 |
| One action component scales the joint motion by JOINT_STEP_SCALE = 0.075 | upstream_code | src/so100_mujoco_rl/envs/utils.py:9 |
| A step adds the scaled action to each joint angle, writes the result to the position actuator ctrl and integrates the MuJoCo model frame_skip times | upstream_code | src/so100_mujoco_rl/envs/env01_v1.py:15-27 |
| MujocoEnv is constructed with frame_skip=16 | upstream_code | src/so100_mujoco_rl/envs/env_base_01.py:42-51 |
| The observation is fifteen numbers: six joint angles, the block-to-end-effector deltas dx, dy and dz, the block position and the end-effector position | upstream_code | src/so100_mujoco_rl/envs/env_base_01.py:241-270 |
| The observation space bounds the six joints by the model ranges and the remaining nine values by -1 to 1 and -0.5 to 0.5 | upstream_code | src/so100_mujoco_rl/envs/env_base_01.py:63-75 |
| The joint ranges are Rotation -2.2 to 2.2, Pitch -3.14158 to 0.2, Elbow 0 to 3.14158, Wrist_Pitch -2.0 to 1.8, Wrist_Roll -3.14158 to 3.14158 and Jaw -0.2 to 2.0 radians | upstream_code | src/so100_mujoco_rl/envs/model/so_arm100_camera.xml:33-50 |
| The position actuators use kp=50, dampratio=1 and a force range of -35 to 35 | upstream_code | src/so100_mujoco_rl/envs/model/so_arm100_camera.xml:31-33 |
| Reset draws the block at a distance of 0.18 to 0.42 m from the base and within 0.25*pi of -0.5*pi in angle | upstream_code | src/so100_mujoco_rl/envs/env01_v1.py:45-47 |
| Reset chooses one of 36 start poses from VALID_START_POSITIONS (six joint angles each) | upstream_code | src/so100_mujoco_rl/envs/utils.py:13-50 |
| Reset draws from numpy's global generator (np.random.uniform and np.random.randint), not from the environment's seeded np_random | upstream_code | src/so100_mujoco_rl/envs/env01_v1.py:45-55 |
| Env01.step always reports terminated=False; the 4000-step TimeLimit wrapper is the only truncation | upstream_code | src/so100_mujoco_rl/envs/env01_v1.py:29-37 |
| The reward combines a block-to-end-effector distance term, joint-range penalties and previous-step positions | upstream_code | src/so100_mujoco_rl/envs/env_base_01.py:180-239 |
| The scene attaches the so_arm100 model and adds a free-joint block_a and a floor | upstream_code | src/so100_mujoco_rl/envs/model/env01.xml:24-40 |
| Contacts between block_a and every arm body are excluded, so the arm never pushes the block | upstream_code | src/so100_mujoco_rl/envs/model/env01.xml:42-49 |
| The scene does not set a MuJoCo timestep: its option timestep line is commented out | upstream_code | src/so100_mujoco_rl/envs/model/env01.xml:3 |

Limits: the driver declares none. The only bounds are the environment's own: the action space gives `action.values`
a per-element limit of -1 to 1 (no source, ref `action_space of the fake backend .fake:FakeEnv01`, derived by the
Gymnasium bridge from `env_base_01.py:77-83`) and the bridge bounds `ticks` to 1..10000. The device is simulated (R0),
so no limit is `operator_required` and there is nothing for a site-limits overlay to narrow.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:Env01-v1`, level F1 (MuJoCo rigid-body model
with contacts and position actuators, no validation), determinism `statistical` because the upstream reset draws from
numpy's global generator (`env01_v1.py:45-55`) rather than from `reset(seed=...)`, timestep 32 ms (16 integration steps
at `env_base_01.py:45` times the MuJoCo default 0.002 s, since `env01.xml:3` leaves the option commented out),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what the fake does not model
and that the fake was not compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: so100, so-arm100, mujoco, gymnasium, reinforcement-learning, robot-arm, simulation

# Facts and tags for gh.unrealzoo/unrealzoo-gym

Every fact cites its source at commit `85f4b72e0ecd3c77f17fab161c3c8bdfdd86cf7c` (`upstream_code` unless stated).
The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from
this page.

| fact | source | ref |
|---|---|---|
| The Go1 entry of ROBOT_SPECS declares an observation dimension of 48 and an action dimension of 12 | upstream_code | gym_unrealcv/envs/mujoco.py:13-14 |
| The action space is a Box with low -1.0 and high 1.0 for every element, shape (action_dim,) and dtype float32 | upstream_code | gym_unrealcv/envs/mujoco.py:129-134 |
| The observation space is a Box with low -inf and high inf, shape (observation_dim,) and dtype float32 | upstream_code | gym_unrealcv/envs/mujoco.py:135-140 |
| A step sends the action to the UnrealCV server and returns (observation, 0.0, False, info): the reward is always 0.0 and the environment signals neither termination nor truncation | upstream_code | gym_unrealcv/envs/mujoco.py:388-393 |
| A reset sets steps to 0, clears last_action, rebuilds the robot state and returns the first observation | upstream_code | gym_unrealcv/envs/mujoco.py:334-339 |
| UnrealCvMujocoEnv.reset takes no seed and no options parameter | upstream_code | gym_unrealcv/envs/mujoco.py:314 |
| UnrealMujoco-Go1-v0 registers the entry point gym_unrealcv.envs:UnrealCvMujocoEnv with the robot keyword go1 | upstream_code | gym_unrealcv/__init__.py:10-19 |
| The Go1 MuJoCo defaults are timestep 0.005 s and control_decimation 4 | upstream_code | gym_unrealcv/envs/base_env_mujoco.py:15-18 |
| The control period is the physics timestep multiplied by control_decimation | upstream_code | gym_unrealcv/envs/base_env_mujoco.py:142-145 |
| The environment connects an unrealcv.Client to (host, port); it does not open a hardware device | upstream_code | gym_unrealcv/envs/base_env_mujoco.py:230-231 |
| The package dependencies pin gym 0.10.9 and unrealcv 1.3.2 | upstream_code | pyproject.toml:10-15 |

Limits: the driver declares none of its own. The only bound is the action space, which the bridge derives from the
environment (`Box(low=-1.0, high=1.0)` per element of the 12-element Go1 action, source `upstream_code`, ref
`gym_unrealcv/envs/mujoco.py:129-134`), and `ticks` (1 to `max_ticks`, 10000 by default). The device is simulated (R0),
so no limit is `operator_required` and no operator overlay is supplied.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `unrealzoo-gym:UnrealMujoco-Go1-v0`, level F0
(kinematic/analytic, no dynamics), determinism `seeded` with `seed_control` `parameter` (the seed reseeds the fake;
`UnrealCvMujocoEnv.reset` itself takes no seed, `gym_unrealcv/envs/mujoco.py:314`), timestep 20 ms
(`0.005 s * 4`, `gym_unrealcv/envs/base_env_mujoco.py:15-18` and `:142-145`), `realtime_factor` 0, clock `lockstep`,
reset `full`, no snapshot and restore. The gaps say that the 48-element observation layout, rigid-body dynamics, task
logic, the UnrealCV server and the Unreal Engine process are not modelled, and that the fake was never compared with
the upstream environment.

Safety: simulated R0 device. There is no hardware backend and no native stop; the e-stop is the runtime's software
latch. After it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the last observation stays
readable. No protection beyond that runtime latch is claimed.

Tags: unrealzoo, unrealcv, mujoco, go1, robot, reinforcement-learning, simulation, gymnasium

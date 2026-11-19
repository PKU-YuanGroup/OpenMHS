# Facts and tags for gh.learnsyslab/crazyflow

Every fact cites its source at commit `70d09e455859580c45b0e4a06ee4a92efbbc2d6f`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page. No limit is
declared in the driver: the only bound is the environment's action space, which the Gymnasium bridge derives from
the served action space (`action.values`), and `ticks` (1 to `max_ticks`, 10000 by default). The device is simulated
(R0), so no limit is `operator_required`.

| fact | source | ref |
|---|---|---|
| DroneReachPos-v0 is registered with vector_entry_point=ReachPosEnv | upstream_code | crazyflow/envs/__init__.py:11 |
| The DroneReachPos-v0 registration names vector_entry_point and does not name an entry_point | upstream_code | crazyflow/envs/__init__.py:11 |
| The user guide builds a registered Crazyflow environment with gymnasium.make_vec | vendor_doc | docs/user-guide/gymnasium-envs.md:21-23 |
| ReachPosEnv defaults to one world, max_episode_time 10.0, Dynamics.so_rpy, frequency 500 and device cpu | upstream_code | crazyflow/envs/reach_pos_env.py:20-31 |
| Importing crazyflow raises when scipy is already imported and SCIPY_ARRAY_API is not "1", then sets SCIPY_ARRAY_API to "1" before importing scipy | upstream_code | crazyflow/__init__.py:10-17 |
| DroneEnv is a gymnasium.vector.VectorEnv and declares autoreset_mode NEXT_STEP | upstream_code | crazyflow/envs/drone_env.py:48-60 |
| The number of worlds defaults to 1 | upstream_code | crazyflow/envs/reach_pos_env.py:26 |
| The action space is batched over the number of worlds | upstream_code | crazyflow/envs/drone_env.py:110-111 |
| The fitted so_rpy command interface is [roll_rad, pitch_rad, yaw_rad, thrust_N] | upstream_code | crazyflow/dynamics/so_rpy/dynamics.py:8 |
| With attitude control the action space is a Box whose roll, pitch and yaw bounds are +-pi/2 and whose collective thrust bounds are 4*thrust_min and 4*thrust_max | upstream_code | crazyflow/envs/drone_env.py:35-41 |
| The default drone of DroneEnv is cf2x_L250 | upstream_code | crazyflow/envs/drone_env.py:68 |
| For cf2x_L250 the per-motor thrust bounds are 0.012817578393224994 N and 0.12 N | upstream_code | crazyflow/dynamics/so_rpy/params.toml:28-29 |
| The cf2x_L250 mass is 0.0328 kg, acc_coef is 0.0 and cmd_f_coef is 1.023224599403443 | upstream_code | crazyflow/dynamics/so_rpy/params.toml:22-31 |
| The gravity vector is [0, 0, -9.81] m/s^2 | upstream_code | crazyflow/dynamics/params.toml:3 |
| The observation space is a Dict of pos (3), quat (4), vel (3) and ang_vel (3), batched by world | upstream_code | crazyflow/envs/drone_env.py:112-120 |
| ReachPosEnv adds difference_to_goal (3) to the observation Dict | upstream_code | crazyflow/envs/reach_pos_env.py:48-51 |
| DroneEnv.reset(seed) seeds the simulation, resets it and returns the observation and an empty info | upstream_code | crazyflow/envs/drone_env.py:157-165 |
| ReachPosEnv samples the goal before resetting the simulation; the options goal_pos_min and goal_pos_max override the goal bounds | upstream_code | crazyflow/envs/reach_pos_env.py:54-60 |
| The default goal box is [-1, -1, 0.5] to [1, 1, 1.5] | upstream_code | crazyflow/envs/reach_pos_env.py:94-96 |
| The reset position box defaults to [-1, -1, 1] to [1, 1, 2] and the velocity box to -1 to 1 m/s | upstream_code | crazyflow/envs/reach_pos_env.py:24-35 |
| The reset randomization draws positions and velocities uniformly from those boxes | upstream_code | crazyflow/envs/reach_pos_env.py:108-109 |
| DroneEnv.step applies the action, advances the simulation by n_substeps, resets the worlds marked done and returns observation, reward, terminated, truncated and an empty info | upstream_code | crazyflow/envs/drone_env.py:122-129 |
| The episode terminates when the drone z position is below zero | upstream_code | crazyflow/envs/drone_env.py:190-191 |
| The episode truncates when the simulation time reaches max_episode_time | upstream_code | crazyflow/envs/drone_env.py:195-196 |
| max_episode_time defaults to 10.0 s | upstream_code | crazyflow/envs/drone_env.py:66 |
| The ReachPos reward is exp(-2 * distance) and -1 when the episode terminated | upstream_code | crazyflow/envs/reach_pos_env.py:83-87 |
| The environment frequency defaults to 500 Hz | upstream_code | crazyflow/envs/drone_env.py:69 |
| The simulation frequency defaults to 500 Hz | upstream_code | crazyflow/sim/sim.py:87 |
| n_substeps is sim.freq // freq | upstream_code | crazyflow/envs/drone_env.py:106 |
| The MuJoCo timestep is 1 / freq | upstream_code | crazyflow/sim/sim.py:293 |
| The attitude action is clipped to the action space bounds before it is applied | upstream_code | crazyflow/envs/drone_env.py:132-150 |
| The default simulation state has an identity quaternion [0, 0, 0, 1] and zero position, velocity and angular velocity | upstream_code | crazyflow/sim/data.py:44-52 |
| seed sets the JAX rng key of the simulation | upstream_code | crazyflow/sim/sim.py:276-282 |

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `crazyflow:DroneReachPos-v0`, level F0 (a single-world
kinematic stand-in, not the batched JAX/MuJoCo simulator), determinism `seeded` with `seed_control` `parameter`,
timestep 2 ms (500 Hz, `crazyflow/envs/drone_env.py:69`), `realtime_factor` 0, clock `lockstep`, reset `full`, no
snapshot and restore. The gaps say what the fake does not model, that the fake was not compared with a JAX/MuJoCo run
or any device, and that the sim backend serves the real `ReachPosEnv` (one world, device cpu) while these gaps
describe the fake stand-in.

Configuration: `env_id = "DroneReachPos-v0"`, `env_module = "crazyflow.envs"` (importing the module runs
`register(id="DroneReachPos-v0", vector_entry_point=ReachPosEnv)` at `crazyflow/envs/__init__.py:11`), and no
`env_kwargs` (the constructor defaults are the served environment: one world, `max_episode_time` 10.0,
`Dynamics.so_rpy`, frequency 500, device `cpu`, `crazyflow/envs/reach_pos_env.py:20-31`). The `fake` backend is
`.fake:FakeReachPosEnv`. The `sim` backend is the callable `_build_sim_reach_pos`. It imports `crazyflow`, as the
integration test does (`tests/integration/test_envs.py:6`). That import runs `crazyflow/__init__.py:10-19`, which
sets `SCIPY_ARRAY_API` to `"1"` and imports `scipy` before the rest of the package, then imports `crazyflow.envs`,
which registers the id. The factory does not assign the variable. It constructs `ReachPosEnv()` and returns
`_OneWorldStep`. That wrapper turns the one world's reward, terminated and truncated arrays (`crazyflow/envs/drone_env.py:129`,
`crazyflow/envs/drone_env.py:191`) into Python scalars with `.item()` and forwards the observation. The registration
names no `entry_point` (`crazyflow/envs/__init__.py:11`), so `gymnasium.make` cannot build the id; the user guide
uses `gymnasium.make_vec` (`docs/user-guide/gymnasium-envs.md:21-23`).

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step,
reset or seed is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: crazyflow, drone, quadrotor, reach-position, reinforcement-learning, simulation, gymnasium, jax, mujoco

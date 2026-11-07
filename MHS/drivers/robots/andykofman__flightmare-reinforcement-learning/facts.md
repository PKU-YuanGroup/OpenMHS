# Facts and tags for gh.andykofman/flightmare-reinforcement-learning

Every fact cites its source at commit `22fb5d16eec32b1816aa568c20643d91ca7c76f7`: `vendor_doc` (a text file of the
clone) or `upstream_code` (`path/in/clone:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| FlightEnvVec is a Gymnasium-compatible wrapper around the C++ flightgym environments and their vectorized interface | upstream_code | flightrl_v2/flightrl_v2/envs/flight_env_vec.py:20-26 |
| FlightEnvVec reads num_envs from impl.getNumOfEnvs(), num_obs from getObsDim() and num_acts from getActDim() | upstream_code | flightrl_v2/flightrl_v2/envs/flight_env_vec.py:37-42 |
| The observation space is a Box with low=-inf, high=inf, shape=(num_obs,), dtype float32 | upstream_code | flightrl_v2/flightrl_v2/envs/flight_env_vec.py:46-51 |
| The action space is a Box normalized to [-1, 1] with one value per action dimension, dtype float32 | upstream_code | flightrl_v2/flightrl_v2/envs/flight_env_vec.py:53-58 |
| seed(seed) calls the base seed and, when the seed is not None, wrapper.setSeed(seed) | upstream_code | flightrl_v2/flightrl_v2/envs/flight_env_vec.py:77-81 |
| reset(seed, options) reseeds when a seed is given, clears the episode buffers, calls wrapper.reset(self._observation) and returns the first environment's observation and an empty info dict | upstream_code | flightrl_v2/flightrl_v2/envs/flight_env_vec.py:101-113 |
| step reshapes a one-dimensional action to (1, -1), calls wrapper.step with the observation, reward, done and extra-info buffers without checking its return value, and returns the first environment's observation, scalar reward, done[0] as terminated, a truncation flag and info | upstream_code | flightrl_v2/flightrl_v2/envs/flight_env_vec.py:131-186 |
| VecEnv::step logs an error and returns false without stepping when the action, observation, reward, done or extra-info dimensions do not match num_envs and the environment dimensions | upstream_code | flightlib/src/envs/vec_env.cpp:79-92 |
| The shipped vec_env.yaml sets num_envs: 100 and num_threads: 10 | upstream_code | flightlib/configs/vec_env.yaml:4-5 |
| make_flight_env_for_sb3 calls make_flight_env with num_envs=1 and num_threads=1 | upstream_code | flightrl_v2/flightrl_v2/envs/gymnasium_wrapper.py:174-183 |
| VecEnv::init reads render, seed, num_envs and scene_id, sets the OpenMP thread count with omp_set_num_threads and calls setUnity(render) | upstream_code | flightlib/src/envs/vec_env.cpp:31-48 |
| FlightEnvVecSB3 steps the whole backend with a zero action in every row other than env_index and returns that row | upstream_code | flightrl_v2/flightrl_v2/envs/flight_env_vec.py:318-337 |
| truncated is true when the first environment's episode length reaches max_episode_steps | upstream_code | flightrl_v2/flightrl_v2/envs/flight_env_vec.py:164 |
| close calls wrapper.close() when the wrapper exists | upstream_code | flightrl_v2/flightrl_v2/envs/flight_env_vec.py:193-196 |
| The pybind module binds VecEnv<QuadrotorEnv> as QuadrotorEnv_v1 with reset, step, setSeed, close, getNumOfEnvs, getObsDim, getActDim and getExtraInfoNames | upstream_code | flightlib/src/wrapper/pybind_wrapper.cpp:16-33 |
| The bound QuadrotorEnv reports kNObs=12 and kNAct=4 | upstream_code | flightlib/include/flightlib/envs/quadrotor_env/quadrotor_env.hpp:36-39 |
| getObs converts the attitude with toRotationMatrix().eulerAngles(2, 1, 0) and writes position, those three angles, linear velocity and angular velocity into the observation | upstream_code | flightlib/src/envs/quadrotor_env/quadrotor_env.cpp:119-128 |
| step sets the four thrust commands to the normalized action times act_std plus act_mean and runs the quadrotor for sim_dt | upstream_code | flightlib/src/envs/quadrotor_env/quadrotor_env.cpp:131-137 |
| act_mean is -mass * Gz / 4 and act_std is -mass * 2 * Gz / 4 in each of the kNAct entries | upstream_code | flightlib/src/envs/quadrotor_env/quadrotor_env.cpp:38-40 |
| QuadrotorEnv loads sim_dt from quadrotor_env.sim_dt | upstream_code | flightlib/src/envs/quadrotor_env/quadrotor_env.cpp:207-210 |
| The shipped quadrotor_env.yaml sets quadrotor_env sim_dt: 0.02 | upstream_code | flightlib/configs/quadrotor_env.yaml:1-3 |
| The episode terminates when the z position is at or below 0.05, with a terminal reward of -10 | upstream_code | flightlib/src/envs/quadrotor_env/quadrotor_env.cpp:198-202 |
| The reward combines weighted position, orientation, linear-velocity and angular-velocity errors and an action penalty, adds a 0.01 survival reward, and adds 1.0 when the position is within 0.1 of the goal and the speed is below 0.1 | upstream_code | flightlib/src/envs/quadrotor_env/quadrotor_env.cpp:159-195 |
| A random reset zeroes the state, sets x, y and the three velocities to uniform_dist_(random_gen_) draws, z to a draw plus 5 (mirrored when negative), the quaternion w to 1 and x, y and z to draws times 0.087, and normalizes the quaternion | upstream_code | flightlib/src/envs/quadrotor_env/quadrotor_env.cpp:83-105 |
| EnvBase::setSeed only calls std::srand(seed) | upstream_code | flightlib/include/flightlib/envs/env_base.hpp:39 |
| EnvBase's uniform_dist_ is uniform on [-1.0, 1.0] and random_gen_ is an std::mt19937 seeded from std::random_device | upstream_code | flightlib/include/flightlib/envs/env_base.hpp:60-62 |
| The vectorized per-agent step resets a terminal environment inside the same step and adds the terminal reward | upstream_code | flightlib/src/envs/vec_env.cpp:144-162 |
| The flightrl_v2 README requires the C++ physics engine flightgym to be built and installed | vendor_doc | flightrl_v2/README.md:84-91 |

Limits: the driver declares none. `cap.world.step.v1` action bounds come from the environment's action space: four
normalized values in [-1, 1], cited at `flightrl_v2/flightrl_v2/envs/flight_env_vec.py:53-58` through
`action_space_ref`. The `ticks` bound (1 to 10000) is the catalogue class's execution bound, not a device limit. The
device is simulated at R0, so no boundary is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic:Flightmare FlightEnvVec stand-in (no flightgym)`,
level F0, seeded with `seed_control` parameter, timestep 20 ms (`sim_dt: 0.02`, quadrotor_env.yaml:3),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot or restore. The gaps say that the fake is an analytic
stand-in with placeholder dynamics, that the real backend needs the flightgym C++ build
(flightrl_v2/README.md:84-91), and that the fake and the real environment were not compared.

Model review of 2026-11-04 (upstream behaviour a live backend would expose):
- Seeding does not reach the reset: `EnvBase::setSeed` only calls `std::srand` (env_base.hpp:39), while the random
  reset draws from an `std::mt19937` seeded from `std::random_device` (env_base.hpp:60-62, quadrotor_env.cpp:83-105).
  `cap.world.seed` and `reset(seed)` therefore cannot repeat a live start state; the fake's seeded repeat, which two
  package cases check, is fake behaviour.
- `FlightEnvVec.step` reshapes a single action to one row and ignores the false return of `VecEnv::step`, which
  refuses any dimension mismatch without stepping (flight_env_vec.py:131-186, vec_env.cpp:79-92). A backend built
  with `num_envs` other than 1 (the shipped vec_env.yaml says 100; `make_flight_env_for_sb3` forces 1) would never
  step and would keep returning the last observation.
- The three angles come from `eulerAngles(2, 1, 0)` (quadrotor_env.cpp:119-128): z, y, x order, with Eigen returning
  the first angle in [0, pi], so the triple can jump near zero yaw. The fake's angle triple is a placeholder.
- Live construction needs `FLIGHTMARE_PATH` and a built flightgym, sets the process-wide OpenMP thread count and, with
  render enabled, creates the Unity bridge singleton (vec_env.cpp:31-48). The repository's ArduPilot deployment
  classes are `NotImplementedError` placeholders; nothing at the pin commands a vehicle.

Safety: simulated R0 device. The e-stop is the runtime's software latch (the family bridge has no native stop); after
it no step, reset or seed is accepted until `mhs.safety.reset` clears the latch, and the last observation and tick
stay readable. No physical device is modelled.

Tags: flightmare, flightgym, quadrotor, reinforcement-learning, simulation, gymnasium

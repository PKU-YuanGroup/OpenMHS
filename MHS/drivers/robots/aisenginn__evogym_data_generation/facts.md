# Facts and tags for gh.aisenginn/evogym_data_generation

Every fact cites its source at commit `91c05ab7a793f86e099c21d377f183c95c9990cd`. The same facts are written into
`driver.py` (`facts = [...]`); the generated `reference.json`/`REFERENCE.md` come from the driver, not from this page.
The driver serves the registered `Walker-v0` environment (`evogym.envs.walk:WalkingFlat`), the first confirmed
entry symbol of the card.

| fact | source | ref |
|---|---|---|
| The repository is built on Evogym, a simulation environment for evolutionary robotics and soft robots | vendor_doc | README.md:7 |
| The package requires Python >=3.7 and <3.11 | upstream_code | pyproject.toml:40 |
| The package depends on gymnasium and numpy<2.0.0 | upstream_code | pyproject.toml:46-49 |
| Installation builds the CMake extension evogym.simulator_cpp from evogym/simulator | upstream_code | setup.py:61-65 |
| WalkingFlat is the concrete environment class of evogym.envs.walk | upstream_code | evogym/envs/walk.py:15 |
| Walker-v0 is registered with entry point evogym.envs.walk:WalkingFlat and max_episode_steps=500 | upstream_code | evogym/envs/__init__.py:16-20 |
| WalkingFlat loads the Walker-v0 world and adds the robot body at position (1, 1) | upstream_code | evogym/envs/walk.py:26-27 |
| The number of action values is the number of actuator indices of the robot | upstream_code | evogym/envs/walk.py:33 |
| num_robot_points is the size of the robot's position array | upstream_code | evogym/envs/walk.py:34 |
| The action space is Box(low=0.6, high=1.6, shape=(num_actuators,)) | upstream_code | evogym/envs/walk.py:36 |
| The observation space is Box(low=-100.0, high=100.0, shape=(2 + num_robot_points,)) | upstream_code | evogym/envs/walk.py:37 |
| The environment's step forwards the robot action to the base step as a one-entry robot dictionary | upstream_code | evogym/envs/walk.py:45 |
| EvoGymBase.step clips every actuator value to [0.6, 1.6] before setting it | upstream_code | evogym/envs/base.py:54-57 |
| The observation concatenates the robot's centre-of-mass velocity with its relative point positions | upstream_code | evogym/envs/walk.py:51-54 |
| get_relative_pos_obs subtracts the point centre and flattens the coordinate array | upstream_code | evogym/envs/base.py:260-262 |
| The reward is the change of the robot's centre-of-mass x between the previous and the new step | upstream_code | evogym/envs/walk.py:56-59 |
| An unstable simulation subtracts 3.0 from the reward | upstream_code | evogym/envs/walk.py:62-64 |
| The goal is met when the centre-of-mass x exceeds 99 voxel sizes and adds 1.0 to the reward | upstream_code | evogym/envs/walk.py:67-69 |
| WalkingFlat.step returns five values and always reports truncated=False | upstream_code | evogym/envs/walk.py:72 |
| WalkingFlat.reset calls the base reset and returns the observation with an empty info dict | upstream_code | evogym/envs/walk.py:74-84 |
| EvoGymBase.reset ignores its seed and options arguments and resets the simulator | upstream_code | evogym/envs/base.py:65-69 |
| BenchmarkBase.VOXEL_SIZE is 0.1 | upstream_code | evogym/envs/base.py:384 |
| The simulator runs physics_updates_per_step=30 updates per environment step | upstream_code | evogym/simulator/SimulatorCPP/Sim.cpp:23 |
| Each physics update integrates 0.0001 s with the RK4 integrator | upstream_code | evogym/simulator/SimulatorCPP/Environment.cpp:190 |
| The project's own test constructs an environment with gym.make(env_name, body=body) | upstream_code | tests/screen_free/test_baseline_envs.py:29-30 |
| The Walker-v0 example supplies a body from sample_robot((5,5)) | upstream_code | examples/gym_test.py:8-9 |
| The voxel types define H_ACT as 3 and V_ACT as 4 | upstream_code | evogym/utils.py:8-15 |

Limits: the driver declares no `Limit`. The `cap.world.step.v1` action bounds are derived by the bridge from the
fake environment's `Box(0.6, 1.6, shape=(num_actuators,))`. The numeric range copies `walk.py:36`, but the actuator
count belongs to a placeholder body rather than a configured upstream instance. There is no `action_space_ref`;
the bridge records the bounds as fake-derived, without an upstream source. The upstream code also clips values to
the same numeric range (`base.py:55`). The device is simulated at R0, so no limit is
`operator_required` and no `site-limits.example.json` is shipped.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic:evogym Walker-v0 fake`, level F0, determinism
`exact` with `seed_control` `none` because the upstream reset ignores seed and options, timestep 3 ms (30 RK4 updates
of 0.0001 s), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say that the fake
is a kinematic F0 stand-in with no soft-body physics, uses four placeholder material points (an observation whose
size is not the device's), uses a placeholder 5x5 body, and was not compared with an upstream run.

Safety: simulated R0 device. The e-stop is the runtime's software latch; no native stop exists. After it, no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable. No hardware backend is
declared.

Tags: evogym, soft-robot, walker, locomotion, reinforcement-learning, simulation, gymnasium

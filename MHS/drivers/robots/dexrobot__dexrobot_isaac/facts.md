# Facts and tags for gh.dexrobot/dexrobot_isaac

The package serves the DexHand Isaac Gym environment through the `GymnasiumDriver` bridge. Every fact below cites the
pinned clone (`dc85a0b54a7051470f0162c7df22a2a1c69cfaf1`) as `upstream_code`; the same facts are in `driver.py` and
are repeated by the generated `reference.json`/`REFERENCE.md`.

## Facts

| fact | source | ref |
|---|---|---|
| The repository provides reinforcement learning environments for training dexterous manipulation policies with robotic hands using NVIDIA's Isaac Gym simulator | upstream_code | README.md:3 |
| The installation instructions require downloading Isaac Gym Preview 4 from NVIDIA before the package is installed | upstream_code | README.md:22-24 |
| The package pins the legacy Gym API, gym 0.23.1 | upstream_code | setup.py:17 |
| DexHandBase imports isaacgym and torch at module import time | upstream_code | dexhand_env/tasks/dexhand_base.py:17-21 |
| DexHandBase is the dexterous-hand environment class and extends VecTask | upstream_code | dexhand_env/tasks/dexhand_base.py:61 |
| The custom Env base declares step, reset, render and close, each raising NotImplementedError | upstream_code | dexhand_env/tasks/base/vec_task.py:155-169 |
| VecTask extends Env and parses the simulation parameters, setting dt from the configured physics timestep | upstream_code | dexhand_env/tasks/base/vec_task.py:172-205 |
| The default hand asset is dexrobot_mujoco/dexrobot_mujoco/models/dexhand021_right_simplified_floating.xml | upstream_code | dexhand_env/tasks/dexhand_base.py:170-171 |
| The hand has 6 base DOFs and 12 active finger DOFs | upstream_code | dexhand_env/constants.py:8-9 |
| The BaseTask configuration enables policy control of the hand base (6 DOFs) and the fingers (12 controls) | upstream_code | dexhand_env/cfg/task/BaseTask.yaml:32-33 |
| The action dimension is the sum of the base DOFs and the active finger DOFs that the policy controls | upstream_code | dexhand_env/components/initialization/initialization_manager.py:54-62 |
| The action space is a Box with low -1.0, high 1.0 and dtype float32, one element per action | upstream_code | dexhand_env/tasks/dexhand_base.py:1162-1169 |
| The observation space is a Box from -inf to +inf with dtype float32, one element per observation | upstream_code | dexhand_env/tasks/dexhand_base.py:1150-1160 |
| episodeLength is 300 steps | upstream_code | dexhand_env/cfg/task/BaseTask.yaml:19 |
| Timeout termination is raised when episode_step_count is at least episodeLength - 1 | upstream_code | dexhand_env/components/termination/termination_manager.py:229-237 |
| The simulation timestep is 0.005 s (200 Hz) | upstream_code | dexhand_env/cfg/task/BaseTask.yaml:10 |
| The default physics configuration uses 4 substeps and gravity [0.0, 0.0, -9.81] | upstream_code | dexhand_env/cfg/physics/default.yaml:3-4 |
| The default position_delta scaling uses a maximum finger joint velocity of 1.0 rad/s, a maximum base linear velocity of 0.5 m/s and a maximum base angular velocity of 1.5 rad/s | upstream_code | dexhand_env/cfg/task/BaseTask.yaml:41-45 |
| The BaseTask reward has an alive term of 0.1 per step | upstream_code | dexhand_env/cfg/task/BaseTask.yaml:62 |
| The BaseTask policy observation lists 13 components: base positions and velocities, active finger positions and velocities, hand pose, five contact indicators, previous actions, base and finger targets, and four 35-value fingertip and fingerpad pose blocks | upstream_code | dexhand_env/cfg/task/BaseTask.yaml:103-116 |
| The observation dimension is computed at initialization from the concatenated selected components | upstream_code | dexhand_env/components/observation/observation_encoder.py:215-234 |
| reset resets all environments and returns the observation buffer | upstream_code | dexhand_env/tasks/dexhand_base.py:805-838 |
| step applies the actions, steps physics and returns (observation, reward, done, info) | upstream_code | dexhand_env/tasks/dexhand_base.py:893-921 |
| seed seeds Python's random module, numpy and torch | upstream_code | dexhand_env/tasks/base/vec_task.py:145-153 |
| make_env is the main entry point for creating environments compatible with RL libraries such as rl_games | upstream_code | dexhand_env/factory.py:93-107 |
| make_env loads dexhand_env/cfg/task/<task_name>.yaml when no configuration is supplied | upstream_code | dexhand_env/factory.py:122-127 |
| The control timestep is measured as physics_dt times the measured number of physics steps per control step | upstream_code | dexhand_env/components/physics/physics_manager.py:243-259 |
| The initial hand position is [0.0, 0.0, 0.5] and the initial hand rotation is [0.0, 0.0, 0.0, 1.0] | upstream_code | dexhand_env/cfg/task/BaseTask.yaml:17-18 |

## Tags

`dexhand`, `dexterous-manipulation`, `isaac-gym`, `reinforcement-learning`, `simulation`, `gymnasium`.

## Contract as served

- `device_kind` is the catalogue's `world.sim`; `mode` is `simulated` and `risk` is `R0`. The three catalogue classes
  `cap.world.step.v1`, `cap.world.reset.v1` and `cap.world.seed.v1` are bound by the Gymnasium bridge from the fake
  environment's `Box` action space and `Box` observation space.
- The action input is `{values: [18 numbers]}` with every element bounded by the upstream action space's `-1.0` to
  `1.0`; `cap.world.step.v1` steps one or more ticks with that action. `cap.world.reset.v1` takes an optional seed
  and options, and `cap.world.seed.v1` records the seed for the next reset.
- The deployed model is the fake, so `fidelity_level` is `F0`: the fake integrates commanded position deltas and has
  no rigid-body dynamics, contacts, actuator model or sensor model. `timestep_ms` is 5.0 (the configured physics
  timestep), `realtime_factor` is 0, `clock` is `lockstep` and snapshots are not offered (DexHandBase has no
  `get_state`/`set_state`).
- No hardware backend exists. The only stop is the runtime's software latch: an e-stop refuses further actuation
  until `mhs.safety.reset` clears it.

## What is not covered

The fake returns a reduced model, not the Isaac Gym simulation: no contact forces, no tendon coupling, no PD
actuators, no rendering, and the fingertip/fingerpad poses are fixed offsets. The upstream control period is measured
at run time and is not exposed; the fake uses one 5 ms physics step per tick. The fake was never compared with a real
Isaac Gym run (Isaac Gym and the bundled hand model were not available where the gate ran). No physical DexHand was
modelled or validated.

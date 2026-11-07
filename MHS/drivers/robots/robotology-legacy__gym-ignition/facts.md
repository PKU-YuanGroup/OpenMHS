# Facts and tags for gh.robotology-legacy/gym-ignition

This package serves the registered legacy OpenAI Gym environment `CartPoleDiscreteBalancing-Gazebo-v0` through the
card's `GymnasiumDriver` helper. Every fact cites the clone at commit
`4bc8e0465eed68911434485ba0b9c0a6740d516e`; the same facts are written into `driver.py` (`facts = [...]`), and the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The package registers four legacy OpenAI Gym environments through gym.envs.registration.register (Pendulum-Gazebo-v0, CartPoleDiscreteBalancing-Gazebo-v0, CartPoleContinuousBalancing-Gazebo-v0 and CartPoleContinuousSwingup-Gazebo-v0) with the GazeboRuntime entry point and max_episode_steps=5000 | upstream_code | python/gym_ignition_environments/__init__.py:6-58 |
| CartPoleDiscreteBalancing-Gazebo-v0 is registered with task_cls CartPoleDiscreteBalancing, agent_rate 1000, physics_rate 1000 and real_time_factor float32 max | upstream_code | python/gym_ignition_environments/__init__.py:24-34 |
| The environments are built on the Ignition Gazebo simulator through the ScenARIO project | vendor_doc | README.md:61 |
| The runtime is a gym.Env: class Runtime(gym.Env, abc.ABC) | upstream_code | python/gym_ignition/base/runtime.py:11 |
| The runtime step sets the task action, runs Gazebo and returns observation, reward, done and info | upstream_code | python/gym_ignition/runtimes/gazebo_runtime.py:103-132 |
| The runtime reset resets the task, runs a paused Gazebo step and returns the observation | upstream_code | python/gym_ignition/runtimes/gazebo_runtime.py:134-152 |
| The runtime seed method delegates to the task and returns the list of seeds | upstream_code | python/gym_ignition/runtimes/gazebo_runtime.py:173-183 |
| The task seeds its numpy RandomState with gym.utils.seeding.np_random(seed) | upstream_code | python/gym_ignition/base/task.py:234-239 |
| A cartpole reset draws x, dx, q and dq uniformly from -0.05 to 0.05 | upstream_code | python/gym_ignition_environments/tasks/cartpole_discrete_balancing.py:144 |
| The action space is Discrete(2) | upstream_code | python/gym_ignition_environments/tasks/cartpole_discrete_balancing.py:49 |
| The cartpole force magnitude is 20.0 | upstream_code | python/gym_ignition_environments/tasks/cartpole_discrete_balancing.py:37 |
| Action 1 commands +force_mag and any other action -force_mag as the linear joint's generalized force target | upstream_code | python/gym_ignition_environments/tasks/cartpole_discrete_balancing.py:75-79 |
| The cart limits are x 2.4 m, dx 20.0 m/s, q 12 degrees and dq 3*360 degrees per second | upstream_code | python/gym_ignition_environments/tasks/cartpole_discrete_balancing.py:41-44 |
| The observation is [x, dx, q, dq] taken from the linear and pivot joint positions and velocities | upstream_code | python/gym_ignition_environments/tasks/cartpole_discrete_balancing.py:89-94 |
| The observation space is the reset box scaled by 1.2 | upstream_code | python/gym_ignition_environments/tasks/cartpole_discrete_balancing.py:61-68 |
| The episode is done when the observation leaves the reset box | upstream_code | python/gym_ignition_environments/tasks/cartpole_discrete_balancing.py:123-124 |
| The reward is 1.0 when not done and 0.0 when done, minus 0.10\|x\|, minus 0.10\|dx\| and minus 10.0 when x >= 0.9*2.4 | upstream_code | python/gym_ignition_environments/tasks/cartpole_discrete_balancing.py:102-113 |
| One environment step runs physics_rate/agent_rate simulation iterations of 1.0/physics_rate seconds | upstream_code | python/gym_ignition/runtimes/gazebo_runtime.py:196-208 |
| Gym-ignition does not provide out-of-the-box environments; the environments package holds canonical examples | vendor_doc | README.md:72-75 |

## Limits

The driver declares no `Limit` of its own. The only bound is the environment's action space, `Discrete(2)`
(`python/gym_ignition_environments/tasks/cartpole_discrete_balancing.py:49`), which the bridge derives as
`action.index` from 0 to 1. No numeric input is `operator_required`: the device is simulated at R0 and has no
hardware bound.

## Fidelity contract

`driver.py` publishes `engine` `gazebo`, `fidelity_level` `F0`, determinism `seeded` with `seed_control`
`parameter`, `timestep_ms` 1.0 (agent_rate and physics_rate are both 1000, so one environment step is one 1/1000 s
simulation iteration; `python/gym_ignition_environments/__init__.py:30-31` and
`python/gym_ignition/runtimes/gazebo_runtime.py:196-208`), `realtime_factor` 0, `clock` `lockstep`, `reset` `full`,
`snapshot_restore` false. The `gaps` say that the gate's fake is an analytic stand-in without rigid-body dynamics,
that the upstream Ignition Gazebo model was not run, that a seed does not give the same trajectory on the fake as
upstream, and that snapshot/restore are not offered.

The level is F0 on purpose: the upstream environment is an Ignition Gazebo rigid-body model, but the only path this
package ran is the analytic fake, and the contract describes the model as deployed (spec 05-fidelity FID-002).
Upstream would be F1 when the Ignition Gazebo backend is actually run.

## Safety

Simulated R0 device. There is no hardware backend and no physical stop. The e-stop is the runtime's software latch:
after it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: cartpole, gazebo, ignition-gazebo, reinforcement-learning, simulation, gym

# Facts and tags for gh.spencerfolk/rotorpy

Every fact cites its source at commit `40b09697a6a1596d404a67f459941d46a39eedd3`: `upstream_code`
(`path/in/clone.py:LINE`).  The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Quadrotor-v0 is registered to rotorpy.learning.quadrotor_environments:QuadrotorEnv | upstream_code | rotorpy/learning/__init__.py:3-6 |
| QuadrotorEnv inherits stable-baselines3's VecEnv, so it is a vectorized environment rather than a gymnasium.Env | upstream_code | rotorpy/learning/quadrotor_environments.py:37 |
| The default control abstraction is cmd_vel | upstream_code | rotorpy/learning/quadrotor_environments.py:76 |
| The metadata lists cmd_motor_speeds, cmd_motor_thrusts, cmd_ctbr, cmd_ctbm, cmd_vel and cmd_ctatt as the control modes | upstream_code | rotorpy/learning/quadrotor_environments.py:71 |
| The cmd_vel action space is Box(-1, 1, shape=(3,)) | upstream_code | rotorpy/learning/quadrotor_environments.py:141 |
| Every other control mode uses Box(-1, 1, shape=(4,)) | upstream_code | rotorpy/learning/quadrotor_environments.py:143 |
| The observation space is Box(-inf, inf, shape=(13,)) | upstream_code | rotorpy/learning/quadrotor_environments.py:137 |
| The observation concatenates position (3), velocity (3), quaternion (4) and body rates (3), so it has 13 values | upstream_code | rotorpy/learning/quadrotor_environments.py:481-487 |
| The default simulation rate is 100 Hz | upstream_code | rotorpy/learning/quadrotor_environments.py:83 |
| The simulation step is 1/sim_rate | upstream_code | rotorpy/learning/quadrotor_environments.py:123 |
| The default maximum session time is 10 s | upstream_code | rotorpy/learning/quadrotor_environments.py:80 |
| A step is done when the elapsed time reaches max_time | upstream_code | rotorpy/learning/quadrotor_environments.py:371 |
| A step is out of bounds when a velocity or body rate exceeds 100 or the position leaves the world extents | upstream_code | rotorpy/learning/quadrotor_environments.py:450-479 |
| The default world is empty free space with bounds -4 to 4 on each axis (wbound = 4) | upstream_code | rotorpy/learning/quadrotor_environments.py:170-174 |
| The cmd_vel action is rescaled to [-max_vel, max_vel] | upstream_code | rotorpy/learning/quadrotor_environments.py:440 |
| max_vel is 4/sqrt(4) | upstream_code | rotorpy/learning/quadrotor_environments.py:163 |
| The default reset bounds are pos_bound 2 and vel_bound 0 | upstream_code | rotorpy/learning/quadrotor_environments.py:23-25 |
| A reset draws position and velocity uniformly from the bounds | upstream_code | rotorpy/learning/quadrotor_environments.py:216-218 |
| A reset reseeds numpy and torch when a seed is supplied | upstream_code | rotorpy/learning/quadrotor_environments.py:298-300 |
| reset returns only the observation | upstream_code | rotorpy/learning/quadrotor_environments.py:317 |
| step returns the 4-tuple (observation, reward, dones, infos) | upstream_code | rotorpy/learning/quadrotor_environments.py:398 |
| reset replaces its options argument with self.reset_options | upstream_code | rotorpy/learning/quadrotor_environments.py:285 |
| The default reward function is vec_hover_reward | upstream_code | rotorpy/learning/quadrotor_environments.py:77 |
| vec_hover_reward adds a survival reward of 2, weights velocity at 0.1, body rate at 0 and action at 1e-5 | upstream_code | rotorpy/learning/quadrotor_reward_functions.py:56-74 |
| _minmax_scale clips a scaled command to its bounds | upstream_code | rotorpy/learning/quadrotor_environments.py:34 |
| The multirotor dynamics are integrated with rk4 | upstream_code | rotorpy/learning/quadrotor_environments.py:133 |

Limits: the driver declares none of its own.  The only bounds are the action space, which the bridge derives from
the environment (`Box(-1, 1, shape=(3,))` at `rotorpy/learning/quadrotor_environments.py:141`, no source, ref
`action_space of the fake backend .fake:FakeQuadrotorEnv`), and `ticks` (1 to the family's `max_ticks`, 10000 by
default).  The device is simulated (R0), so no bound is `operator_required` and there is no
`site-limits.example.json`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `rotorpy:Quadrotor-v0`, level F0 (the fake is kinematic:
it integrates a velocity command and computes no forces or contacts), determinism `seeded` with `seed_control`
`parameter`, timestep 10 ms (the upstream default `sim_rate = 100` Hz at
`rotorpy/learning/quadrotor_environments.py:83`, with `t_step = 1/sim_rate` at `:123`), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore.  The gaps disclose the batch-axis collapse, the unmodelled
rigid-body dynamics, the difference between the fake's Python RNG and upstream's numpy/torch seeding, and the lack
of auto-reset, rendering and snapshot support.

Safety: simulated R0 device.  There is no native stop; the e-stop is the runtime's software latch.  After it no
step or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: quadrotor, uav, multirotor, reinforcement-learning, simulation, gymnasium, rotorpy

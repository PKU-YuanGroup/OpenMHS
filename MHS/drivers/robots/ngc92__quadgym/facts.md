# Facts and tags for gh.ngc92/quadgym

Every fact cites its source at commit `f7eb2fecaad5fcfbf2b8a5b9ef3062b809b64b99`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are in
`facts = [Fact(text, source=..., ref=...)]` in `driver.py`; `reference.json` is generated from the driver, not from
this page.

The device is the simulated attitude environment `QuadrotorStabilizeAttitude-MotorCommands-v0`
(`gym_quadrotor/__init__.py:19-23`). Every action moves the simulated attitude; no fact below is a safety limit.

Scope: one package serves one environment. The card lists four entry symbols; this package serves the first one,
`gym_quadrotor.envs:CopterStabilizeAttitudeEnv` (`gym_quadrotor/envs/attitude_env.py:11`, registered as
`QuadrotorStabilizeAttitude-MotorCommands-v0` at `gym_quadrotor/__init__.py:19-23`). The other card symbols are
`CopterStabilizeAttitude2DEnv` (`gym_quadrotor/envs/minimal.py:17`) and
`CopterStabilizeAttitude2DMarkovianEnv` (`gym_quadrotor/envs/minimal.py:73`); the fourth card entry
(`CopterStabilizeAttitudeEnvAngular`, card line `gym_quadrotor/__init__.py:25`, confidence `recon`) is the
registration of a factory function (`gym_quadrotor/envs/attitude_env.py:58-60`), not a class. Serving another
environment would change `env_id`, `native` and the fake, one package each.

| fact | source | ref |
|---|---|---|
| The action space is Box(0, 1, (4,)): four motor commands between zero and one | upstream_code | gym_quadrotor/envs/base.py:18 |
| The observation is [roll, pitch, wrapped yaw, roll rate, pitch rate, yaw rate] as a float array | upstream_code | gym_quadrotor/envs/attitude_env.py:42-47 |
| The observation space is Box(0, 1, (6,)), which does not bound the state; the source carries a TODO to fix it | upstream_code | gym_quadrotor/envs/attitude_env.py:8-12 |
| A step clips the action to [0, 1], sets each desired rotor speed to sqrt(action) times max_rotor_speed, integrates one 0.02 s step and returns the state, reward, done and info | upstream_code | gym_quadrotor/envs/base.py:43-52 |
| The default maximum rotor speed is 500.0 | upstream_code | gym_quadrotor/dynamics/copter.py:19 |
| Rotor speeds approach the desired speed with gamma = 1 - 0.5**(dt / rotor_speed_half_time) and are clamped at zero | upstream_code | gym_quadrotor/dynamics/dynamics.py:86-90 |
| The default rotor_speed_half_time is 1/16 s | upstream_code | gym_quadrotor/dynamics/copter.py:20 |
| The attitude reward is -angle_factor * angle_error - angvel_factor * sum(angular_velocity^2), with angle_error = pitch^2 + roll^2 + yaw^2 | upstream_code | gym_quadrotor/envs/reward.py:24-30 |
| The environment uses AttitudeReward(1.0, attitude_error_transform=np.sqrt), so the angle term is the square root of the squared angle error | upstream_code | gym_quadrotor/envs/attitude_env.py:19 |
| The target band is 1 degree and the in-target bonus is 0.5 | upstream_code | gym_quadrotor/envs/attitude_env.py:16-17 |
| The bonus is added separately for roll, pitch and yaw when each absolute error is below the target | upstream_code | gym_quadrotor/envs/attitude_env.py:34-39 |
| Roll and pitch are clipped at pi/4; when clipping happens the reward is reduced by the boundary penalty 1.0 | upstream_code | gym_quadrotor/envs/attitude_env.py:18-26 |
| A reset randomises roll and pitch within 20 degrees and the angular velocity within 2.0, sets yaw uniformly in [-0.3, 0.3], places the copter at altitude 1 and halves the yaw rate | upstream_code | gym_quadrotor/envs/attitude_env.py:49-55 |
| The environment step never signals done: _step_copter always returns False | upstream_code | gym_quadrotor/envs/attitude_env.py:29 |
| The environment id is registered with max_episode_steps=500, so gym.make wraps it in a 500-step TimeLimit | upstream_code | gym_quadrotor/__init__.py:19-23 |
| The legacy seed() calls gym.utils.seeding.np_random and returns [seed] | upstream_code | gym_quadrotor/envs/base.py:39-41 |
| Body angular velocity is mapped to Euler-angle rates through the 3x3 matrix of the roll and pitch angles | upstream_code | gym_quadrotor/dynamics/coordinates.py:176-180 |

Tags (short lowercase keywords): `quadrotor`, `attitude-control`, `flight-dynamics`, `reinforcement-learning`,
`simulation`, `gymnasium`.

## What the fake does not cover

`fake.py` re-implements the rotational equations in pure Python; the driver's `fidelity.gaps` lists every known
omission: no contacts, no aerodynamic or sensor model, Python's random stream instead of numpy's, no rendering, no
snapshot, and the observation space's upstream mismatch. The fake was never compared with a run of the upstream
environment; the gate only checks the contract on the fake backend.

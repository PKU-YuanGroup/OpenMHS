# Facts and tags for gh.jjshoots/pyflyt

Every fact cites the upstream clone at commit `9095d41f6fc5f07fe711346b747b4f7fd475b424`. The same facts are
written into `driver.py` (`facts = [...]`); `reference.json` is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| PyFlyt/QuadX-Hover-v4 is registered with entry point PyFlyt.gym_envs.quadx_envs.quadx_hover_env:QuadXHoverEnv | upstream_code | PyFlyt/gym_envs/__init__.py:8-11 |
| The hover action is [vp, vq, vr, T]: angular velocity setpoints and thrust | upstream_code | PyFlyt/gym_envs/quadx_envs/quadx_hover_env.py:15 |
| The flight-mode-0 action space is a four-element Box with low [-pi, -pi, -pi, 0.0] and high [pi, pi, pi, 0.8] | upstream_code | PyFlyt/gym_envs/quadx_envs/quadx_base_env.py:80-103 |
| The quaternion attitude space has 13 elements and the combined observation space has 13 + 4 + 4 = 21 elements | upstream_code | PyFlyt/gym_envs/quadx_envs/quadx_base_env.py:62-115 |
| The hover observation concatenates body angular velocity (3), quaternion orientation (4), body linear velocity (3), ground linear position (3), the previous action (4) and the auxiliary state | upstream_code | PyFlyt/gym_envs/quadx_envs/quadx_hover_env.py:96-115 |
| The Aviary state is body angular velocity, ground angular position, body linear velocity and ground linear position | upstream_code | PyFlyt/core/aviary.py:335-351 |
| The QuadX auxiliary state is the throttle of each motor | upstream_code | PyFlyt/core/drones/quadx.py:536 |
| Motors.get_states returns the throttle level of each motor | upstream_code | PyFlyt/core/abstractions/motors.py:97-104 |
| The hover environment defaults to flight_mode 0, flight_dome_size 3.0, max_duration_seconds 10.0, quaternion angle_representation and agent_hz 40 | upstream_code | PyFlyt/gym_envs/quadx_envs/quadx_hover_env.py:30-40 |
| max_steps is int(agent_hz * max_duration_seconds) and env_step_ratio is int(120 / agent_hz) | upstream_code | PyFlyt/gym_envs/quadx_envs/quadx_base_env.py:117-123 |
| The episode truncates when step_count exceeds max_steps | upstream_code | PyFlyt/gym_envs/quadx_envs/quadx_base_env.py:255-259 |
| The episode terminates with reward -100.0 when the drone touches the floor or leaves the flight dome | upstream_code | PyFlyt/gym_envs/quadx_envs/quadx_base_env.py:261-271 |
| Each step starts with reward -0.1; the dense hover reward adds 1.0 and subtracts the distance to [0, 0, 1], the roll-pitch angle and 0.01 times the square of the yaw rate | upstream_code | PyFlyt/gym_envs/quadx_envs/quadx_hover_env.py:117-138 |
| The base step sets reward to -0.1 before running the controllers | upstream_code | PyFlyt/gym_envs/quadx_envs/quadx_base_env.py:283-300 |
| reset passes the seed to gymnasium.Env.reset and stabilises the Aviary for 10 steps | upstream_code | PyFlyt/gym_envs/quadx_envs/quadx_base_env.py:152-216 |
| Aviary physics_hz defaults to 240 and physics_period is 1/physics_hz | upstream_code | PyFlyt/core/aviary.py:156-164 |
| Aviary.step advances updates_per_step = physics_hz / min(control_hz) physics steps | upstream_code | PyFlyt/core/aviary.py:287-290 |
| The QuadX control loop defaults to control_hz 120 | upstream_code | PyFlyt/core/drones/quadx.py:22-28 |
| The observation space is a Box with -inf/inf bounds and dtype float64 | upstream_code | PyFlyt/gym_envs/quadx_envs/quadx_base_env.py:73-115 |

## Limits

The driver declares no `Limit` of its own. The action bounds are derived by the Gymnasium bridge from the fake
environment's action space (a `Box` with low `[-pi, -pi, -pi, 0.0]` and high `[pi, pi, pi, 0.8]`); the bridge gives
that bound no source and the ref `action_space of the fake backend .fake:FakeQuadXHoverEnv`. The `ticks` range (1
to 10000) is the bridge's step bound, not a device limit. This is a simulated R0 package and there is no
operator-required bound.

## Fidelity

`driver.py` declares engine `PyFlyt:PyFlyt/QuadX-Hover-v4`, level F0 (a kinematic stand-in), timestep 25 ms at the
default settings, determinism `seeded` with `seed_control` `parameter`, `realtime_factor` 0, `clock` `lockstep`,
`reset` `full` and no snapshot/restore. The 25 ms follows from the cited defaults: agent_hz 40 gives three
environment steps per Aviary control step, each Aviary step runs two 240 Hz physics steps, so one environment step
is 3 * 2 / 240 s = 0.025 s. The fake does not reproduce the upstream PyBullet dynamics, contacts, motors, sensors,
wind or numpy random stream; the fidelity `gaps` list those omissions and the fact that the fake was never compared
with a real PyFlyt run.

## Safety

This is a simulated R0 device. The e-stop is the runtime's software latch: after it no step or reset is accepted
until `mhs.safety.reset` clears the latch, and the environment state stays readable. There is no physical stop path
and no hardware backend.

## Tags

pyflyt, quadx, uav, quadrotor, hover, gymnasium, simulation

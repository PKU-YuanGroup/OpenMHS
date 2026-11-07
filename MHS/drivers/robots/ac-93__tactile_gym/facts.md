# Facts and tags for gh.ac-93/tactile_gym

Every fact cites `upstream_code` at commit `28417ebaf52ac325200c4fbd351cd13c6a466f7d`, a path from the clone root.
The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not
from this page.

| fact | source | ref |
|---|---|---|
| `edge_follow-v0` is registered with entry point `tactile_gym.rl_envs.exploration.edge_follow.edge_follow_env:EdgeFollowEnv` | upstream_code | `tactile_gym/rl_envs/__init__.py:3-6` |
| `EdgeFollowEnv` computes a simulation time step of 1/240 s, a control rate of 1/10 s and a velocity action repeat of `floor(control_rate / sim_time_step)` | upstream_code | `tactile_gym/rl_envs/exploration/edge_follow/edge_follow_env.py:32-37` |
| The `EdgeFollowEnv` constructor's default `max_steps` is 250 | upstream_code | `tactile_gym/rl_envs/exploration/edge_follow/edge_follow_env.py:25` |
| The termination distance to the goal is 0.01 m | upstream_code | `tactile_gym/rl_envs/exploration/edge_follow/edge_follow_env.py:67` |
| The `mg400` branch sets the TCP limits x -0.150 to +0.150, y -0.11 to +0.11, z -0.1 to +0.1, roll and pitch 0 to 0 and yaw -pi to +pi | upstream_code | `tactile_gym/rl_envs/exploration/edge_follow/edge_follow_env.py:71-79` |
| `min_action` and `max_action` are -0.25 and 0.25 | upstream_code | `tactile_gym/rl_envs/exploration/edge_follow/edge_follow_env.py:140` |
| The action space is a `Box` with `low=min_action`, `high=max_action` and shape `(act_dim,)` | upstream_code | `tactile_gym/rl_envs/exploration/edge_follow/edge_follow_env.py:168-174` |
| `get_act_dim` returns 2 when `movement_mode` is `xy` | upstream_code | `tactile_gym/rl_envs/exploration/edge_follow/edge_follow_env.py:478-480` |
| The oracle observation concatenates the TCP position, the TCP linear velocity, the goal position and the edge angle | upstream_code | `tactile_gym/rl_envs/exploration/edge_follow/edge_follow_env.py:454-475` |
| The dense reward is `-((1.0 * goal_dist) + (10.0 * edge_dist) + (1.0 * yaw_dist))` with `yaw_dist` 0 | upstream_code | `tactile_gym/rl_envs/exploration/edge_follow/edge_follow_env.py:440-451` |
| The edge angle is drawn uniformly from -pi to pi on every reset | upstream_code | `tactile_gym/rl_envs/exploration/edge_follow/edge_follow_env.py:237-240` |
| The edge length is 0.105 for `mg400`/`magician` and 0.175 for the other arms, and the edge height is 0.035 | upstream_code | `tactile_gym/rl_envs/exploration/edge_follow/edge_follow_env.py:208-216` |
| `reset` returns the starting observation | upstream_code | `tactile_gym/rl_envs/exploration/edge_follow/edge_follow_env.py:333-336` |
| The observation space for `observation_mode` `oracle` is a `Dict` with one `Box` from -inf to +inf whose shape is the oracle observation shape | upstream_code | `tactile_gym/rl_envs/base_tactile_env.py:76-91` |
| `step` returns `(observation, reward, done, {})`, the legacy Gym API four-tuple, not the Gymnasium five-tuple | upstream_code | `tactile_gym/rl_envs/base_tactile_env.py:166-185` |
| `seed` sets the environment RNG through `gym.utils.seeding.np_random` | upstream_code | `tactile_gym/rl_envs/base_tactile_env.py:61-64` |
| `close` disconnects PyBullet and destroys the OpenCV windows | upstream_code | `tactile_gym/rl_envs/base_tactile_env.py:69-74` |

## Limits

The driver declares no `Limit`. The only bound the bridge enforces is the environment's action space, which it
derives from the fake's `Box(-0.25, 0.25, shape=(2,))` (`action.values` with source `upstream_code` and the ref
`tactile_gym/rl_envs/exploration/edge_follow/edge_follow_env.py:140`). `ticks` is bounded by
`GymnasiumDriver.max_ticks` (10000 by default). The TCP limits at `edge_follow_env.py:71-79` are limits of the
simulated robot controller, not of this interface, so they are stated as a Fact and not as a Limit. The device is
simulated (R1), so no limit is `operator_required` and there is no operator overlay (`site-limits.example.json`).

## Risk

The device is `mode = "simulated"` and `risk = "R1"`. The package has no hardware backend and never touches a
PyBullet process or a robot. The R1 classification follows MHS-004 section 2.1, which lists simulation stepping as a
low-energy bounded action; the card's `safety.risk_floor` is R0 and is not exceeded downward. Because the driver is
simulated, no independent physical stop exists and none is claimed: an e-stop is the runtime's software latch, after
which no step or reset is accepted until `mhs.safety.reset` clears the latch, and the last state stays readable. The
e-stop is not a hardware safety function and nothing here was tested on hardware.

## Fidelity

`fidelity` declares the model as deployed: engine `analytic:tactile_gym/edge_follow-v0`, level F0 (kinematic, no
dynamics), determinism `seeded` with `seed_control` `parameter`, `timestep_ms` 100.0 (one control interval of 1/10 s;
upstream repeats the velocity action 24 times at a simulation step of 1/240 s), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot/restore. The gaps state that the fake is a 2-D kinematic stand-in with no
PyBullet dynamics, arm IK, contacts or tactile sensor, that its `random.Random` stream differs from upstream's numpy
generator, that only the oracle observation is modelled, and that the `sim` backend was not run.

## Deployment configuration

`env_kwargs` passes `env_modes`: the class's own `env_modes_default` at `edge_follow_env.py:13-20` (`xy`,
`TCP_velocity_control`, `fixed_height`, `oracle`, `dense`, `mg400`) plus `tactile_sensor_name: tactip`, which the
constructor reads at `edge_follow_env.py:59` but the default dict omits; the demo sets that key at
`examples/demo_edge_env.py:23`. This is deployment configuration, not a Fact and not a bound. The fake implements the
`xy` action dimension (2) and the oracle observation space of this configuration.

## Other entry symbols

The card lists five environment classes. This package implements the first, `EdgeFollowEnv` (`edge_follow-v0`); the
other four are not implemented (one device per package, as the playbook says):

| symbol | class file:line |
|---|---|
| `SurfaceFollowAutoEnv` (`surface_follow-v0`) | `tactile_gym/rl_envs/exploration/surface_follow/surface_follow_auto/surface_follow_auto_env.py:15` |
| `SurfaceFollowGoalEnv` (`surface_follow-v1`) | `tactile_gym/rl_envs/exploration/surface_follow/surface_follow_goal/surface_follow_goal_env.py:15` |
| `ObjectRollEnv` (`object_roll-v0`) | `tactile_gym/rl_envs/nonprehensile_manipulation/object_roll/object_roll_env.py:23` |
| `ObjectPushEnv` (`object_push-v0`) | `tactile_gym/rl_envs/nonprehensile_manipulation/object_push/object_push_env.py:25` |

The observation modes `tactile`, `visual`, `visuotactile` and their `*_and_feature` variants
(`base_tactile_env.py:76-113`) would carry camera images and tactile arrays. They are not modelled by the fake: the
deployed configuration is `observation_mode: oracle`, and the fake serves only the 10-value oracle vector. The
tactile, visual and `extended_feature` arrays are NOT COVERED by this package.

## Tags

`tactile`, `edge-follow`, `pybullet`, `robot-arm`, `exploration`, `reinforcement-learning`, `simulation`, `gymnasium`

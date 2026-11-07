# Facts and tags for gh.angelomorgado/carla-gymdrive

Every fact cites its source at commit `7d950f9d90d20b7dfbc17fa5b77e67437bde2d29` (`upstream_code`: a file of the
clone at the pinned path and line). The same facts are written into `driver.py` (`facts = [...]`); the reference file
is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The environment is registered as carla-rl-gym-v0 with entry point src.env.environment:CarlaEnv and max_episode_steps config.ENV_MAX_STEPS | upstream_code | src/env/environment.py:41-45 |
| The default constructor starts with continuous actions, a 60-second time limit and server initialization on | upstream_code | src/env/environment.py:58 |
| The continuous action space is a two-element Box from -1.0 to 1.0: steering and throttle/brake | upstream_code | src/env/observation_action_space.py:32-33 |
| The discrete action space is Discrete(4): accelerate, decelerate, turn left, turn right | upstream_code | src/env/observation_action_space.py:35-36 |
| The observation declares the RGB image as 360 x 640 x 3 and the LiDAR array as 3 x 500 | upstream_code | src/env/observation_action_space.py:5-12 |
| The observation also carries position, target position, next waypoint position, speed and a situation index | upstream_code | src/env/observation_action_space.py:22-30 |
| The situation map maps Road to 0, Roundabout to 1, Junction to 2 and Tunnel to 3 | upstream_code | src/env/observation_action_space.py:15-20 |
| The simulator connects to a CARLA server at localhost:2000 with a 100 s timeout | upstream_code | src/config/configuration.py:17-19 |
| SIM_FPS is 30 | upstream_code | src/config/configuration.py:23 |
| The world applies its synchronous flag to the CARLA settings and, when synchronous, fixes the delta to 1.0 / SIM_FPS seconds | upstream_code | src/carlacore/world.py:99-105 |
| ENV_MAX_STEPS is 430, the maximum number of steps per episode | upstream_code | src/config/configuration.py:27 |
| reset returns the initial observation and an info dict with the scenario name and the waypoints | upstream_code | src/env/environment.py:162-170 |
| step ticks the world in synchronous mode, applies the vehicle control and returns observation, reward, terminated, truncated and info | upstream_code | src/env/environment.py:179-219 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`continuous_action_space = spaces.Box(low=np.array([-1.0, -1.0]), high=np.array([1.0, 1.0]))` at
`src/env/observation_action_space.py:33`, or `discrete_action_space = spaces.Discrete(4)` at `:36`); the reference
shows the derived `action.values` or `action.index` bound. The device is simulated (R0), so no limit is
`operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:carla-rl-gym-v0 (CARLA server at
localhost:2000)`, level F0 (the fake is a kinematic stand-in: no vehicle dynamics, contacts or sensors), determinism
`seeded` with `seed_control` `parameter`, timestep 33.333 ms (the upstream synchronous fixed delta of `1.0 / SIM_FPS`
at `src/carlacore/world.py:103`, with `SIM_FPS = 30` at `src/config/configuration.py:23`), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore. The gaps name the real observation sizes
(360 x 640 x 3 RGB and 3 x 500 LiDAR) against the fake's smaller stand-ins, the Python-number values, the upstream
PreProcessing step that is not modelled, the placeholder reward and termination, traffic/weather/rendering, the
different random generators, and say that the fake was never compared with CARLA.

Safety: simulated R0 device. The e-stop is the runtime's software latch (there is no hardware stop); after it no
step or reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and
the world state stays readable. There is no hardware backend.

Tags: carla, driving, reinforcement-learning, simulation, gymnasium, sim-env

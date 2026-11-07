# Facts and tags for gh.farama-foundation/highwayenv

Every fact cites its source at commit `2a268f348f10f4d1ac83f96bc8a53d2fa50dd3b0` (`upstream_code`: a line of the
clone). The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the
driver, not from this page.

| fact | source | ref |
|---|---|---|
| highway-v0 registers highway_env.envs.highway_env:HighwayEnv | upstream_code | highway_env/__init__.py:46-49 |
| The action space is DiscreteMetaAction with five meta-actions: 0 LANE_LEFT, 1 IDLE, 2 LANE_RIGHT, 3 FASTER and 4 SLOWER | upstream_code | highway_env/envs/common/action.py:204 |
| The action space is Discrete(len(actions)), five when both lateral and longitudinal actions are enabled | upstream_code | highway_env/envs/common/action.py:252-253 |
| The Kinematics observation has the features presence, x, y, vx and vy and observes five vehicles by default | upstream_code | highway_env/envs/common/observation.py:166-172 |
| The Kinematics observation space is Box(-inf, inf, shape=(vehicles_count, len(features))), a (5, 5) array in the default configuration | upstream_code | highway_env/envs/common/observation.py:207-213 |
| The default configuration has 4 lanes, 50 vehicles, 1 controlled vehicle and an episode duration of 40 s | upstream_code | highway_env/envs/highway_env.py:35-39 |
| The simulation runs at 15 Hz and the policy at 1 Hz | upstream_code | highway_env/envs/common/abstract.py:114-115 |
| Each policy step adds 1 / policy_frequency to the simulated time | upstream_code | highway_env/envs/common/abstract.py:276 |
| The episode terminates when the ego vehicle has crashed, or when offroad_terminal is set and the vehicle is off the road | upstream_code | highway_env/envs/highway_env.py:141-147 |
| The episode is truncated when the simulated time reaches the configured duration | upstream_code | highway_env/envs/highway_env.py:149-151 |
| The reward weights are collision_reward -1, right_lane_reward 0.1 and high_speed_reward 0.4, with reward_speed_range [20, 30] and normalize_reward set | upstream_code | highway_env/envs/highway_env.py:42-49 |
| With normalize_reward the weighted reward is mapped from [collision_reward, high_speed_reward + right_lane_reward] to [0, 1] and multiplied by the on-road term | upstream_code | highway_env/envs/highway_env.py:110-120 |
| Vehicles of the default configuration are created at 25 m/s | upstream_code | highway_env/envs/highway_env.py:81-86 |
| The straight road network is built with speed_limit 30 m/s | upstream_code | highway_env/envs/highway_env.py:61-64 |
| The environment resets itself in AbstractEnv.__init__ | upstream_code | highway_env/envs/common/abstract.py:91 |
| reset(seed, options) forwards the seed to gym.Env.reset and rebuilds the spaces and the scene | upstream_code | highway_env/envs/common/abstract.py:234-249 |
| highway-fast-v0 is the same environment with simulation_frequency 5, 3 lanes, 20 vehicles and a duration of 30 s | upstream_code | highway_env/envs/highway_env.py:162-175 |
| The repository registers exit-v0 and exit-v1 (ExitEnv and ConnectedLaneExitEnv) before highway-v0 | upstream_code | highway_env/__init__.py:36-43 |
| The repository registers intersection-v0, intersection-v1 and intersection-v2 around IntersectionEnv | upstream_code | highway_env/__init__.py:55-67 |

## The contract and the fidelity

The bridge derives the contract from the environment's spaces, so the driver declares no parameter and no limit of
its own: `cap.world.step.v1` takes `{ticks, action}` with `action.index` bounded by the five meta-actions (0 to 4),
`cap.world.reset.v1` takes `{seed, options}` and `cap.world.seed.v1` takes `{seed}`. The task card's other entry
symbols are `ExitEnv`/`ConnectedLaneExitEnv` (`exit-v0`/`exit-v1`), `HighwayEnvFast` (`highway-fast-v0`) and
`IntersectionEnv` (`intersection-v0`); this package implements `HighwayEnv` (`highway-v0`), the base environment.

The fidelity is declared in `driver.py` (`fidelity = {...}`): engine `highway_env:highway-v0`, level `F0`
(kinematic), determinism `seeded` with seed control by parameter, 1000 ms per tick (one policy step of
1 / policy_frequency = 1 s), realtime_factor 0, clock lockstep, full reset and no snapshot/restore. The `gaps` list
says what the fake does not model: the road network, the kinematic/IDM vehicle dynamics, the (5, 5) observation
array (the fake returns 25 flat numbers), rendering and the reward values of a particular episode. The `sim` backend
(`gymnasium.make("highway-v0")`) was not run: the upstream environment needs gymnasium, numpy, pandas, pygame-ce and
noise, which are not installed where the gate runs.

Tags: highway, autonomous-driving, traffic-simulation, reinforcement-learning, simulation, gymnasium

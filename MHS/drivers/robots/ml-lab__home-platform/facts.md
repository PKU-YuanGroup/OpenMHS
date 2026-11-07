# Facts and tags for gh.ml-lab/home-platform

Every fact cites its source at commit `cbd373f270faaf19f21ed88f0e3bd272a1cbdaa6`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Home-v0 is registered with entry point home_platform.gym.envs:HomeEnv, max_episode_steps 1000 and reward_threshold 0.0 | upstream_code | home_platform/gym/__init__.py:3-8 |
| HomeEnv subclasses gym.Env | upstream_code | home_platform/gym/envs/home_env_basic.py:13 |
| The action has two components, moving and looking, each a Discrete 5 action 0 to 4 (NOOP, UP, RIGHT, DOWN, LEFT) | upstream_code | home_platform/gym/envs/home_env_basic.py:17-30 |
| The constructor defaults turning_speed to 0.1 and moving_speed to 100 | upstream_code | home_platform/gym/envs/home_env_basic.py:34 |
| The action space is constructed as spaces.MultiDiscrete([[0, 4], [0, 4]]) | upstream_code | home_platform/gym/envs/home_env_basic.py:47 |
| The observation is a Dict: position and orientation of 3 values each in -100 to 100, an image of 500 x 500 x 3 values in 0 to 255, and a collision flag of 0 or 1 | upstream_code | home_platform/gym/envs/home_env_basic.py:48-61 |
| Each step applies moving then looking, advances the environment one step, and returns the observation with reward 0, done False and misc None | upstream_code | home_platform/gym/envs/home_env_basic.py:130-144 |
| Looking action 1 subtracts turning_speed from heading, 2 adds it to roll, 3 adds it to heading and 4 subtracts it from roll | upstream_code | home_platform/gym/envs/home_env_basic.py:91-108 |
| Moving action 1 applies a +moving_speed impulse on y, 2 +x on x, 3 -y on y and 4 -x on x | upstream_code | home_platform/gym/envs/home_env_basic.py:110-128 |
| A reset places the agent at (42, -39, 1) with orientation (0, 0, 0), advances the environment once, increments the house index and wraps it at the end of the list | upstream_code | home_platform/gym/envs/home_env_basic.py:146-168 |
| The clone ships one house id (list_of_houses) and _seed asserts seed < len(list_of_houses), so the only valid house index is 0 | upstream_code | home_platform/gym/envs/home_env_basic.py:68-89 |
| BasicEnvironment defaults its integration interval dt to 0.1 seconds | upstream_code | home_platform/env.py:93 |
| BasicEnvironment.step advances the physics and render worlds by dt, which is the configured 0.1 s unless realtime is set | upstream_code | home_platform/env.py:225-234 |
| The agent is a Bullet capsule of radius 0.1, height 1.6 and mass 60.0 | upstream_code | home_platform/env.py:100-107 |

Limits: the driver declares none. The only bounds are the action space and `ticks`, which the Gymnasium bridge derives
from the fake environment: `action.values` is two integers 0 to 4 (the documented moving and looking components) and
`ticks` is 1 to the bridge's `max_ticks` (10000 by default). They come from the fake environment (no source, ref
`action_space of the fake backend .fake:FakeHomeEnv`) and the bridge, not a driver Limit; the device is simulated
(R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `home-platform:Home-v0`, level F0 (the fake is a
kinematic/analytic stand-in with no rigid-body dynamics, contacts, friction, renderer or sensor model), determinism
`seeded` with `seed_control` `parameter`, timestep 100 ms (`dt = 0.1` s at `home_platform/env.py:93`, one
`BasicEnvironment.step` per environment step at `home_env_basic.py:136`), `realtime_factor` 0, clock `lockstep`, reset
`full`, no snapshot and restore. The gaps list the smaller placeholder image (4 x 4 x 3 against the upstream
500 x 500 x 3 at `home_env_basic.py:57`), the always-zero collision flag, the missing 1000-step TimeLimit of
`gym.make("Home-v0")`, the seed handling (upstream asserts `seed < len(list_of_houses)` at `home_env_basic.py:85`
while the fake maps any non-negative seed to the only house), and that the upstream package was never imported or
compared.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: household, multimodal, reinforcement-learning, simulation, gymnasium

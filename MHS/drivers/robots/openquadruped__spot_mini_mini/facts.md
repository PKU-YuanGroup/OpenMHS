# Facts and tags for gh.openquadruped/spot_mini_mini

Every fact cites its source at commit `c7e4905be176c63fa0e68a09c177b937e916fa60`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The facts are declared in
`driver.py`; the reference files are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| SpotMicroEnv-v0 is registered with entry point `spotmicro.spot_gym_env:spotGymEnv` and `max_episode_steps` 1000 | upstream_code | `spotmicro/spot_gym_env.py:47-51` |
| `spotGymEnv` simulates the locomotion of a quadruped robot; its docstring says the action space is the desired motor angle for each motor | upstream_code | `spotmicro/spot_gym_env.py:62-69` |
| `NUM_MOTORS` is 12 | upstream_code | `spotmicro/spot_gym_env.py:31` |
| The action bound `_action_bound` is 1 | upstream_code | `spotmicro/spot_gym_env.py:240` |
| The action space is `spaces.Box(-action_high, action_high)` with `action_high` made of `_action_bound` for `action_dim = NUM_MOTORS` | upstream_code | `spotmicro/spot_gym_env.py:280-282` |
| The observation bounds come from `Spot.GetObservationUpperBound()` plus `OBSERVATION_EPS` and `GetObservationLowerBound()` minus `OBSERVATION_EPS` | upstream_code | `spotmicro/spot_gym_env.py:276-279` |
| The observation upper bound is 2*pi for roll and pitch, infinity for the three angular rates and three linear accelerations, 2.0 for the four leg phases and 1.0 for the four contacts | upstream_code | `spotmicro/spot.py:590-597` |
| The observation lower bound is minus the upper bound | upstream_code | `spotmicro/spot.py:600-602` |
| `GetObservation` appends roll, pitch, the angular twist xyz, the linear acceleration xyz, the leg phases and, when contacts are enabled, the four foot contacts | upstream_code | `spotmicro/spot.py:688-703` |
| The `contacts` constructor option defaults to True | upstream_code | `spotmicro/spot_gym_env.py:118` |
| `is_fallen` returns true when the dot product of the world up direction and the base's local up direction is below 0.55 | upstream_code | `spotmicro/spot_gym_env.py:536-551` |
| `_termination` returns `is_fallen()` or whether the base distance exceeds `_distance_limit` | upstream_code | `spotmicro/spot_gym_env.py:553-556` |
| `distance_limit` defaults to `float("inf")` | upstream_code | `spotmicro/spot_gym_env.py:87` |
| The simulation time step is 0.01 s and the control period is `_time_step * _action_repeat` | upstream_code | `spotmicro/spot_gym_env.py:198-211` |
| `action_repeat` defaults to 1, and `pd_control_enabled` and `accurate_motor_model_enabled` default to False | upstream_code | `spotmicro/spot_gym_env.py:91-105` |
| `seed` calls `gym.utils.seeding.np_random` and returns `[seed]` | upstream_code | `spotmicro/spot_gym_env.py:382-384` |
| `step` returns a numpy observation, the reward, `done` and an empty info dictionary | upstream_code | `spotmicro/spot_gym_env.py:440` |
| `env_randomizer` defaults to a `SpotEnvRandomizer` instance | upstream_code | `spotmicro/spot_gym_env.py:107` |
| `SpotEnvRandomizer` seeds numpy's global generator with 0 in its constructor | upstream_code | `spotmicro/spot_env_randomizer.py:37` |
| The constructor creates a pybullet_utils `BulletClient`, so the environment runs on PyBullet | upstream_code | `spotmicro/spot_gym_env.py:264-268` |
| The environment metadata declares the human and rgb_array render modes and 50 video frames per second | upstream_code | `spotmicro/spot_gym_env.py:72-75` |

Tags (short lowercase keywords): `spot`, `quadruped`, `robot`, `locomotion`, `pybullet`, `reinforcement-learning`,
`simulation`, `gym`.

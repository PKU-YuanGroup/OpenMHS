# Facts and tags for gh.duburcqa/jiminy

Every fact cites its source at commit `accdf3629d9d8c08bb97f2905f010f1616d2168a`. Every entry is `upstream_code`,
because the claims come from the source of the clone, not from a manual. The same facts are written into `driver.py`
(`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The environment is registered as 'cartpole' with max_episode_steps=500, order_enforce=False and disable_env_checker=True | upstream_code | python/gym_jiminy/envs/gym_jiminy/envs/__init__.py:31-38 |
| The environment step period STEP_DT and the controller update period CONTROL_DT are both 0.02 s | upstream_code | python/gym_jiminy/envs/gym_jiminy/envs/cartpole.py:20-23 |
| The failure thresholds are 2.4 for the cart position and 12 degrees for the pole angle | upstream_code | python/gym_jiminy/envs/gym_jiminy/envs/cartpole.py:24-27 |
| The sampling ranges of cart position, pole angle, cart velocity and pole velocity are all 0.05 | upstream_code | python/gym_jiminy/envs/gym_jiminy/envs/cartpole.py:28-35 |
| The constructor's continuous flag defaults to False, so the discrete action space is selected | upstream_code | python/gym_jiminy/envs/gym_jiminy/envs/cartpole.py:82-84 |
| The two encoder sensors are 'slider' on slider_to_cart and 'pole' on cart_to_pole, attached in that order | upstream_code | python/gym_jiminy/envs/gym_jiminy/envs/cartpole.py:117-121 |
| The EncoderSensor fieldnames are Q and V, so its measurement matrix has a position row then a velocity row | upstream_code | core/src/hardware/basic_sensors.cc:394 |
| The observation flattens the EncoderSensor measurement matrix with reshape((-1,)) | upstream_code | python/gym_jiminy/envs/gym_jiminy/envs/cartpole.py:197-199 |
| The observation space is a Box with the symmetric position bounds [X_THRESHOLD, THETA_THRESHOLD] and the robot's velocity limit | upstream_code | python/gym_jiminy/envs/gym_jiminy/envs/cartpole.py:158-169 |
| The three discrete commands are -command_limit, zero and +command_limit, where command_limit is the motor effort limit | upstream_code | python/gym_jiminy/envs/gym_jiminy/envs/cartpole.py:131-134 |
| The action space is Discrete(len(AVAIL_CTRL)) when continuous is False | upstream_code | python/gym_jiminy/envs/gym_jiminy/envs/cartpole.py:171-180 |
| The cart motor effort limit is 10 N | upstream_code | data/toys_models/cartpole/cartpole.urdf:25 |
| The cart is 1.0 kg | upstream_code | data/toys_models/cartpole/cartpole.urdf:37-40 |
| The pole is a 0.1 kg point mass at 1.0 m from its joint | upstream_code | data/toys_models/cartpole/cartpole.urdf:59-64 |
| The simulation uses the euler_explicit integrator with dtMax = CONTROL_DT | upstream_code | python/gym_jiminy/envs/gym_jiminy/envs/cartpole.py:139-147 |
| A reset samples cart position and pole angle, then cart velocity and pole velocity, from the environment's np_random generator | upstream_code | python/gym_jiminy/envs/gym_jiminy/envs/cartpole.py:184-195 |
| A discrete action selects its force from AVAIL_CTRL | upstream_code | python/gym_jiminy/envs/gym_jiminy/envs/cartpole.py:201-208 |
| The reward is 1.0 if the episode is not terminated and 0.0 otherwise | upstream_code | python/gym_jiminy/envs/gym_jiminy/envs/cartpole.py:210-216 |
| By default has_terminated returns terminated=False and truncates when the observation is out of bounds | upstream_code | python/gym_jiminy/common/gym_jiminy/common/envs/generic.py:1434-1464 |
| A step truncates when the observation is out of bounds or the simulation exceeds simulation_duration_max | upstream_code | python/gym_jiminy/common/gym_jiminy/common/envs/generic.py:843-849 |
| The default simulation_duration_max is 86400 s | upstream_code | python/gym_jiminy/common/gym_jiminy/common/envs/generic.py:125 |

The observation is the flat `EncoderSensor` matrix: row Q is the slider then the pole joint, row V is the slider then
the pole velocity (`core/src/hardware/basic_sensors.cc:394`, `cartpole.py:117-121`), and `reshape((-1,))` flattens it
row by row (`cartpole.py:197-199`). The four values are therefore `[cart position, pole angle, cart velocity, pole
velocity]`, not the OpenAI Gym order `[cart position, cart velocity, pole angle, pole velocity]`.

The action space is not the OpenAI Gym `Discrete(2)`. `AVAIL_CTRL` is a three-element tuple of the motor effort limit,
zero and the opposite effort (`cartpole.py:131-134`); with the 10 N joint effort limit (`cartpole.urdf:25`) action 0
applies -10 N, action 1 applies 0 N and action 2 applies +10 N. The docstring table at `cartpole.py:54-58` still
describes two actions; the code at `cartpole.py:177-180` and `:208` is authoritative and is what the bridge derives.

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Discrete(3)`: `action.index` from 0 to 2, with no source and the ref
`action_space of the fake backend .fake:FakeCartPoleJiminyEnv`), and `ticks` (1 to `max_ticks`,
10000 by default). The device is simulated (R0), so no limit is `operator_required`.

Termination and truncation: the default `BaseJiminyEnv.has_terminated` returns `terminated=False` and truncates when
the observation leaves the Box of `cartpole.py:158-169` (`generic.py:1434-1464`); a step also truncates at
`simulation_duration_max` (`generic.py:843-849`, default 86400 s at `generic.py:125`), and the registration adds the
500-step limit that `gymnasium.make` applies through its `TimeLimit` wrapper (`__init__.py:31-38`). The reward is
computed from `terminated` only (`cartpole.py:210-216`), so the truncating step still pays 1.0.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:cartpole`, level F1 (rigid-body cart-pole, no
contacts, no friction, no actuator, sensor or noise model), determinism `seeded` with `seed_control` `parameter`,
timestep 20 ms (`STEP_DT = 0.02` s, `cartpole.py:21`), `realtime_factor` 0, clock `lockstep`, reset `full`, no
snapshot and restore. The gaps say what is not modelled, that the fake is a point-mass re-implementation and that it
was never compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: cartpole, classic-control, reinforcement-learning, simulation, gymnasium, jiminy

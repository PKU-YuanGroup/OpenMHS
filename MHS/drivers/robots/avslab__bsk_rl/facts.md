# Facts and tags for gh.avslab/bsk_rl

Every fact cites `upstream_code` at commit `e307f335a3f133ef6dc528a9bb3b2ceb06329605`; the same facts are written into
`driver.py` (`facts = [...]`), and `reference.json` is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| SatelliteTasking-v1 is registered to bsk_rl.gym:SatelliteTasking | upstream_code | src/bsk_rl/__init__.py:22-25 |
| SatelliteTasking is the single-satellite special case of GeneralSatelliteTasking and exposes the satellite's action space directly | upstream_code | src/bsk_rl/gym.py:582-604 |
| SatelliteTasking exposes the satellite's observation space directly | upstream_code | src/bsk_rl/gym.py:606-610 |
| SatelliteTasking refuses to be constructed with anything but exactly one satellite | upstream_code | src/bsk_rl/gym.py:595-599 |
| The multi-satellite base composes a Tuple of the satellites' action spaces | upstream_code | src/bsk_rl/gym.py:480-487 |
| The multi-satellite observation space composes the satellites' observation spaces and calls reset() when no simulator exists yet | upstream_code | src/bsk_rl/gym.py:489-505 |
| A satellite subclass defines observation_spec and action_spec, which determine its observation and action spaces | upstream_code | src/bsk_rl/sats/__init__.py:9-12 |
| The documented construction passes a configured satellite instance to gymnasium.make('SatelliteTasking-v1', ...) | upstream_code | src/bsk_rl/sats/__init__.py:32 |
| With a discrete action spec the satellite's action space is Discrete(sum of each action's n_actions) | upstream_code | src/bsk_rl/act/discrete_actions.py:34-37 |
| An integer action outside the discrete action space raises ValueError('Action index ... out of range') | upstream_code | src/bsk_rl/act/discrete_actions.py:84 |
| Downlink is a DiscreteFSWAction | upstream_code | src/bsk_rl/act/discrete_actions.py:218 |
| DiscreteFSWAction contributes one discrete action (n_actions=1) | upstream_code | src/bsk_rl/act/discrete_actions.py:139 |
| Image is a DiscreteAction and Image(n_ahead_image) contributes n_ahead_image discrete actions | upstream_code | src/bsk_rl/act/discrete_actions.py:244-272 |
| A list observation becomes Box(low=-1e16, high=1e16, shape=(len,)) and a scalar observation becomes a Box of shape (1,) | upstream_code | src/bsk_rl/obs/observations.py:43-48 |
| A Time observation returns the simulation time divided by its normalization, and the normalization is the time limit when norm is not set | upstream_code | src/bsk_rl/obs/observations.py:298-311 |
| The observation builder derives its space from the first observation it builds | upstream_code | src/bsk_rl/obs/observations.py:150-154 |
| reset stores self.seed, calls gymnasium's Env.reset(seed) and numpy.random.seed; a missing seed is time_ns() % 2**32 | upstream_code | src/bsk_rl/gym.py:341-346 |
| The reset options argument is unused | upstream_code | src/bsk_rl/gym.py:331-333 |
| Each reset sets latest_step_duration to 0.0 s | upstream_code | src/bsk_rl/gym.py:356 |
| reset returns the observation and the info mapping | upstream_code | src/bsk_rl/gym.py:408-411 |
| A step applies a non-no-action action through Satellite.set_action and then runs the simulator | upstream_code | src/bsk_rl/gym.py:514-527 |
| Satellite.set_action forwards the action to its action builder | upstream_code | src/bsk_rl/sats/satellite.py:320-326 |
| Each step measures latest_step_duration as the change in simulator time | upstream_code | src/bsk_rl/gym.py:525-527 |
| The step reward is the sum of the rewarder's reward_dict plus failure_penalty for each dead satellite | upstream_code | src/bsk_rl/gym.py:456-462 |
| The episode terminates when a satellite is not alive or its rewarder terminates | upstream_code | src/bsk_rl/gym.py:464-472 |
| The episode truncates when simulator time reaches time_limit or a rewarder truncates | upstream_code | src/bsk_rl/gym.py:474-478 |
| The step returns observation, reward, terminated, truncated and info | upstream_code | src/bsk_rl/gym.py:556-570 |
| info reports each satellite's requires_retasking and the last step duration as d_ts | upstream_code | src/bsk_rl/gym.py:443-454 |
| SatelliteTasking flattens the satellite's info entries to the top level of the step info | upstream_code | src/bsk_rl/gym.py:624-629 |
| A single-satellite step wraps the scalar action in a one-element list | upstream_code | src/bsk_rl/gym.py:617-619 |
| close deletes the simulator when one exists | upstream_code | src/bsk_rl/gym.py:576-579 |
| UniqueImageReward rewards each newly imaged target by its priority, once per target | upstream_code | src/bsk_rl/data/unique_image_data.py:192-199 |

## Limits

The driver declares no Limit and no site-limits overlay. The upstream action space is a property of the configured
satellite, not a fixed number of the environment: the discrete builder sums the `n_actions` of the actions in the
satellite's `action_spec` (`src/bsk_rl/act/discrete_actions.py:34-37`). The bridge therefore derives `action.index`
from the live environment that the fake backend serves, with no source and the reference
`action_space of the fake backend .fake:FakeSatelliteTasking`; that reference is deliberately not a `path:LINE` and G4
does not check it as one. The fake's configuration is test data (see `fake.py`), not a bound of the upstream
environment, so no Limit is authored from it. A deployment that replaces the fake with the real environment gets the
real satellite's action space and therefore the real bound.

## Fidelity contract

`engine` is `bsk_rl:SatelliteTasking-v1`, `fidelity_level` is `F0` because the checked model is the analytic
stand-in (tasking state only, no dynamics), `timestep_ms` is 0 because an environment step is event-driven,
`realtime_factor` is 0, the clock is `lockstep`, reset is `full`, and snapshot/restore is false (upstream exposes no
`get_state`/`set_state`). Determinism is `seeded` with `seed_control` `parameter`: reset accepts a seed and the fake
repeats a trajectory for the same seed and actions, but it uses Python's `random.Random` while upstream seeds numpy's
global generator, so the two do not share a random stream. The gaps name the absent Basilisk dynamics, the fake
configuration, the fixed fake step duration, the random-stream difference, the absent snapshot, and the unrun `sim`
backend (which needs installed bsk_rl/Basilisk and a configured satellite in `env_kwargs`).

## Safety

Simulated R0 device. There is no hardware backend and no native stop: the e-stop is the runtime's software latch, and
after it no step or reset is accepted until `mhs.safety.reset` clears the latch; the world state stays readable. No
operator-required bound exists.

Tags: satellite, tasking, astrodynamics, basilisk, reinforcement-learning, simulation, gymnasium

# Facts and tags for gh.lucasalegre/sumo-rl

Every fact cites its source at commit `86f0fc41401eeca724b2e8878f5020dc6d70c9b4`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

This package implements the card's only entry symbol, `sumo_rl.environment.env:SumoEnvironment`, through the
`sumo-rl-v0` registration. The upstream gym test creates that registration on the single-intersection network
(`tests/gym_test.py:8-14`); the driver configures the same network and the fake models a single traffic signal with
two green phases and four controlled lanes.

| fact | source | ref |
|---|---|---|
| sumo-rl-v0 is registered with entry point sumo_rl.environment.env:SumoEnvironment and kwargs single_agent=True | upstream_code | sumo_rl/environment/__init__.py:6-10 |
| SumoEnvironment is a gymnasium.Env for traffic signal control with the SUMO simulator | upstream_code | sumo_rl/environment/env.py:51-56 |
| The environment module raises ImportError when SUMO_HOME is not set | upstream_code | sumo_rl/environment/env.py:8-12 |
| The constructor requires net_file and route_file | upstream_code | sumo_rl/environment/env.py:96-97 |
| num_seconds, the simulated seconds of one episode, defaults to 20000 | upstream_code | sumo_rl/environment/env.py:102 |
| delta_time, the simulated seconds between actions, defaults to 5 and yellow_time defaults to 2 | upstream_code | sumo_rl/environment/env.py:106-107 |
| min_green defaults to 5 s and max_green defaults to 50 s | upstream_code | sumo_rl/environment/env.py:108-109 |
| sumo_seed defaults to 'random', so a run without a reset seed is not reproducible | upstream_code | sumo_rl/environment/env.py:117 |
| sim_max_time is begin_time plus num_seconds | upstream_code | sumo_rl/environment/env.py:142 |
| reset closes the previous simulation, increments the episode, masks a supplied seed to 31 bits and starts SUMO again | upstream_code | sumo_rl/environment/env.py:263-271 |
| For single_agent the reset returns (observation, info) | upstream_code | sumo_rl/environment/env.py:280-281 |
| For single_agent step returns (observation, reward, terminated, truncated, info); terminated is always False and truncated is dones['__all__'] | upstream_code | sumo_rl/environment/env.py:305-313 |
| The episode truncates when sim_step is at least sim_max_time | upstream_code | sumo_rl/environment/env.py:341-344 |
| close stops the SUMO simulation and sets self.sumo to None | upstream_code | sumo_rl/environment/env.py:459-472 |
| sumo_seed is passed to SUMO as --seed unless it is 'random', which passes --random | upstream_code | sumo_rl/environment/env.py:228-231 |
| The action space is Discrete(num_green_phases), one action per green phase | upstream_code | sumo_rl/environment/traffic_signal.py:118 |
| The default reward is the change in cumulative vehicle delay, with waiting times divided by 100 | upstream_code | sumo_rl/environment/traffic_signal.py:232-236 |
| The default observation concatenates the one-hot green phase, a min-green flag, lane densities and lane queues | upstream_code | sumo_rl/environment/observations.py:38-43 |
| The observation space is Box from 0 to 1 with length num_green_phases + 1 + 2 * len(lanes) | upstream_code | sumo_rl/environment/observations.py:45-50 |
| The upstream gym test creates sumo-rl-v0 with the single-intersection network and num_seconds=100 | upstream_code | tests/gym_test.py:8-14 |
| The single-intersection network has two incoming lanes from the north and two from the west | upstream_code | sumo_rl/nets/single-intersection/single-intersection.net.xml:41-55 |
| The single-intersection network declares two green phases and two yellow phases | upstream_code | sumo_rl/nets/single-intersection/single-intersection.net.xml:58-63 |

Limits: the driver declares none. The only input bound is the action space, which the bridge derives from the
environment (`Discrete(2)` on the configured single-intersection network: `action.index` from 0 to 1, with no source
and the ref `action_space of the fake backend .fake:FakeSumoEnvironment`). `ticks` is bounded by the catalogue class
and `max_ticks` (1 to 10000 by default). The device is simulated (R0), so no limit is `operator_required`; there is
nothing for an operator overlay to fill and no `site-limits.example.json`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `sumo-rl:SUMO traffic signal control`, level F0 (the
fake is an analytic/kinematic stand-in without vehicle dynamics), determinism `seeded` with `seed_control`
`parameter` (a reset seed is masked to 31 bits and passed to SUMO as `--seed`, while the upstream default is
`random`), timestep 5000 ms (one environment step advances `delta_time` 5 s), `realtime_factor` 0, clock `lockstep`,
reset `full`, no snapshot and restore. The gaps say what is not modelled, that the fake was not compared with the
upstream environment, and that the sim backend was not run because it needs `SUMO_HOME`, the upstream package and
SUMO.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable. The package declares no
hardware backend and no physical stop path.

Tags: sumo-rl, sumo, traffic-signal-control, reinforcement-learning, simulation, gymnasium

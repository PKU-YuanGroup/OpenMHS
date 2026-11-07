OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.google-research/football

Every fact cites its source at commit `3d9e754720a95621bba6475c4d3b0d56fe919014`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The registered environment ids are built for every scenario name as GFootball-{env_name}-SMM-v0, GFootball-{env_name}-Pixels-v0, GFootball-{env_name}-simple115-v0 and GFootball-{env_name}-simple115v2-v0, with entry point gfootball.env:create_environment | upstream_code | gfootball/__init__.py:23-58 |
| create_environment constructs football_env.FootballEnv(c) and calls _apply_output_wrappers before returning it | upstream_code | gfootball/env/__init__.py:212-225 |
| The output wrapper chain applies the reward, representation, single-agent and GetState wrappers | upstream_code | gfootball/env/__init__.py:76-86 |
| FootballEnv.action_space is Discrete(action-set length) when one player is agent-controlled | upstream_code | gfootball/env/football_env.py:49-57 |
| The default action set is action_set_v1: 19 actions from idle through release_dribble | upstream_code | gfootball/env/football_action_set.py:129-135 |
| The default config action_set is 'default' | upstream_code | gfootball/env/config.py:87 |
| The simple115 observation is a Box with 115 values per controlled player, float32, bounds -inf to inf | upstream_code | gfootball/env/wrappers.py:108-111 |
| The simple115 layout is 88 player values (backfilled with -1 when fewer than 11 players), then the ball position array, the ball direction array, a 3-value possession one-hot, 11 active-player flags and 7 game-mode flags | upstream_code | gfootball/env/wrappers.py:161-188 |
| The raw observation's ball position and ball direction are each arrays of three values | upstream_code | gfootball/env/football_env_core.py:296-304 |
| The 11_vs_11_stochastic scenario sets game_duration 3000 and deterministic False | upstream_code | gfootball/scenarios/11_vs_11_stochastic.py:23-25 |
| The episode is done when the step count reaches game_duration | upstream_code | gfootball/env/football_env_core.py:238-242 |
| FootballEnv.step returns observation, reward, done and info; reset returns the observation | upstream_code | gfootball/env/football_env.py:183-190 |
| The engine runs 100 physics steps per second | upstream_code | gfootball/env/constants.py:20-21 |
| The default config advances 10 physics steps per frame | upstream_code | gfootball/env/config.py:94 |
| The default config is not real-time paced (real_time False) | upstream_code | gfootball/env/config.py:96 |
| The default config's player list is agent:left_players=1 | upstream_code | gfootball/env/config.py:92 |
| FootballEnvCore.reset starts a new episode and resets the action set and step counter | upstream_code | gfootball/env/football_env_core.py:109-120 |

Limits: the driver declares none of its own. The only bound is the action space, which the bridge derives from the
environment (`Discrete(19)`: `action.index` from 0 to 18, with no source and the ref `action_space of the fake backend .fake:FakeFootballEnv`), and `ticks` (1 to `max_ticks`, 10000 by default). The device is simulated (R0), so no limit is
`operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gfootball:fake-simple115`, level F0 (a kinematic
stand-in, no dynamics), determinism `none` (the upstream scenario is stochastic and its reset takes no seed or
options), timestep 100 ms (10 physics steps per frame at 100 physics steps per second), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled: players, goals, reward,
contacts and physics, the C++ engine, seed control and snapshots; the fake was not compared with an upstream run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: football, gfootball, reinforcement-learning, simulation, gymnasium

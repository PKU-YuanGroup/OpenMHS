# Facts and tags for gh.clementperroud/gym-trading-env

Every fact cites its source at commit `a86fc03d29759374fae2db7df4d878485808a730`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The package registers the environment as TradingEnv with entry point gym_trading_env.environments:TradingEnv | upstream_code | src/gym_trading_env/__init__.py:3-8 |
| The package also registers MultiDatasetTradingEnv, a TradingEnv that switches dataset on reset | upstream_code | src/gym_trading_env/__init__.py:9-14 |
| The constructor's default positions list is [0, 1] | upstream_code | src/gym_trading_env/environments.py:81 |
| The action space is spaces.Discrete(len(positions)): the integer action indexes the positions list | upstream_code | src/gym_trading_env/environments.py:112 |
| The observation space is a Box from -np.inf to +np.inf with one element per static feature plus one dynamic feature per function | upstream_code | src/gym_trading_env/environments.py:113-123 |
| A column of the DataFrame is a static feature when its name contains 'feature' | upstream_code | src/gym_trading_env/environments.py:130 |
| Two dynamic features are added by default: the last position taken and the real position of the portfolio | upstream_code | src/gym_trading_env/environments.py:43-46 |
| The default reward is the logarithm of the portfolio valuation at a step divided by the valuation at the previous step | upstream_code | src/gym_trading_env/environments.py:17-18 |
| Step first trades to positions[position_index] when an action is given, then advances the row index | upstream_code | src/gym_trading_env/environments.py:233-235 |
| The portfolio starts at portfolio_initial_value, 1000 by default | upstream_code | src/gym_trading_env/environments.py:87 |
| The episode is done when the portfolio valuation is 0 or below | upstream_code | src/gym_trading_env/environments.py:246-247 |
| The episode is truncated when the row index reaches the last row of the DataFrame | upstream_code | src/gym_trading_env/environments.py:248 |
| A reset sets step 0 and row index 0, and draws the position uniformly from positions when initial_position is 'random' | upstream_code | src/gym_trading_env/environments.py:163-167 |
| When windows is an integer W, the observation is a stack of the last W rows | upstream_code | src/gym_trading_env/environments.py:118-123 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Discrete(len(positions))`: `action.index` from 0 to `len(positions) - 1`, with no source and the ref
`action_space of the fake backend .fake:FakeTradingEnv`), and `ticks` (1 to `max_ticks`, 10000 by default). The number
of positions is a constructor argument, not a fixed bound of a device, so it is not written into a Limit here: the
bridge reads it from the live environment. The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:TradingEnv`, level F0 (the row of the supplied
dataset is the state transition; no device dynamics), determinism `seeded` with `seed_control` `parameter`, timestep
0 ms because the dataset fixes the interval between rows (not declared by the environment), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore. The gaps say that no order book, slippage, latency or market
impact is modelled, that the fake replays a canned series, and that nothing was validated against a market.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: trading, reinforcement-learning, simulation, gymnasium

The `fake` backend is a pure Python re-implementation of the class's public `reset`/`step` behaviour over a synthetic
price series. It is not the upstream environment: it was not compared with a real run, and its series, starting
value and feature count are test data (marked `# placeholder` in `fake.py`), not facts or limits.

"""OpenMHS driver for gh.clementperroud/gym-trading-env: the ``TradingEnv`` Gymnasium environment.

A ``GymnasiumDriver`` is configuration only: ``env_id`` names the environment and the bridge derives the whole
contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action
``{index}`` bounded by ``spaces.Discrete(len(positions))``, ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a
machine and no operator-required limit.

The ``fake`` backend is the package's own pure Python stand-in (fake.py).  A backend name that ``backends`` does
not list (``sim``) is served by ``gymnasium.make(env_id, **env_kwargs)`` (``GymnasiumDriver.open_native``): the
driver names ``env_module = "gym_trading_env"`` because importing it runs the module-level ``register`` calls
(``src/gym_trading_env/__init__.py:1-14``), and ``env_kwargs`` supplies the constructor's required ``df``
(``src/gym_trading_env/environments.py:37`` and ``:79-80``) as a deterministic 120-row OHLC frame with one
``feature_close`` column and a second-resolution ``DatetimeIndex``, so the observation space is one static plus the
two default dynamic features (the same width the fake models).  The index resolution matters: reset and step copy
``self.df.index.values[idx]`` into the history info (``environments.py:189`` and ``:256``), and a nanosecond
``datetime64`` turns into an integer nanoseconds count above 2**53-1, which the bridge's canonical state hash
refuses; a second-resolution one turns into a Python datetime, which the bridge treats as non-JSON info and omits.
The gate's fake-only interpreter may not have pandas; then ``env_kwargs`` is empty, which the fake backend ignores.
The sim install has pandas because it is a declared dependency (``pyproject.toml:20``).

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every constant and rule cites a line of the clone at the pinned commit
(a86fc03d29759374fae2db7df4d878485808a730).  This package is model-authored and unreviewed.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "src/gym_trading_env/environments.py"
INIT = "src/gym_trading_env/__init__.py"
FRAME_ROWS = 120

try:  # pandas is a declared dependency (pyproject.toml:20); the fake gate's interpreter need not have it
    import numpy as _np
    import pandas as _pd
except ImportError:  # the fake backend ignores env_kwargs; the sim install provides both distributions
    _np = _pd = None


def _market_frame():
    """The deterministic market DataFrame the constructor requires (environments.py:37 and :79-80)."""
    close = _np.arange(100.0, 100.0 + FRAME_ROWS)
    return _pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "feature_close": _np.concatenate(([0.0], close[1:] / close[:-1] - 1.0)),
        },
        # A DatetimeIndex is required (environments.py:37) but its resolution is free.  reset and step record the
        # row date from df.index.values (environments.py:189 and :256); a nanosecond datetime64 becomes an integer
        # nanoseconds count above 2**53-1, which the bridge's canonical state hash refuses, while a second-resolution
        # datetime64 becomes a Python datetime, which the bridge's jsonable() refuses as info, so the state is JSON.
        index=_pd.date_range("2024-01-01", periods=FRAME_ROWS, freq="h", unit="s"),
    )


class TradingEnvDriver(GymnasiumDriver):
    device_id = "gym-trading-env"
    env_id = "TradingEnv"
    env_module = "gym_trading_env"  # importing it runs register(...) at src/gym_trading_env/__init__.py:3-14
    env_kwargs = {"df": _market_frame()} if _pd is not None else {}
    native = "gym_trading_env.environments:TradingEnv"
    backends = {"fake": ".fake:FakeTradingEnv"}
    display_name = "Gym Trading Env TradingEnv"
    vendor, model = "Clement Perroud", "gym-trading-env"
    tags = ["trading", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("Importing gym_trading_env runs the module-level register(...) call that registers TradingEnv with "
             "entry point gym_trading_env.environments:TradingEnv", source="upstream_code", ref=f"{INIT}:1-8"),
        Fact("The package also registers MultiDatasetTradingEnv, a TradingEnv that switches dataset on reset",
             source="upstream_code", ref=f"{INIT}:9-14"),
        Fact("The TradingEnv constructor requires a pandas DataFrame df whose columns contain open, high, low and "
             "close and whose index is a DatetimeIndex; each column whose name contains 'feature' is an "
             "observation", source="upstream_code", ref=f"{ENV}:37"),
        Fact("df is the constructor's first argument and has no default", source="upstream_code",
             ref=f"{ENV}:79-80"),
        Fact("Reset records the row's date in the history info as self.df.index.values[idx]; step records it the "
             "same way at environments.py:256", source="upstream_code", ref=f"{ENV}:189"),
        Fact("The constructor's default positions list is [0, 1]", source="upstream_code", ref=f"{ENV}:81"),
        Fact("The action space is spaces.Discrete(len(positions)): the integer action indexes the positions list",
             source="upstream_code", ref=f"{ENV}:112"),
        Fact("The observation space is a Box from -np.inf to +np.inf with one element per static feature plus one "
             "dynamic feature per function", source="upstream_code", ref=f"{ENV}:113-123"),
        Fact("A column of the DataFrame is a static feature when its name contains 'feature'", source="upstream_code",
             ref=f"{ENV}:130"),
        Fact("Two dynamic features are added by default: the last position taken and the real position of the "
             "portfolio", source="upstream_code", ref=f"{ENV}:43-46"),
        Fact("The default reward is the logarithm of the portfolio valuation at a step divided by the valuation "
             "at the previous step", source="upstream_code", ref=f"{ENV}:17-18"),
        Fact("Step first trades to positions[position_index] when an action is given, then advances the row index",
             source="upstream_code", ref=f"{ENV}:233-235"),
        Fact("The portfolio starts at portfolio_initial_value, 1000 by default", source="upstream_code",
             ref=f"{ENV}:87"),
        Fact("The episode is done when the portfolio valuation is 0 or below", source="upstream_code",
             ref=f"{ENV}:246-247"),
        Fact("The episode is truncated when the row index reaches the last row of the DataFrame",
             source="upstream_code", ref=f"{ENV}:248"),
        Fact("A reset sets step 0 and row index 0, and draws the position uniformly from positions when "
             "initial_position is 'random'", source="upstream_code", ref=f"{ENV}:163-167"),
        Fact("When windows is an integer W, the observation is a stack of the last W rows", source="upstream_code",
             ref=f"{ENV}:118-123"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:TradingEnv",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) reseeds the environment's random generator; the market series and the trade "
                     "arithmetic are deterministic, so one implementation repeats a trajectory for the same seed "
                     "and actions.  The package's fake draws the initial position with Python's random.Random and "
                     "upstream with numpy's generator, so a seed can pick a different position on the two",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "event-driven market model: one step advances one row of the supplied dataset and the interval between "
            "rows is not declared by the environment, so timestep_ms is 0",
            "the market data, the features, the fees, the borrow interest and the reward are those of the supplied "
            "DataFrame and the user's functions: no order book, slippage, latency or market impact is modelled",
            "the fake backend replays a fixed synthetic price series in pure Python and was not compared with the "
            "upstream environment (pandas, numpy and gymnasium are not needed by the gate): its observations and "
            "trajectories differ from a real run",
            "no physical device is modelled and the model was never validated against a market",
            "snapshot and restore are not offered: TradingEnv exposes no get_state or set_state",
        ],
    }

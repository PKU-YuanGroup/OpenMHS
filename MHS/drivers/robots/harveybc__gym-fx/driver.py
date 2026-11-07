"""OpenMHS driver for gh.harveybc/gym-fx: the backtrader-backed GymFxEnv trading environment.

A ``GymnasiumDriver`` is configuration only: the bridge derives ``cap.world.step.v1``, ``cap.world.reset.v1`` and
``cap.world.seed.v1`` from the environment's spaces and reset/step methods.  The default action space is
``Discrete(3)`` (0 hold, 1 long, 2 short), so the bridge bounds ``action.index`` to 0..2; the observation is the
default six-block ``Dict`` of the preprocessor plugin (prices, returns, position, equity_norm,
unrealized_pnl_norm, steps_remaining_norm).  The device is simulated (R0): there is no hardware backend and no
operator-required limit.

The upstream environment cannot be opened here: ``GymFxEnv`` needs a config plus six plugin instances
(``app/env.py:113-124``), a pandas CSV feed and backtrader, and package code never imports the clone.  The ``fake``
backend is therefore the package's own pure Python stand-in (``fake.py``); it mirrors the default spaces,
``reset(seed=..., options=...)`` and ``step(action)`` only.  No Gymnasium environment id is registered by the
upstream project, so the ``sim`` backend (``gymnasium.make``) was not used; the fake backend is the checked one.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002), not of the
upstream engine: the fake is an analytic price walk, so the level is F0 and the gaps say what is missing.  Facts
cite the clone at commit 1eeecb789965f3e01e9e51f479c6f89265b03859.  This package is model-authored and unreviewed.
"""

from mhs.driver import Fact, GymnasiumDriver


class GymFx(GymnasiumDriver):
    device_id = "gym-fx"
    #: A package label for the bridge description, not a Gymnasium registration (gym_fx/__init__.py:4-12 builds
    #: the environment from a config and six plugin objects; it never calls gymnasium.register).
    env_id = "gym-fx.backtrader"
    native = "app.env:GymFxEnv"
    backends = {"fake": ".fake:FakeGymFxEnv"}
    action_space_ref = "app/env.py:181"
    display_name = "gym-fx backtrader trading environment"
    vendor, model = "harveybc", "gym-fx"
    tags = ["trading", "forex", "crypto", "backtrader", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("GymFxEnv is a Gymnasium Env subclass", source="upstream_code", ref="app/env.py:102"),
        Fact("reset(seed=..., options=...) returns the first observation and info",
             source="upstream_code", ref="app/env.py:311-340"),
        Fact("step(action) returns (observation, reward, terminated, truncated, info)",
             source="upstream_code", ref="app/env.py:342-413"),
        Fact("The default action space is Discrete(3): 0 is hold, 1 is long and 2 is short",
             source="upstream_code", ref="app/env.py:8"),
        Fact("A config can select a continuous Box(-1, +1) action with a threshold (0.33 by default)",
             source="upstream_code", ref="app/env.py:166-181"),
        Fact("The continuous action maps a value at or above the threshold to long, a value at or below its "
             "negative to short and a value between them to hold", source="upstream_code",
             ref="app/env.py:478-509"),
        Fact("The default observation contract is a Dict of prices and returns windows plus one-element position, "
             "equity_norm, unrealized_pnl_norm and steps_remaining_norm blocks",
             source="upstream_code", ref="app/env.py:65-94"),
        Fact("The default preprocessor pads the price window with its first price until window_size bars exist "
             "and sets the first return to zero", source="upstream_code",
             ref="preprocessor_plugins/default_preprocessor.py:46-52"),
        Fact("The default preprocessor normalizes equity and unrealized PnL by initial_cash and steps remaining "
             "by total_bars", source="upstream_code",
             ref="preprocessor_plugins/default_preprocessor.py:66-68"),
        Fact("reset(seed) reseeds the environment's numpy generator when a seed is given and restarts the "
             "backtrader bridge; options are accepted but not used by GymFxEnv.reset",
             source="upstream_code", ref="app/env.py:311-340"),
        Fact("step's truncated flag is always false, and terminated is true when the bridge has terminated or, "
             "in normal_realistic solvency mode, equity is at or below min_equity",
             source="upstream_code", ref="app/env.py:384-389"),
        Fact("initial_cash defaults to 10000.0 and min_equity defaults to one percent of initial_cash; both are "
             "config overrides", source="upstream_code", ref="app/env.py:127-131"),
        Fact("The timeframe comes from the config; with no timeframe the env reports 0 hours, so a bar has no "
             "fixed wall-clock duration", source="upstream_code", ref="app/env.py:666-684"),
        Fact("build_environment returns GymFxEnv when simulation_engine is backtrader (the default)",
             source="upstream_code", ref="gym_fx/__init__.py:4-12"),
        Fact("NautilusGymFxEnv subclasses GymFxEnv", source="upstream_code",
             ref="simulation_engines/nautilus_gym.py:230"),
        Fact("The default data feed and broker are offline simulations over CSV files with no network access and "
             "no live-trading path", source="vendor_doc", ref="README.md:215-218"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step, reset or seed is accepted until "
                  "mhs.safety.reset clears the runtime latch, and the last observation stays readable")
    #: Fidelity contract of the deployed model (spec 05-fidelity section 2): an analytic stand-in for the
    #: backtrader environment, not the engine itself.
    fidelity = {
        "engine": "gym-fx:backtrader",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed=...) reseeds GymFxEnv's numpy generator (app/env.py:311-314); the fake reseeds "
                     "Python's random.Random from the same seed, so its synthetic price series repeats for one "
                     "seed.  The fake and upstream do not share a random stream, so one seed does not replay the "
                     "same trajectory on both.",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no dynamics are modelled: prices are an analytic placeholder random walk, positions change directly "
            "from the action, and no order book, fill, commission, slippage, margin, stop-loss, take-profit or "
            "solvency accounting runs (the upstream wraps a backtrader Cerebro, app/env.py:4-6)",
            "the reward is a synthetic equity delta ((new_equity - prev_equity) / initial_cash), not the configured "
            "reward plugin of the upstream",
            "the fake covers only the default discrete action space and the default six-block observation; "
            "continuous actions, feature_columns, stage_b force-close, OANDA calendar and execution-cost "
            "observation blocks are not modelled",
            "no wall-clock pacing and no fixed timestep: timestep_ms is 0 because a bar has no fixed duration "
            "(app/env.py:666-684), and each step advances one synthetic bar",
            "the fake terminates at the end of its synthetic series and does not implement the upstream's "
            "min_equity termination rule; truncated is always false",
            "snapshot and restore are not offered: GymFxEnv declares no get_state/set_state, and the fake "
            "declares none either",
            "the fake was not compared with an upstream run and no upstream package was imported or executed",
        ],
    }

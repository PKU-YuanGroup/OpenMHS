# Facts and tags for gh.harveybc/gym-fx

Every fact cites its source at commit `1eeecb789965f3e01e9e51f479c6f89265b03859`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| GymFxEnv is a Gymnasium Env subclass | upstream_code | app/env.py:102 |
| reset(seed=..., options=...) returns the first observation and info | upstream_code | app/env.py:311-340 |
| step(action) returns (observation, reward, terminated, truncated, info) | upstream_code | app/env.py:342-413 |
| The default action space is Discrete(3): 0 is hold, 1 is long and 2 is short | upstream_code | app/env.py:8 |
| A config can select a continuous Box(-1, +1) action with a threshold (0.33 by default) | upstream_code | app/env.py:166-181 |
| The continuous action maps a value at or above the threshold to long, a value at or below its negative to short and a value between them to hold | upstream_code | app/env.py:478-509 |
| The default observation contract is a Dict of prices and returns windows plus one-element position, equity_norm, unrealized_pnl_norm and steps_remaining_norm blocks | upstream_code | app/env.py:65-94 |
| The default preprocessor pads the price window with its first price until window_size bars exist and sets the first return to zero | upstream_code | preprocessor_plugins/default_preprocessor.py:46-52 |
| The default preprocessor normalizes equity and unrealized PnL by initial_cash and steps remaining by total_bars | upstream_code | preprocessor_plugins/default_preprocessor.py:66-68 |
| reset(seed) reseeds the environment's numpy generator when a seed is given and restarts the backtrader bridge; options are accepted but not used by GymFxEnv.reset | upstream_code | app/env.py:311-340 |
| step's truncated flag is always false, and terminated is true when the bridge has terminated or, in normal_realistic solvency mode, equity is at or below min_equity | upstream_code | app/env.py:384-389 |
| initial_cash defaults to 10000.0 and min_equity defaults to one percent of initial_cash; both are config overrides | upstream_code | app/env.py:127-131 |
| The timeframe comes from the config; with no timeframe the env reports 0 hours, so a bar has no fixed wall-clock duration | upstream_code | app/env.py:666-684 |
| build_environment returns GymFxEnv when simulation_engine is backtrader (the default) | upstream_code | gym_fx/__init__.py:4-12 |
| NautilusGymFxEnv subclasses GymFxEnv | upstream_code | simulation_engines/nautilus_gym.py:230 |
| The default data feed and broker are offline simulations over CSV files with no network access and no live-trading path | vendor_doc | README.md:215-218 |

Limits: the driver declares none of its own. The only action bound is the environment's action space; the bridge
derives `action.index` 0..2 from `Discrete(3)` (`app/env.py:8` and `:181`), so it is a derived simulation limit with
the source `upstream_code` and the ref `app/env.py:181`, not a hand-written Limit. `ticks` is bounded 1..10000 by
the bridge's `cap.world.step.v1` schema, and a reset or seed must be a non-negative integer; none is an
operator-required bound. The device is simulated (R0), so no write or invoke input needs an operator-supplied
envelope.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gym-fx:backtrader`, level F0 (an analytic price walk
with no dynamics), determinism `seeded` with `seed_control` `parameter`, `timestep_ms` 0 because a bar has no fixed
duration (`app/env.py:666-684`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The
gaps say what the fake does not model: the backtrader fill engine, commissions, slippage, margin, solvency,
stop-loss/take-profit orders, the continuous action mode and the optional observation blocks. The package fake was
not compared with an upstream run, and no upstream package was imported or executed.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step,
reset or seed is accepted until `mhs.safety.reset` clears the latch, and the last observation stays readable.

Tags: trading, forex, crypto, backtrader, reinforcement-learning, simulation, gymnasium

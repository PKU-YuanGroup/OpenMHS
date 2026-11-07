"""Fake backend of the Gym Trading Env driver: a pure Python stand-in for ``TradingEnv``.

Why a fake: the acceptance gate cannot import the upstream package (it needs pandas, numpy and gymnasium,
``pyproject.toml:22``), and package code never imports the clone.  This module re-implements the observable
behaviour of ``gym_trading_env.environments:TradingEnv`` at the pinned commit
(a86fc03d29759374fae2db7df4d878485808a730): ``reset(seed, options)`` draws the starting position, ``step`` trades
to the action's position, advances one row of the price series and returns the observation, the log-return reward
and the terminal flags.  The trade arithmetic follows ``src/gym_trading_env/utils/portfolio.py`` (one position in
[0, 1], no borrow interest by default) and the truncation rule follows ``environments.py:248``.

What this is not: the upstream environment.  The public members are the ones ``TradingEnv`` has (``reset`` and
``step``; gate G7) and the two space classes duck-type ``gymnasium.spaces.Discrete`` and ``Box`` (the bridge reads
``n``, ``start``, ``low``, ``high``, ``shape``).  Differences, all listed in the fidelity ``gaps`` of the driver:

* it replays a fixed synthetic price series instead of a user DataFrame: no market data, features, fees, borrow
  interest or reward function of the caller are modelled beyond the defaults;
* the starting position comes from Python's ``random.Random(seed)``, upstream draws it from numpy's generator;
* observations are Python floats, upstream returns a float32 array; the optional ``windows`` stack is supported
  only for rows visited in the current episode;
* it does not read a ``df`` argument, render, log metrics or expose ``get_state``/``set_state``.

The synthetic series, the starting value and every other number below are test data, not facts about the upstream
environment or a device.  Nothing here talks to a market or a device.
"""

import math
import random

# placeholder: the whole synthetic series is canned test data (120 rows, prices 100, 101, 102, ...).
PRICE_COUNT = 120
FIRST_PRICE = 100.0
PRICE_STEP = 1.0
# placeholder: the default portfolio value mirrors the constructor default only as test data.
DEFAULT_PORTFOLIO_VALUE = 1000.0


class Discrete:
    """Duck-typed ``gymnasium.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, shape=None):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = "float32"


class _Portfolio:
    """The part of ``utils/portfolio.py:1-34`` the fake needs (no interest, one asset and fiat)."""

    def __init__(self, position, value, price):
        # utils/portfolio.py:35-42 (TargetPortfolio)
        self.asset = position * value / price
        self.fiat = (1 - position) * value
        self.interest_asset = 0.0
        self.interest_fiat = 0.0

    def valorisation(self, price):
        # utils/portfolio.py:7-13
        return self.asset * price + self.fiat - self.interest_asset * price - self.interest_fiat

    def real_position(self, price):
        # utils/portfolio.py:14-15
        return (self.asset - self.interest_asset) * price / self.valorisation(price)

    def position(self, price):
        # utils/portfolio.py:16-17
        return self.asset * price / self.valorisation(price)

    def trade_to_position(self, position, price, trading_fees):
        # utils/portfolio.py:18-33
        asset_trade = position * self.valorisation(price) / price - self.asset
        if asset_trade > 0:
            asset_trade = asset_trade / (1 - trading_fees + trading_fees * position)
            self.asset = self.asset + asset_trade * (1 - trading_fees)
            self.fiat = self.fiat - asset_trade * price
        else:
            asset_trade = asset_trade / (1 - trading_fees * position)
            self.asset = self.asset + asset_trade
            self.fiat = self.fiat - asset_trade * price * (1 - trading_fees)


class FakeTradingEnv:
    """A pure Python ``TradingEnv`` over a canned price series: ``reset(seed, options)`` and ``step(action)``."""

    def __init__(self, positions=(0, 1), initial_position="random", trading_fees=0.0,
                 borrow_interest_rate=0.0, portfolio_initial_value=DEFAULT_PORTFOLIO_VALUE,
                 windows=None, max_episode_duration="max"):
        self.positions = list(positions)
        self.initial_position = initial_position
        self.trading_fees = trading_fees
        self.borrow_interest_rate = borrow_interest_rate
        self.portfolio_initial_value = float(portfolio_initial_value)
        self.windows = windows
        self.max_episode_duration = max_episode_duration
        # placeholder: the prices and the feature count are the fake's canned data.
        self._prices = [FIRST_PRICE + PRICE_STEP * index for index in range(PRICE_COUNT)]
        self._nb_features = 3                      # one static feature plus the two default dynamic features
        self.action_space = Discrete(len(self.positions))                 # environments.py:112
        self.observation_space = Box([-math.inf] * self._nb_features,    # environments.py:113-117
                                     [math.inf] * self._nb_features)
        if self.windows is not None:
            self.observation_space = Box([-math.inf] * self.windows * self._nb_features,
                                         [math.inf] * self.windows * self._nb_features,
                                         shape=[self.windows, self._nb_features])
        self._rng = random.Random()
        self._idx = 0
        self._step = 0
        self._position = 0
        self._portfolio = None
        self._previous_value = self.portfolio_initial_value
        self._rows = []

    def reset(self, seed=None, options=None):
        # environments.py:163-199; options is accepted but the fake declares no reset options.
        if seed is not None:
            self._rng = random.Random(seed)
        self._step = 0
        self._position = (self._rng.choice(self.positions) if self.initial_position == "random"
                          else self.initial_position)                     # environments.py:167
        self._idx = 0
        if self.windows is not None:
            self._idx = self.windows - 1                                   # environments.py:172
        if self.max_episode_duration != "max":
            self._idx = self._rng.randint(
                self._idx, len(self._prices) - self.max_episode_duration - self._idx)
        price = self._prices[self._idx]
        self._portfolio = _Portfolio(self._position, self.portfolio_initial_value, price)
        self._previous_value = self.portfolio_initial_value
        # The dynamic feature columns start at 0 for rows before the episode start (environments.py:135-138).
        self._rows = [[self._static_feature(index), 0.0, 0.0] for index in range(self._idx)]
        self._rows.append(self._row())
        return self._observation(), self._info(0.0)

    def step(self, position_index=None):
        # environments.py:233-272
        if position_index is not None:
            self._take_action(self.positions[position_index])
        self._idx += 1
        self._step += 1
        price = self._prices[self._idx]
        portfolio_value = self._portfolio.valorisation(price)
        done, truncated = False, False
        if portfolio_value <= 0:
            done = True                                                    # environments.py:246-247
        if self._idx >= len(self._prices) - 1:
            truncated = True                                               # environments.py:248
        if isinstance(self.max_episode_duration, int) and self._step >= self.max_episode_duration - 1:
            truncated = True                                               # environments.py:250-251
        reward = 0.0 if done else math.log(portfolio_value / self._previous_value)
        self._previous_value = portfolio_value
        self._rows.append(self._row())
        return self._observation(), reward, done, truncated, self._info(reward)

    def _take_action(self, position):
        # environments.py:204-215
        if position != self._position:
            self._portfolio.trade_to_position(position, self._prices[self._idx], self.trading_fees)
            self._position = position

    def _static_feature(self, index):
        # environments.py:130-143: a precomputed column; the fake's is the close-to-close return.
        if index <= 0:
            return 0.0
        return self._prices[index] / self._prices[index - 1] - 1.0

    def _row(self):
        # environments.py:152-160: static feature at the row, then the two default dynamic features.
        price = self._prices[self._idx]
        return [self._static_feature(self._idx), self._position, self._portfolio.real_position(price)]

    def _observation(self):
        # environments.py:156-160
        if self.windows is None:
            return list(self._rows[-1])
        return [list(row) for row in self._rows[-self.windows:]]

    def _info(self, reward):
        # environments.py:186-197 and :253-264: the History row returned as info.
        price = self._prices[self._idx]
        return {
            "idx": self._idx,
            "step": self._step,
            "position": self._position,
            "real_position": self._portfolio.real_position(price),
            "portfolio_valuation": self._portfolio.valorisation(price),
            "reward": reward,
        }

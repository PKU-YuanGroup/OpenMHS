"""Fake backend of the gym-fx driver: a pure Python stand-in for the backtrader-backed GymFxEnv.

Why a fake: ``GymFxEnv`` needs a config plus six plugin instances, a pandas CSV data feed and backtrader
(``app/env.py:113-124``), and package code never imports the clone.  This module mirrors the public surface the
bridge uses from ``app.env:GymFxEnv``: ``action_space``, ``observation_space``, ``reset(seed=..., options=...)``,
``step(action)`` and ``close`` (gate G7 checks the public methods against the upstream class).  The action space
is the default ``Discrete(3)`` (``app/env.py:8`` and ``:181``); the observation is the default six-block ``Dict``
of ``preprocessor_plugins/default_preprocessor.py:70-77``.

Every device-like numeric constant below is test data, not a Fact or a Limit, and is marked ``# placeholder``.
The synthetic price series, starting cash and position size are not the upstream's CSV data or config.  What this
is not, all listed in the fidelity ``gaps`` of driver.py: the backtrader fill engine, commissions, slippage, margin,
solvency, stop-loss/take-profit orders, the continuous action mode and every optional observation block.  Nothing
here talks to a device or opens a network connection.
"""

import random

# placeholder: the fake's whole market and account state are test data.
WINDOW_SIZE = 32                                # placeholder
TOTAL_BARS = 64                                 # placeholder
INITIAL_CASH = 10000.0                          # placeholder
POSITION_SIZE = 1.0                             # placeholder
START_PRICE = 1.0                               # placeholder
STEP_SIGMA = 0.002                              # placeholder
PRICE_FLOOR = 0.01                              # placeholder

#: The action names are upstream code (app/env.py:8); the mapping itself is the fake's test data.
ACTION_NAMES = {0: "hold", 1: "long", 2: "short"}   # placeholder


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
    """Duck-typed ``gymnasium.spaces.Box``: one lower and upper bound per element."""

    def __init__(self, low, high, shape, dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(int(item) for item in shape)
        self.dtype = dtype


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: a mapping of member name to space."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _window(values, step):
    """The default preprocessor's price window (preprocessor_plugins/default_preprocessor.py:46-52)."""
    left = max(0, step - WINDOW_SIZE)
    window = list(values[left:step]) if step > 0 else []
    if len(window) < WINDOW_SIZE:
        fill = float(window[0]) if window else float(values[0])
        window = [fill] * (WINDOW_SIZE - len(window)) + window
    return window


def _returns(window):
    """``np.diff(window, prepend=window[0])`` (preprocessor_plugins/default_preprocessor.py:52)."""
    return [0.0] + [window[index] - window[index - 1] for index in range(1, len(window))]


class FakeGymFxEnv:
    """The default discrete GymFxEnv contract without pandas, numpy, backtrader or the upstream plugins."""

    def __init__(self, **options):
        # The bridge passes the driver's options; the upstream constructor takes a config and six plugin objects.
        self._options = dict(options)
        self.action_space = Discrete(3)                                      # app/env.py:181
        self.observation_space = Dict({                                      # app/env.py:65-94
            "prices": Box([float("-inf")] * WINDOW_SIZE, [float("inf")] * WINDOW_SIZE, (WINDOW_SIZE,)),
            "returns": Box([float("-inf")] * WINDOW_SIZE, [float("inf")] * WINDOW_SIZE, (WINDOW_SIZE,)),
            "position": Box([-1.0], [1.0], (1,)),
            "equity_norm": Box([float("-inf")], [float("inf")], (1,)),
            "unrealized_pnl_norm": Box([float("-inf")], [float("inf")], (1,)),
            "steps_remaining_norm": Box([0.0], [1.0], (1,)),
        })
        self._rng = random.Random()                                          # placeholder
        self._prices = []
        self._bar_index = 0
        self._position = 0
        self._entry_price = 0.0
        self._equity = INITIAL_CASH
        self._previous_equity = INITIAL_CASH
        self._terminated = False
        self._truncated = False
        self._started = False
        self._closed = False

    # -- Gymnasium API (app/env.py:311-340 and :342-413) -------------------------------
    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))                             # placeholder
        self._prices = self._make_prices()
        self._bar_index = 0
        self._position = 0
        self._entry_price = float(self._prices[0])
        self._equity = INITIAL_CASH
        self._previous_equity = INITIAL_CASH
        self._terminated = False
        self._truncated = False
        self._started = True
        # GymFxEnv.reset accepts options and does not read them (app/env.py:311-340).
        return self._observation(), self._info(coerced_action=None)

    def step(self, action):
        if not self._started:
            raise RuntimeError("Call reset() before step().")                 # app/env.py:343-344
        if action not in ACTION_NAMES:
            raise AssertionError(f"action {action!r} is outside Discrete(3)")
        if self._terminated:
            return self._observation(), 0.0, True, False, self._info(coerced_action=action)

        self._previous_equity = self._equity
        if action != 0:
            new_position = 1 if action == 1 else -1
            if new_position != self._position:
                self._entry_price = float(self._prices[self._bar_index])
            self._position = new_position
        self._bar_index += 1
        price = float(self._prices[min(self._bar_index, len(self._prices) - 1)])
        self._equity = INITIAL_CASH + self._position * (price - self._entry_price) * POSITION_SIZE
        reward = (self._equity - self._previous_equity) / INITIAL_CASH     # placeholder reward scale
        self._terminated = self._bar_index >= TOTAL_BARS - 1
        self._truncated = False
        return self._observation(), reward, self._terminated, self._truncated, self._info(coerced_action=action)

    def close(self):
        self._started = False
        self._closed = True

    # -- internals ---------------------------------------------------------------
    def _make_prices(self):
        prices = [START_PRICE]
        for _ in range(TOTAL_BARS - 1):
            price = prices[-1] * (1.0 + self._rng.gauss(0.0, STEP_SIGMA))
            prices.append(max(PRICE_FLOOR, price))
        return prices

    def _observation(self):
        step = self._bar_index
        window = _window(self._prices, step)
        price = float(self._prices[min(step, len(self._prices) - 1)])
        unrealized = self._position * (price - window[-1]) * POSITION_SIZE
        return {
            "prices": window,
            "returns": _returns(window),
            "position": [float(self._position)],
            "equity_norm": [(self._equity - INITIAL_CASH) / INITIAL_CASH],
            "unrealized_pnl_norm": [unrealized / INITIAL_CASH],
            "steps_remaining_norm": [max(0, TOTAL_BARS - step) / TOTAL_BARS],
        }

    def _info(self, *, coerced_action):
        return {
            "equity": self._equity,
            "position": self._position,
            "price": float(self._prices[min(self._bar_index, len(self._prices) - 1)]),
            "bar_index": self._bar_index,
            "total_bars": TOTAL_BARS,
            "coerced_action": coerced_action,
        }

"""Fake backend of the Gymnasium driver: a pure Python stand-in for ``gymnasium.make("CartPole-v1")``.

Why a fake: the acceptance gate runs without gymnasium (the upstream package needs Python 3.11 or newer and numpy,
pyproject.toml:11 and :27), and package code never imports the clone.  This module re-implements the equations of
``gymnasium.envs.classic_control.cartpole:CartPoleEnv`` (the class the driver names as ``native``) and the step limit
that ``gymnasium.make`` adds to CartPole-v1 (a ``TimeLimit`` of 500 steps).  Every constant and rule below cites the
line of the clone at the pinned commit (d77197c284406e6094c9d1a74d4988a8749ce849).  The public members are the ones
CartPoleEnv has (``reset``, ``step``, ``close``; gate G7), and the two space classes duck-type
``gymnasium.spaces.Discrete`` and ``Box`` (the bridge reads ``n``, ``start``, ``low``, ``high``, ``shape``).

What this is not: the upstream environment.  Differences, all listed in the fidelity ``gaps`` of the driver:

* the initial state comes from Python's ``random.Random(seed)``, upstream draws it from numpy's generator, so a seed
  does not give the same trajectory on both;
* states and observations are Python floats; upstream returns a float32 observation array;
* there is no rendering, no ``PassiveEnvChecker`` and no ``OrderEnforcing`` wrapper.

Nothing here talks to a device.
"""

import math
import random

# gymnasium/envs/classic_control/cartpole.py:125-133 (CartPoleEnv.__init__)
GRAVITY = 9.8
MASSCART = 1.0
MASSPOLE = 0.1
TOTAL_MASS = MASSPOLE + MASSCART
LENGTH = 0.5                                    # "actually half the pole's length" (cartpole.py:129)
POLEMASS_LENGTH = MASSPOLE * LENGTH
FORCE_MAG = 10.0
TAU = 0.02                                      # seconds between state updates (cartpole.py:132)
# cartpole.py:136-137
THETA_THRESHOLD_RADIANS = 12 * 2 * math.pi / 360
X_THRESHOLD = 2.4
# gymnasium/envs/__init__.py:30 (max_episode_steps of CartPole-v1, applied by the TimeLimit wrapper that make() adds)
MAX_EPISODE_STEPS = 500
# cartpole.py:238-241: the default bounds of the uniform initial state
RESET_LOW, RESET_HIGH = -0.05, 0.05


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
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


def _reset_bounds(options):
    """``utils.maybe_parse_reset_bounds(options, -0.05, 0.05)`` (gymnasium/envs/classic_control/utils.py:17-46)."""
    if options is None:
        return RESET_LOW, RESET_HIGH
    low = options.get("low") if "low" in options else RESET_LOW
    high = options.get("high") if "high" in options else RESET_HIGH
    try:
        low, high = float(low), float(high)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"An option ({low}, {high}) could not be converted to a float.") from exc
    if low > high:
        raise ValueError(f"Lower bound ({low}) must be lower than higher bound ({high}).")
    return low, high


class FakeCartPoleEnv:
    """CartPole-v1 without numpy: ``reset(seed, options)`` and ``step(action)`` return what gymnasium's do."""

    def __init__(self, sutton_barto_reward=False, render_mode=None):
        if render_mode is not None:
            raise ValueError("the fake CartPole cannot render; use render_mode=None")
        self._sutton_barto_reward = sutton_barto_reward                     # cartpole.py:123
        # cartpole.py:139-152: the failing observation is still inside the bounds (twice the thresholds)
        high = [X_THRESHOLD * 2, math.inf, THETA_THRESHOLD_RADIANS * 2, math.inf]
        self.action_space = Discrete(2)                                     # cartpole.py:151
        self.observation_space = Box([-value for value in high], high)      # cartpole.py:152
        self._state = None
        self._steps_beyond_terminated = None
        self._elapsed_steps = 0
        self._rng = random.Random()

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(seed)
        low, high = _reset_bounds(options)
        self._state = [self._rng.uniform(low, high) for _ in range(4)]      # cartpole.py:243
        self._steps_beyond_terminated = None                                # cartpole.py:244
        self._elapsed_steps = 0                                             # gymnasium/wrappers/common.py:150
        return list(self._state), {}

    def step(self, action):
        if not self.action_space.contains(action):                          # cartpole.py:166-168
            raise AssertionError(f"{action!r} ({type(action)}) invalid")
        if self._state is None:                                             # cartpole.py:169
            raise AssertionError("Call reset before using step method.")
        x, x_dot, theta, theta_dot = self._state
        force = FORCE_MAG if action == 1 else -FORCE_MAG                    # cartpole.py:171
        costheta = math.cos(theta)
        sintheta = math.sin(theta)
        # cartpole.py:177-184
        temp = (force + POLEMASS_LENGTH * theta_dot * theta_dot * sintheta) / TOTAL_MASS
        thetaacc = (GRAVITY * sintheta - costheta * temp) / (
            LENGTH * (4.0 / 3.0 - MASSPOLE * costheta * costheta / TOTAL_MASS))
        xacc = temp - POLEMASS_LENGTH * thetaacc * costheta / TOTAL_MASS
        # cartpole.py:186-190 (the "euler" integrator, the default)
        x = x + TAU * x_dot
        x_dot = x_dot + TAU * xacc
        theta = theta + TAU * theta_dot
        theta_dot = theta_dot + TAU * thetaacc
        self._state = [x, x_dot, theta, theta_dot]
        # cartpole.py:199-204
        terminated = bool(x < -X_THRESHOLD or x > X_THRESHOLD
                          or theta < -THETA_THRESHOLD_RADIANS or theta > THETA_THRESHOLD_RADIANS)
        # cartpole.py:206-221
        if not terminated:
            reward = 0.0 if self._sutton_barto_reward else 1.0
        elif self._steps_beyond_terminated is None:
            self._steps_beyond_terminated = 0                               # the pole just fell
            reward = -1.0 if self._sutton_barto_reward else 1.0
        else:
            self._steps_beyond_terminated += 1
            reward = -1.0 if self._sutton_barto_reward else 0.0
        # gymnasium/wrappers/common.py:130-134: the TimeLimit that make() wraps CartPole-v1 in
        self._elapsed_steps += 1
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS
        return list(self._state), reward, terminated, truncated, {}

    def close(self):
        self._state = None

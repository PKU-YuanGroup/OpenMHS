"""Pure Python fake backend for the robust-gymnasium CartPole driver.

The gate host has no robust_gymnasium or gymnasium installation, and package code never imports the read-only
clone, so this module re-implements the equations of ``robust_gymnasium.envs.classic_control.cartpole:CartPoleEnv``
and the 500-step time limit that ``make("CartPole-v1")`` adds.  The public surface is the upstream environment's
(``reset``, ``step`` and ``close``; gate G7); the two space objects duck-type the Gymnasium ``Discrete`` and ``Box``
members the bridge reads (``n``, ``start``, ``low``, ``high``, ``shape``, ``dtype``, ``contains``).

This is not the upstream environment.  The initial state is drawn from Python's ``random.Random`` while upstream uses
numpy's generator, and the returned state is a list of Python floats while upstream returns a float32 numpy array.
There is no rendering and no ``PassiveEnvChecker`` or ``OrderEnforcing`` wrapper.

All numeric literals here are placeholder test data of the fake.  The comments point at the clone lines whose
equations the fake mirrors, but no number below is a Fact, a Limit or a reference.  Nothing here talks to a device.
"""

import math
import random

# placeholder: the equations of robust_gymnasium/envs/classic_control/cartpole.py:123-131
GRAVITY = 9.8
MASSCART = 1.0
MASSPOLE = 0.1
TOTAL_MASS = MASSPOLE + MASSCART
LENGTH = 0.5                                    # half the pole's length, cartpole.py:127
POLEMASS_LENGTH = MASSPOLE * LENGTH
FORCE_MAG = 10.0
TAU = 0.02                                      # seconds between state updates, cartpole.py:130
# placeholder: the failure thresholds of cartpole.py:134-135
THETA_THRESHOLD_RADIANS = 12 * 2 * math.pi / 360
X_THRESHOLD = 2.4
# placeholder: max_episode_steps=500 of CartPole-v1, robust_gymnasium/envs/__init__.py:27-33
MAX_EPISODE_STEPS = 500
# placeholder: the default reset bounds of cartpole.py:243-246
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
    """The low/high used by ``reset``; mirrors the helper cartpole.py:243-246 calls.

    cartpole.py imports that helper from the installed gymnasium package (cartpole.py:13); the clone carries an
    identical copy at robust_gymnasium/envs/classic_control/utils.py:32-46.
    """
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
    """A numpy-free CartPole-v1 that follows ``CartPoleEnv`` plus the time limit of ``make``."""

    def __init__(self, sutton_barto_reward=False, render_mode=None):
        if render_mode is not None:
            raise ValueError("the fake CartPole cannot render; use render_mode=None")
        self._sutton_barto_reward = sutton_barto_reward                     # cartpole.py:118-121
        high = [X_THRESHOLD * 2, math.inf, THETA_THRESHOLD_RADIANS * 2, math.inf]   # cartpole.py:139-147
        self.action_space = Discrete(2)                                     # cartpole.py:149
        self.observation_space = Box([-value for value in high], high)      # cartpole.py:150
        self.render_mode = render_mode
        self.state = None                                                   # cartpole.py:159
        self.steps_beyond_terminated = None                                 # cartpole.py:161
        self._elapsed_steps = 0
        self._rng = random.Random()

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(seed)
        low, high = _reset_bounds(options)
        self.state = [self._rng.uniform(low, high) for _ in range(4)]       # cartpole.py:243-246
        self.steps_beyond_terminated = None                                 # cartpole.py:247
        self._elapsed_steps = 0
        return list(self.state), {}

    def step(self, action):
        if not self.action_space.contains(action):                          # cartpole.py:164-166
            raise AssertionError(f"{action!r} ({type(action)}) invalid")
        if self.state is None:                                              # cartpole.py:167
            raise AssertionError("Call reset before using step method.")
        x, x_dot, theta, theta_dot = self.state
        force = FORCE_MAG if action == 1 else -FORCE_MAG                    # cartpole.py:169
        costheta = math.cos(theta)
        sintheta = math.sin(theta)
        # cartpole.py:175-181
        temp = (force + POLEMASS_LENGTH * theta_dot * theta_dot * sintheta) / TOTAL_MASS
        thetaacc = (GRAVITY * sintheta - costheta * temp) / (
            LENGTH * (4.0 / 3.0 - MASSPOLE * costheta * costheta / TOTAL_MASS))
        xacc = temp - POLEMASS_LENGTH * thetaacc * costheta / TOTAL_MASS
        # cartpole.py:183-187: the default "euler" integrator
        x = x + TAU * x_dot
        x_dot = x_dot + TAU * xacc
        theta = theta + TAU * theta_dot
        theta_dot = theta_dot + TAU * thetaacc
        self.state = [x, x_dot, theta, theta_dot]                           # cartpole.py:194
        terminated = bool(x < -X_THRESHOLD or x > X_THRESHOLD
                          or theta < -THETA_THRESHOLD_RADIANS or theta > THETA_THRESHOLD_RADIANS)   # :196-201
        # cartpole.py:203-227
        if not terminated:
            reward = 0.0 if self._sutton_barto_reward else 1.0
        elif self.steps_beyond_terminated is None:
            self.steps_beyond_terminated = 0
            reward = -1.0 if self._sutton_barto_reward else 1.0
        else:
            self.steps_beyond_terminated += 1
            reward = -1.0 if self._sutton_barto_reward else 0.0
        # The time limit that make("CartPole-v1") adds; step itself always reports truncated=False (cartpole.py:231-232).
        self._elapsed_steps += 1
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS
        return list(self.state), reward, terminated, truncated, {}

    def close(self):
        self.state = None

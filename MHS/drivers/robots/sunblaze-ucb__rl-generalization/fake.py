"""Fake backend of the SunblazeCartPole driver: a pure Python stand-in for the deterministic CartPole environment.

Why a fake: the acceptance gate runs without the upstream package (``setup.py:42-51`` pins gym==0.10.8r1, Box2D and
numpy==1.14.2, none of which is installed), and package code never imports the clone.  This module re-implements the
parts of ``sunblaze_envs.classic_control:ModifiableCartPoleEnv`` that the Gymnasium bridge touches: the action and
observation spaces of Gym's CartPoleEnv, ``reset`` (``classic_control.py:52-56``) and ``step``
(``classic_control.py:62-65``), plus the 200-step TimeLimit that the package registry adds
(``registration.py:126-131``, ``time_limit.py:4-10``).

What is sourced from the clone: the parent defaults recorded in the commented block of
``classic_control.py:340-347`` (gravity, masscart, masspole, length, force_mag, tau) and the documented deterministic
CartPole parameters at ``sunblaze_envs/README.md:22-24``.  The clone states no failure thresholds for the
deterministic class, and the base class calls Gym's ``reset`` (``classic_control.py:52-56``); the randomized variants
show the initial-state spread used below (-0.05 to 0.05, ``classic_control.py:296-299``), but the base class's draw is
Gym's ``gym.envs.classic_control.cartpole`` (imported at ``classic_control.py:3``).  Every number below marked
``# placeholder`` is test data of this fake and is never cited as a Fact or a Limit.

What this is not: the upstream environment.  The fake uses Python's ``random.Random(seed)`` where Gym uses numpy's
generator, returns Python floats where Gym returns a float32 array, has no rendering and no ``PassiveEnvChecker``.
Those differences are listed in the ``fidelity`` gaps of ``driver.py``.  Nothing here talks to a device.
"""

import math
import random

# classic_control.py:340-347 (the commented parent Gym defaults)
GRAVITY = 9.8
MASSCART = 1.0
MASSPOLE = 0.1
TOTAL_MASS = MASSPOLE + MASSCART
LENGTH = 0.5                                     # "actually half the pole's length"
POLEMASS_LENGTH = MASSPOLE * LENGTH
FORCE_MAG = 10.0
TAU = 0.02                                       # seconds between state updates
# placeholder: the clone states no failure thresholds; these are test data of the fake
THETA_THRESHOLD_RADIANS = 12 * 2 * math.pi / 360
X_THRESHOLD = 2.4
# placeholder: the clone states no reset spread; this is test data of the fake
RESET_LOW, RESET_HIGH = -0.05, 0.05
# sunblaze_envs/__init__.py:10 (max_episode_steps=200 for SunblazeCartPole-v0)
MAX_EPISODE_STEPS = 200


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n):
        self.n = int(n)
        self.start = 0
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return (isinstance(value, int) and not isinstance(value, bool)
                and self.start <= value < self.start + self.n)


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeModifiableCartPoleEnv:
    """The deterministic CartPole of SunblazeCartPole-v0 without numpy or Gym.

    The public members are the ones the bridge calls on the upstream class (``reset`` and ``step``; gate G7);
    ``action_space`` and ``observation_space`` are instance data, as they are on Gym's CartPoleEnv.
    """

    def __init__(self, **_options):
        # placeholder: the observation bounds are Gym's and are not stated by the clone
        high = [X_THRESHOLD * 2, math.inf, THETA_THRESHOLD_RADIANS * 2, math.inf]
        self.action_space = Discrete(2)
        self.observation_space = Box([-value for value in high], high)
        self._state = None
        self._steps_beyond_terminated = None
        self._elapsed_steps = 0
        self._rng = random.Random()

    def reset(self, *, seed=None, options=None):
        """Draw the four state values like Gym's CartPoleEnv.reset (classic_control.py:52-56 calls it)."""
        if seed is not None:
            self._rng = random.Random(seed)                 # placeholder: the seed stream is the fake's, not Gym's
        self._state = [self._rng.uniform(RESET_LOW, RESET_HIGH) for _ in range(4)]  # placeholder spread
        self._steps_beyond_terminated = None
        self._elapsed_steps = 0
        #: ``options`` is accepted for the bridge and ignored: the upstream reset takes ``new``, not reset options.
        return list(self._state), {}

    def step(self, action):
        """Advance one ``tau``; return the legacy Gym 4-tuple ``(observation, reward, done, info)``."""
        if not self.action_space.contains(action):
            raise AssertionError(f"{action!r} ({type(action)}) invalid")
        if self._state is None:
            raise AssertionError("Call reset before using step method.")
        x, x_dot, theta, theta_dot = self._state
        force = FORCE_MAG if action == 1 else -FORCE_MAG      # classic_control.py:346, the deterministic D force
        costheta = math.cos(theta)
        sintheta = math.sin(theta)
        temp = (force + POLEMASS_LENGTH * theta_dot * theta_dot * sintheta) / TOTAL_MASS
        thetaacc = (GRAVITY * sintheta - costheta * temp) / (
            LENGTH * (4.0 / 3.0 - MASSPOLE * costheta * costheta / TOTAL_MASS))
        xacc = temp - POLEMASS_LENGTH * thetaacc * costheta / TOTAL_MASS
        x = x + TAU * x_dot
        x_dot = x_dot + TAU * xacc
        theta = theta + TAU * theta_dot
        theta_dot = theta_dot + TAU * thetaacc
        self._state = [x, x_dot, theta, theta_dot]
        terminated = bool(x < -X_THRESHOLD or x > X_THRESHOLD
                          or theta < -THETA_THRESHOLD_RADIANS or theta > THETA_THRESHOLD_RADIANS)  # placeholder
        if not terminated:
            reward = 1.0
        elif self._steps_beyond_terminated is None:
            self._steps_beyond_terminated = 0
            reward = 1.0
        else:
            self._steps_beyond_terminated += 1
            reward = 0.0
        self._elapsed_steps += 1
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS
        # the legacy Gym API reports the time limit through the same done flag as a terminal state
        return list(self._state), reward, bool(terminated or truncated), {}

"""Fake backend of the Roboschool driver: a pure Python stand-in for the InvertedPendulum scene.

Why a fake: the gate runs without ``gym``, ``numpy`` or the compiled Bullet scene, and package code never imports
the clone.  This module implements the public surface of ``roboschool:RoboschoolInvertedPendulum`` that the
Gymnasium bridge uses -- ``reset``, ``step`` and ``seed`` -- plus the two space objects the bridge reads
(``action_space`` and ``observation_space``).  The numbers below are test data for a stable stand-in, not limits,
facts or the upstream model: each is marked ``# placeholder``.  The upstream interface and rules are cited in
``driver.py`` and ``facts.md`` at commit d32bcb2b35b94168b5ce27233ca62f3c8678886f.

What this is not: the Bullet/MuJoCo scene.  There is no cart rail, no contact solver, no camera and no HUD; the
masses, inertia, damping and motor model are chosen to keep the fake deterministic and cheap, so trajectories differ
from the upstream environment.  The driver's fidelity ``gaps`` say all of this.  Nothing here talks to a device.
"""

import math
import random


class Box:
    """Duck-typed gym Box: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeInvertedPendulum:
    """The InvertedPendulum interface without gym, numpy or Bullet."""

    # placeholder: test data for the stand-in clock; the upstream scene states timestep 0.0165 at
    # roboschool/gym_pendulums.py:81
    TAU = 0.0165
    # placeholder: test data of the stand-in dynamics
    GRAVITY_TERM = 4.0
    ACTION_TERM = 0.5
    CART_TERM = 0.5
    DAMPING = 0.1
    # placeholder: the upstream termination threshold is 0.2 rad at roboschool/gym_pendulums.py:114
    TERMINATION_ANGLE = 0.2
    # placeholder: the registered episode limit, 1000 at roboschool/__init__.py:14
    MAX_EPISODE_STEPS = 1000

    def __init__(self, **_options):
        self.action_space = Box([-1.0], [1.0])                       # placeholder bounds
        self.observation_space = Box([-math.inf] * 5, [math.inf] * 5)  # placeholder dimension
        self._rng = random.Random()
        self._state = None
        self._elapsed_steps = 0
        self._terminated = False
        self._truncated = False

    def seed(self, seed=None):
        """Seed the generator used by the next reset; the upstream method returns ``[seed]``."""
        self._rng = random.Random(seed)
        return [seed]

    def reset(self, *, seed=None, options=None):
        """Start an episode and return the initial observation, as the legacy upstream reset does.

        ``options`` is accepted for the family bridge but not used: the upstream reset takes no options.  The pole
        angle draw and the zero start are placeholder test data; upstream draws the angle uniformly from -0.1 to
        0.1 (``roboschool/gym_pendulums.py:87-88``).
        """
        if seed is not None:
            self._rng = random.Random(seed)
        theta = self._rng.uniform(-0.1, 0.1)                          # placeholder start draw
        self._state = [0.0, 0.0, theta, 0.0]                          # placeholder start position and speeds
        self._elapsed_steps = 0
        self._terminated = False
        self._truncated = False
        return self._observation()

    def _observation(self):
        """The five values upstream calc_state returns: x, vx, cos(theta), sin(theta), theta_dot."""
        x, x_dot, theta, theta_dot = self._state
        return [x, x_dot, math.cos(theta), math.sin(theta), theta_dot]  # placeholder values, upstream shape

    def step(self, action):
        """Advance the stand-in by one placeholder timestep.

        The return shape is the five-tuple of the Gymnasium bridge; the bare upstream class returns the legacy
        four-tuple (``roboschool/gym_pendulums.py:120``) and the registered TimeLimit is added by ``gym.make``.
        """
        if self._state is None:
            raise AssertionError("Call reset before using step method.")
        if self._terminated or self._truncated:
            raise AssertionError("the episode has ended; reset before the next step")
        value = float(action[0])
        if not math.isfinite(value):
            raise ValueError("the action must be finite")
        value = max(-1.0, min(1.0, value))                            # placeholder clip, as upstream line 93
        x, x_dot, theta, theta_dot = self._state
        # placeholder stand-in dynamics; not the upstream Bullet model
        theta_ddot = (self.GRAVITY_TERM * math.sin(theta)
                      - self.ACTION_TERM * value * math.cos(theta)
                      - self.DAMPING * theta_dot)
        cart_accel = self.CART_TERM * value
        theta_dot = theta_dot + self.TAU * theta_ddot
        theta = theta + self.TAU * theta_dot
        x_dot = x_dot + self.TAU * cart_accel
        x = x + self.TAU * x_dot
        self._state = [x, x_dot, theta, theta_dot]
        self._elapsed_steps += 1
        self._terminated = abs(theta) > self.TERMINATION_ANGLE       # placeholder threshold
        self._truncated = self._elapsed_steps >= self.MAX_EPISODE_STEPS
        reward = 1.0                                                  # placeholder reward
        return self._observation(), reward, self._terminated, self._truncated, {}

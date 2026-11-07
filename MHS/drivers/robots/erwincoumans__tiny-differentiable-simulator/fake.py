"""Fake backend of the tiny-differentiable-simulator driver: a pure Python stand-in for CartpolePyTinyDiffSim.

Why a fake: the acceptance gate runs without the compiled ``pytinydiffsim`` extension and the legacy ``gym`` package,
and package code never imports the clone.  This module needs no numpy either.  It re-implements the environment behind
``tds_environments.cartpole_tds_env:CartpolePyTinyDiffSim`` at the pinned commit
8381b8c9ad7f0a959548e4982eb8a63431a842d2: its action and observation spaces (cartpole_tds_env.py:19-37), the legacy
``reset()`` / ``step(action)`` / ``seed(seed)`` API (cartpole_tds_env.py:49-79) and the state order and thresholds of
the compiled ``pytinydiffsim.CartpoleEnv`` (examples/environments/cartpole_environment2.h:182-219, :221-307).

Gate G7: the public members defined here are the ones ``CartpolePyTinyDiffSim`` has (``reset``, ``step``, ``seed``,
``close``); the space object is this module's private duck type, not a member of the environment.

What this is not: the TDS engine.  The fake integrates a standard analytic cart-pole with the URDF masses and the
1/60 s timestep of the clone; it does not run TDS forward dynamics, the URDF multibody or the contact simulation, and
it was never compared with the upstream engine.  The fidelity ``gaps`` of driver.py say so.  Every number below is
either a constant of the clone (with its line) or a placeholder, marked ``# placeholder``.
"""

import math
import random

# examples/environments/cartpole_environment2.h:27
DT = 1.0 / 60.0
# examples/environments/cartpole_environment2.h:37
GRAVITY = 10.0
# examples/environments/cartpole_urdf.h:41 (cart mass) and :64 (pole mass)
CART_MASS = 1.0
POLE_MASS = 0.1
# examples/environments/cartpole_urdf.h:55-63 (a 1.0 m pole with its inertial origin at 0.5 m)
POLE_HALF_LENGTH = 0.5
# python/tds_environments/cartpole_tds_env.py:30
FORCE_MAG = 10.0
# python/tds_environments/cartpole_tds_env.py:19-20
THETA_THRESHOLD_RADIANS = 12 * 2 * math.pi / 360
X_THRESHOLD = 0.4
# python/tds_environments/cartpole_tds_env.py:23,25 (numpy.finfo(numpy.float32).max) and :72 (the wrapper's reward)
FLOAT32_MAX = 3.4028234663852886e38
REWARD = 1.0
# examples/environments/cartpole_environment2.h:187 (0.05 * ((rand / RAND_MAX) - 0.5) * 2.0)
RESET_LOW, RESET_HIGH = -0.05, 0.05


class _Box:
    """Duck-typed ``gym.spaces.Box``: ``low``, ``high``, ``shape`` and ``dtype`` (what the bridge reads)."""

    def __init__(self, low, high, shape=(), dtype="float32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = dtype

    def contains(self, value):
        if len(value) != len(self.low):
            return False
        return all(self.low[index] <= value[index] <= self.high[index] for index in range(len(value)))


class FakeCartpolePyTinyDiffSim:
    """``CartpolePyTinyDiffSim`` without gym, numpy or the compiled extension."""

    def __init__(self):
        # python/tds_environments/cartpole_tds_env.py:19-28
        self.theta_threshold_radians = THETA_THRESHOLD_RADIANS
        self.x_threshold = X_THRESHOLD
        high = [self.x_threshold * 2, FLOAT32_MAX,
                self.theta_threshold_radians * 2, FLOAT32_MAX]
        # python/tds_environments/cartpole_tds_env.py:30-35
        self.force_mag = FORCE_MAG
        self.action_space = _Box([-self.force_mag], [self.force_mag], (1,))
        # python/tds_environments/cartpole_tds_env.py:37
        self.observation_space = _Box([-value for value in high], high, (4,))
        self._rng = random.Random()
        self.state = None
        # python/tds_environments/cartpole_tds_env.py:39 (the wrapper seeds itself in the constructor)
        self.seed()

    def seed(self, seed=None):
        """``cartpole_tds_env.py:49-55`` and ``cartpole_environment2.h:216-219``: seed the wrapped RNG."""
        if seed is None:
            seed = random.SystemRandom().randrange(1 << 32)   # placeholder: entropy when no seed is supplied
        original = int(seed)
        self._rng = random.Random(original & 0xffffffff)
        return [original]

    def reset(self):
        """``cartpole_tds_env.py:75-79``: draw the four state values and return them as the observation."""
        # examples/environments/cartpole_environment2.h:182-192: each value is uniform in [-0.05, 0.05]
        self.state = [self._rng.uniform(RESET_LOW, RESET_HIGH) for _ in range(4)]
        return list(self.state)

    def step(self, action):
        """``cartpole_tds_env.py:65-73``: one force value in, ``[x, theta, x_dot, theta_dot]`` out."""
        if self.state is None:
            raise AssertionError("reset() must be called before step()")
        force = float(action[0])
        # examples/environments/cartpole_environment2.h:285-291: the C++ step clips to the constructor bounds
        force = max(-self.force_mag, min(self.force_mag, force))
        x, theta, x_dot, theta_dot = self.state
        costheta = math.cos(theta)
        sintheta = math.sin(theta)
        total_mass = CART_MASS + POLE_MASS
        # placeholder: the standard analytic cart-pole equations, not the TDS URDF forward dynamics
        temp = (force + POLE_MASS * POLE_HALF_LENGTH * theta_dot * theta_dot * sintheta) / total_mass
        thetaacc = (GRAVITY * sintheta - costheta * temp) / (
            POLE_HALF_LENGTH * (4.0 / 3.0 - POLE_MASS * costheta * costheta / total_mass))
        xacc = temp - POLE_MASS * POLE_HALF_LENGTH * thetaacc * costheta / total_mass
        # placeholder: Euler integration with the clone's 1/60 s timestep (cartpole_environment2.h:27)
        x = x + DT * x_dot
        x_dot = x_dot + DT * xacc
        theta = theta + DT * theta_dot
        theta_dot = theta_dot + DT * thetaacc
        self.state = [x, theta, x_dot, theta_dot]
        # examples/environments/cartpole_environment2.h:298-307: reward 1 and done at the position and angle thresholds
        done = bool(x < -X_THRESHOLD or x > X_THRESHOLD
                    or theta < -THETA_THRESHOLD_RADIANS or theta > THETA_THRESHOLD_RADIANS)
        return list(self.state), REWARD, done, {}

    def close(self):
        """``cartpole_tds_env.py:144-145``: the wrapper deletes its wrapped environment."""
        self.state = None

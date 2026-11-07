"""Fake backend of the gym-dart driver: a pure-Python stand-in for ``gym_dart.envs:DartCartPoleEnv``.

Why a fake: the gate must not import or run the clone, and the upstream environment needs ``dartpy`` and its
``cartpole.skel`` world (``gym_dart/envs/dart_env.py:24-34``), which is not installed here.  This module
re-implements the parts of ``gym_dart/envs/dart_cartpole_env.py`` the contract needs: the two spaces, the reset
draw, the action as a cart velocity, the reward, the done conditions and the registration's 200-step limit.

What this is not: DART.  The dynamics below are a placeholder damped pendulum plus a cart moved by the action;
there is no cart-pole inertia coupling, contact, friction, actuator or sensor model, and the trajectories were
never compared with the upstream environment.  The driver's fidelity ``gaps`` say so.

The upstream class returns the legacy 3-tuple from ``step()`` and its ``reset()`` takes no seed
(``gym_dart/envs/dart_cartpole_env.py:70-80``); the gymnasium bridge requires the 5-tuple and passes ``seed=``, so
this fake returns ``(observation, reward, terminated, truncated, info)`` and accepts ``reset(seed, options)``.
Only ``reset`` and ``step`` are public (gate G7); every constant cites the clone line it mirrors.
"""

import math
import random

# gym_dart/envs/dart_cartpole_env.py:35-36
GRAVITY = 9.8
TIMESTEP_S = 0.01
# gym_dart/envs/assets/cartpole.skel:64 (the pole's inertia offset) and :96-115 (joint damping)
POLE_HALF_LENGTH = 0.3
JOINT_DAMPING = 1.0
# gym_dart/envs/dart_cartpole_env.py:13, :14, :43
THETA_THRESHOLD_RADIANS = 12 * 2 * math.pi / 360
X_THRESHOLD = 2.4
THETA_REWARD_THRESHOLD = 0.1
# gym_dart/envs/dart_cartpole_env.py:49-50
INITIAL_STATE_LIMIT = 0.1
# gym_dart/envs/dart_cartpole_env.py:40, :182
MAX_TIME_STEPS = 10000
CART_LIMIT = 1.0
# gym_dart/__init__.py:12 (max_episode_steps, applied by the TimeLimit wrapper of gymnasium.make)
MAX_EPISODE_STEPS = 200
# gym_dart/envs/dart_cartpole_env.py:21, :25 (np.finfo(np.float32).max)
FLOAT32_MAX = 3.4028234663852886e38
# gym_dart/envs/dart_cartpole_env.py:60
ACTION_LIMIT = 5.0


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeDartCartPoleEnv:
    """A gymnasium-shaped stand-in for ``DartCartPoleEnv``: only ``reset`` and ``step`` are public."""

    def __init__(self, **_options):
        # gym_dart/envs/dart_cartpole_env.py:18-30 (the observation bounds) and :62-66 (the action space)
        high = [X_THRESHOLD * 2, FLOAT32_MAX, THETA_THRESHOLD_RADIANS * 2, FLOAT32_MAX]
        self.observation_space = Box([-value for value in high], high)
        self.action_space = Box([-ACTION_LIMIT], [ACTION_LIMIT])
        self._rng = random.Random()
        self._state = None
        self._step = 0

    def reset(self, *, seed=None, options=None):
        """``DartCartPoleEnv.reset`` plus the seed the bridge passes (the upstream reset has neither seed nor options)."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        # gym_dart/envs/dart_cartpole_env.py:133-139: four values uniform in the initial state limits, in the
        # order [pole angle, pole angular velocity, cart position, cart velocity]
        self._state = [self._rng.uniform(-INITIAL_STATE_LIMIT, INITIAL_STATE_LIMIT) for _ in range(4)]
        self._step = 0
        return list(self._state), {}

    def step(self, action):
        """One transition: the action is the cart velocity, as in ``DartCartPoleEnv._simulation_step`` (line 163)."""
        if self._state is None:
            raise RuntimeError("reset() must be called before step()")
        values = action.tolist() if hasattr(action, "tolist") else action
        velocity = float(values[0] if isinstance(values, (list, tuple)) else values)
        velocity = min(max(velocity, -ACTION_LIMIT), ACTION_LIMIT)   # dart_cartpole_env.py:162
        reward = self._reward(self._state)                           # dart_cartpole_env.py:166 (reward before world.step)
        self._state = self._advance(self._state, velocity)
        self._step += 1
        theta, theta_dot, x, x_dot = self._state
        terminated = (abs(theta) > THETA_THRESHOLD_RADIANS or abs(x) > CART_LIMIT
                      or self._step >= MAX_TIME_STEPS)               # dart_cartpole_env.py:180-186
        truncated = self._step >= MAX_EPISODE_STEPS                  # gym_dart/__init__.py:12
        return list(self._state), reward, terminated, truncated, {}

    def _reward(self, state):
        # gym_dart/envs/dart_cartpole_env.py:144-156
        theta, _theta_dot, x, _x_dot = state
        if abs(theta) < THETA_REWARD_THRESHOLD:
            return (THETA_REWARD_THRESHOLD - abs(theta)) / THETA_REWARD_THRESHOLD + math.exp(-x)
        return 0.0

    def _advance(self, state, velocity):
        # placeholder model: a damped pendulum driven by gravity and a cart moved at the commanded velocity.
        theta, theta_dot, x, _x_dot = state
        theta_dot += TIMESTEP_S * (-(GRAVITY / POLE_HALF_LENGTH) * math.sin(theta) - JOINT_DAMPING * theta_dot)
        theta += TIMESTEP_S * theta_dot
        x += TIMESTEP_S * velocity
        return [theta, theta_dot, x, velocity]

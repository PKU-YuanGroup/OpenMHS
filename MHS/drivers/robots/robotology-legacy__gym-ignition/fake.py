"""Fake backend: an analytic stand-in for the registered legacy Gym environment.

The upstream package registers ``CartPoleDiscreteBalancing-Gazebo-v0`` as a legacy OpenAI Gym environment
(``gym.envs.registration.register``) whose entry point is
``gym_ignition.runtimes.gazebo_runtime:GazeboRuntime``.  Opening it needs Ignition Gazebo, ScenARIO and the
``gym_ignition_models`` package, none of which the acceptance gate installs, and package code never imports the clone.
This module therefore serves a deterministic stand-in with the public gym.Env surface of ``GazeboRuntime`` that the
bridge calls: ``reset()``, ``step(action)``, ``seed(seed)`` and ``close()``.  Gate G7 checks those names against the
upstream class.

The public members mirror the upstream signatures: ``GazeboRuntime.reset`` takes no seed or options and returns the
observation, ``step`` takes an integer action and returns ``(observation, reward, done, info)`` (the legacy four-value
form), ``seed`` returns the list of seeds and ``close`` releases the environment.  The two space classes duck-type
``gym.spaces.Discrete`` and ``gym.spaces.Box``; the bridge reads ``n``, ``start``, ``low``, ``high``, ``shape``.

Every numeric constant and rule in this file is stand-in test data for the gate, not a fact, a limit or a device
bound: each is marked ``# placeholder``.  The facts and their upstream citations live in ``driver.py`` and
``facts.md``.  This fake does not model the physics of the upstream cartpole: it moves the cart and pole positions
directly and applies a fixed force to the cart, so the driver declares fidelity level F0 and lists the omission in
its ``gaps``.
"""

import math
import random

# Stand-in test data for the gate, never used as a Fact or a Limit.
ACTION_COUNT = 2                                    # placeholder: upstream action space Discrete(2)
X_THRESHOLD = 2.4                                   # placeholder
DX_THRESHOLD = 20.0                                 # placeholder
Q_THRESHOLD = math.radians(12.0)                    # placeholder
DQ_THRESHOLD = math.radians(3.0 * 360.0)            # placeholder
OBSERVATION_SCALE = 1.2                             # placeholder
FORCE_MAG = 20.0                                    # placeholder
TIMESTEP_S = 0.001                                  # placeholder
MAX_EPISODE_STEPS = 5000                            # placeholder
RESET_LOW = -0.05                                   # placeholder
RESET_HIGH = 0.05                                   # placeholder
REWARD_X = 0.10                                     # placeholder
REWARD_DX = 0.10                                    # placeholder
REWARD_RAIL = 10.0                                  # placeholder
RAIL_FRACTION = 0.9                                 # placeholder


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeCartPoleDiscrete:
    """Stand-in for ``gym.make("CartPoleDiscreteBalancing-Gazebo-v0")`` without Gazebo."""

    def __init__(self, **_options):
        high = [
            X_THRESHOLD * OBSERVATION_SCALE,
            DX_THRESHOLD * OBSERVATION_SCALE,
            Q_THRESHOLD * OBSERVATION_SCALE,
            DQ_THRESHOLD * OBSERVATION_SCALE,
        ]
        self.action_space = Discrete(ACTION_COUNT)
        self.observation_space = Box([-value for value in high], high)
        self._rng = random.Random(0)                # placeholder: default seed before the first seed() call
        self._state = None
        self._elapsed_steps = 0

    def seed(self, seed=None):
        """Seed the reset generator and return the list of seeds, like ``GazeboRuntime.seed``."""

        if seed is None:
            seed = self._rng.randrange(0, 2 ** 31)  # placeholder: fallback seed when none is given
        seed = int(seed)
        self._rng = random.Random(seed)
        return [seed]

    def reset(self):
        """Draw a new state uniformly and return it, like the legacy environment's ``reset``."""

        self._state = [self._rng.uniform(RESET_LOW, RESET_HIGH) for _ in range(4)]  # placeholder: reset draw
        self._elapsed_steps = 0
        return list(self._state)

    def step(self, action):
        """Apply one action and return the legacy ``(observation, reward, done, info)`` tuple."""

        if self._state is None:
            raise RuntimeError("Call reset before using step method")
        if action not in (0, 1):
            raise ValueError(f"action {action!r} is outside the discrete action space")
        x, dx, q, dq = self._state
        force = FORCE_MAG if action == 1 else -FORCE_MAG  # placeholder: action mapping of the stand-in model
        # Direct kinematic update: no rigid-body dynamics, contacts or inertia in this stand-in.
        x = x + dx * TIMESTEP_S
        dx = dx + force * TIMESTEP_S
        q = q + dq * TIMESTEP_S
        self._state = [x, dx, q, dq]
        self._elapsed_steps += 1
        done = not self._in_reset_box(self._state) or self._elapsed_steps >= MAX_EPISODE_STEPS
        reward = 0.0 if done else 1.0
        reward -= REWARD_X * abs(x)
        reward -= REWARD_DX * abs(dx)
        if x >= RAIL_FRACTION * X_THRESHOLD:
            reward -= REWARD_RAIL
        return list(self._state), float(reward), bool(done), {}

    def close(self):
        """Release the stand-in state, like ``GazeboRuntime.close``."""

        self._state = None

    @staticmethod
    def _in_reset_box(state):
        x, dx, q, dq = state
        return (abs(x) <= X_THRESHOLD and abs(dx) <= DX_THRESHOLD
                and abs(q) <= Q_THRESHOLD and abs(dq) <= DQ_THRESHOLD)

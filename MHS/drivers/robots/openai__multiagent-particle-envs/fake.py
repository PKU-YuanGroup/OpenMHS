"""Fake backend of the particle-world driver: a pure Python stand-in for the ``simple.py`` scenario.

Why a fake: the upstream environment imports the legacy ``gym`` and ``numpy`` (``multiagent/environment.py:1-5`` and
``setup.py:12``), neither of which is installed where the acceptance gate runs, and package code never imports the
clone.  This module re-implements the observable contract of ``multiagent.environment:MultiAgentEnv`` for the
single-agent ``multiagent/scenarios/simple.py`` world: one movable, non-colliding, silent agent and one immovable,
non-colliding landmark, the physics constants of ``multiagent/core.py``, and the discrete action mapping of
``multiagent/environment.py:164-167``.  The public members are the ones ``MultiAgentEnv`` has that this driver needs
(``reset`` and ``step``; gate G7), and the two space classes duck-type the ``gym.spaces`` objects the bridge reads
(``n``, ``start``, ``low``, ``high``, ``shape``).

What this is not: the upstream environment.  It serves only the simple scenario, applies the
``discrete_action_input=True`` branch to the declared ``Discrete(5)`` action space (the upstream default is False and
expects a 5-element vector), draws from Python's ``random.Random`` where upstream uses numpy's global generator, and
has no rendering.  All of that is listed in the driver's fidelity ``gaps``.  Every number below is placeholder test
data, not a fact and not a bound of a device.

Nothing here talks to a device.
"""

import math
import random

# Placeholder test data (the fake is not the device): the simple.py world constants, copied here only to make a
# deterministic stand-in world.  They are not facts, not limits, and the reference files do not derive from them.
DT = 0.1                         # placeholder: world.dt
DAMPING = 0.25                   # placeholder: world.damping
SENSITIVITY = 5.0                # placeholder: action sensitivity when agent.accel is None
MASS = 1.0                       # placeholder: agent initial_mass
RESET_LOW = -1.0                 # placeholder: reset position lower bound
RESET_HIGH = 1.0                 # placeholder: reset position upper bound
MAX_EPISODE_STEPS = 100          # placeholder: registration max_episode_steps
DIM_P = 2                        # placeholder: world.dim_p
NUM_ACTIONS = DIM_P * 2 + 1      # placeholder: Discrete(world.dim_p * 2 + 1)


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the integers ``start .. start + n - 1``."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
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


class FakeSimpleEnv:
    """The simple.py world without numpy: ``reset(seed, options)`` and ``step(action)``."""

    def __init__(self):
        self.action_space = Discrete(NUM_ACTIONS)
        self.observation_space = Box([-math.inf] * 4, [math.inf] * 4)  # placeholder: four observation values
        self._rng = random.Random()
        self._agent_pos = [0.0, 0.0]
        self._agent_vel = [0.0, 0.0]
        self._landmark_pos = [0.0, 0.0]
        self._tick = 0
        self._reset_state()

    def _reset_state(self):
        self._agent_pos = [self._rng.uniform(RESET_LOW, RESET_HIGH) for _ in range(DIM_P)]
        self._agent_vel = [0.0] * DIM_P
        self._landmark_pos = [self._rng.uniform(RESET_LOW, RESET_HIGH) for _ in range(DIM_P)]
        self._tick = 0

    def _observation(self):
        return [self._agent_vel[0], self._agent_vel[1],
                self._landmark_pos[0] - self._agent_pos[0],
                self._landmark_pos[1] - self._agent_pos[1]]

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(seed)
        # The upstream reset takes no options; the class schema is open, so an options object has no effect.
        self._reset_state()
        return self._observation(), {}

    def step(self, action):
        if not self.action_space.contains(action):
            raise AssertionError(f"{action!r} ({type(action)}) invalid")
        index = int(action)
        # environment.py:164-167: the discrete_action_input branch.
        force_x = -SENSITIVITY if index == 1 else SENSITIVITY if index == 2 else 0.0  # placeholder mapping
        force_y = -SENSITIVITY if index == 3 else SENSITIVITY if index == 4 else 0.0  # placeholder mapping
        # core.py:158-169: velocity damping, the applied force, then the position update.
        self._agent_vel[0] = self._agent_vel[0] * (1.0 - DAMPING) + (force_x / MASS) * DT
        self._agent_vel[1] = self._agent_vel[1] * (1.0 - DAMPING) + (force_y / MASS) * DT
        self._agent_pos[0] += self._agent_vel[0] * DT
        self._agent_pos[1] += self._agent_vel[1] * DT
        self._tick += 1
        delta_x = self._landmark_pos[0] - self._agent_pos[0]
        delta_y = self._landmark_pos[1] - self._agent_pos[1]
        reward = -(delta_x * delta_x + delta_y * delta_y)  # placeholder: simple.py reward
        terminated = False                                 # placeholder: no done callback
        truncated = self._tick >= MAX_EPISODE_STEPS        # placeholder: registration limit
        return self._observation(), reward, terminated, truncated, {"n": [{}]}

"""Fake backend of the Muller-Brown driver: a pure Python stand-in for the upstream discrete environment.

Why a fake: package code never imports the clone, and the acceptance gate runs without ``gym``/``gymnasium``.
This module re-implements the public surface of
``gym_muller_brown.envs.muller_brown_discrete:MullerBrownDiscreteEnv`` (the class the driver names as ``native``):
the grid, the analytic Muller-Brown energy, the five discrete moves and the reward rule, each with the line of the
clone it comes from.  The two space helpers only duck-type the parts the bridge reads (``n``, ``start``, ``nvec``,
``shape``, ``dtype``); the environment class defines only members the upstream class has (gate G7).

What this is not: the upstream environment.  Differences, also listed in the fidelity ``gaps`` of the driver:

* the start state is drawn from a seeded Python ``random.Random``; upstream draws it from an unseeded
  ``observation_space.sample()`` and never calls the imported ``gym.utils.seeding`` helper, so the upstream class
  has no seed control;
* coordinates and energies are Python floats, not numpy scalars;
* there is no rendering, no ``plotPES`` and no matplotlib; no snapshot/restore pair is exposed;
* the upstream ``energies`` cache built in ``__init__`` is not precomputed because the driver never plots.

Nothing here talks to a device.
"""

import math
import random

GRID = "gym_muller_brown/envs/muller_brown_discrete.py"
#: The registered grid size of MullerBrownDiscrete-v0 (gym_muller_brown/__init__.py:3-7); the fake's constructor
#: defaults to it so the bridge can build the environment without arguments.
DEFAULT_M, DEFAULT_N = 5, 5
#: The upstream extent [xmin, xmax, ymin, ymax] (muller_brown_discrete.py:14).
EXTENT = [-1.5, 1.0, -0.5, 2.0]
#: The five moves of muller_brown_discrete.py:19.
ACTION_DICT = {0: [0, 1], 1: [0, -1], 2: [-1, 0], 3: [1, 0], 4: [0, 0]}
#: The four terms of the Muller-Brown potential (muller_brown_discrete.py:75-80).
A = [-200, -100, -170, 15]
A_X = [-1, -1, -6.5, 0.7]
B = [0, 0, 11, 0.6]
C = [-10, -10, -6.5, 0.7]
X0 = [1, 0, -0.5, -1]
Y0 = [0, 0.5, 1.5, 1]


def _linspace(start, stop, count):
    """``numpy.linspace(start, stop, count)`` for the grid axes (muller_brown_discrete.py:15-16)."""
    count = int(count)
    if count <= 0:
        return []
    if count == 1:
        return [float(start)]
    step = (float(stop) - float(start)) / (count - 1)
    return [float(start) + index * step for index in range(count)]


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the integers ``start .. start + n - 1`` (muller_brown_discrete.py:18)."""

    def __init__(self, n, start=0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and self.start <= value < self.start + self.n


class MultiDiscrete:
    """Duck-typed ``gym.spaces.MultiDiscrete``: one integer per axis, sampled uniformly.

    The upstream observation space is ``spaces.MultiDiscrete([m, n])`` (muller_brown_discrete.py:17) and its
    ``sample()`` is the only source of randomness in ``reset()`` (muller_brown_discrete.py:118).
    """

    def __init__(self, nvec):
        self.nvec = [int(value) for value in nvec]
        self.shape = (len(self.nvec),)
        self.dtype = "int64"
        self._rng = random.Random()  # placeholder: RNG state, seeded only by reset(seed=...)

    def seed(self, seed):
        self._rng = random.Random(seed)

    def sample(self):
        return [self._rng.randrange(int(size)) for size in self.nvec]


class FakeMullerBrownDiscreteEnv:
    """The upstream grid world without numpy: ``reset(seed, options)`` and ``step(action)``."""

    def __init__(self, m=DEFAULT_M, n=DEFAULT_N):
        self.m = int(m)
        self.n = int(n)
        self.extent = list(EXTENT)                                  # muller_brown_discrete.py:14
        self.x_values = _linspace(self.extent[0], self.extent[1], self.m)   # muller_brown_discrete.py:15
        self.y_values = _linspace(self.extent[2], self.extent[3], self.n)   # muller_brown_discrete.py:16
        self.observation_space = MultiDiscrete([self.m, self.n])    # muller_brown_discrete.py:17
        self.action_space = Discrete(5)                             # muller_brown_discrete.py:18
        self.action_dict = {action: list(step) for action, step in ACTION_DICT.items()}  # muller_brown_discrete.py:19
        self.agent_position = None

    def reset(self, seed=None, options=None):
        """Upstream reset (muller_brown_discrete.py:117-120) plus the bridge's optional seed/options keywords.

        The upstream ``reset()`` takes no arguments; the seed is an extension of the fake so the bridge's
        ``cap.world.seed.v1``/``cap.world.reset.v1`` parameter has an effect here.  ``options`` is accepted and
        ignored because the upstream reset defines none.
        """
        if seed is not None:
            self.observation_space.seed(int(seed))
        new_position = self.observation_space.sample()              # muller_brown_discrete.py:118
        self.set_state(new_position)                                # muller_brown_discrete.py:119
        return self.agent_position

    def state_to_coord(self, state):
        """Physical coordinates of an integer grid state (muller_brown_discrete.py:52-58)."""
        ix, iy = state
        return self.x_values[ix], self.y_values[iy]

    def energy(self, state):
        """The Muller-Brown potential of a grid state (muller_brown_discrete.py:65-87)."""
        x, y = self.state_to_coord(state)
        value = 0.0
        for k in range(len(X0)):
            value += A[k] * math.exp(A_X[k] * (x - X0[k]) ** 2
                                     + B[k] * (x - X0[k]) * (y - Y0[k])
                                     + C[k] * (y - Y0[k]) ** 2)
        return value

    def set_state(self, state):
        self.agent_position = state                              # muller_brown_discrete.py:89-90

    def is_off_grid(self, state):
        ix, iy = state
        if ix not in range(self.m):                              # muller_brown_discrete.py:92-99
            return True
        if iy not in range(self.n):
            return True
        return False

    def step(self, action):
        """Move one grid point and reward the energy decrease (muller_brown_discrete.py:101-115)."""
        old_energy = self.energy(self.agent_position)
        delta = self.action_dict[action]
        new_state = [self.agent_position[0] + delta[0], self.agent_position[1] + delta[1]]
        done = False                                             # muller_brown_discrete.py:105
        if not self.is_off_grid(new_state):                      # muller_brown_discrete.py:107
            self.set_state(new_state)                            # muller_brown_discrete.py:108
            new_energy = self.energy(new_state)                  # muller_brown_discrete.py:109
            reward = old_energy - new_energy                     # muller_brown_discrete.py:110
            return new_state, reward, done, {}
        reward = -1e2                                            # muller_brown_discrete.py:114
        return self.agent_position, reward, done, {}             # muller_brown_discrete.py:115

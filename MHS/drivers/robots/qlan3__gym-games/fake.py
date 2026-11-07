"""Fake backend of the gym-games driver: a pure Python stand-in for ``gym_exploration.envs.nchain:NChainEnv``.

Why a fake: the acceptance gate runs without gymnasium, numpy or the upstream package, and package code never
imports the clone.  This module re-implements NChainEnv (the class the driver names as ``native``): a chain of
``n`` states, a start at state 1, actions 0 (left) and 1 (right), the 0.001/1.0 end rewards, the boolean
observation ``(v <= state)`` and the ``n + 8`` step termination.  Every constant and rule below cites the line of
the clone at the pinned commit 0220815982456a20f02887b20a7d9a5fbeeedd55.

The public members are the ones NChainEnv has (``reset``, ``step``, ``reward``, ``close``; gate G7), and the two
space classes duck-type ``gymnasium.spaces.Discrete`` and ``Box`` (the bridge reads ``n``, ``start``, ``low``,
``high``, ``shape``).  What this is not: the upstream environment.  The fake returns lists of Python ints where
upstream returns numpy uint8 arrays, it has no ``render`` method, and it was not compared with a run of the
upstream class (gymnasium and numpy were not importable where the gate ran).  The driver's fidelity ``gaps`` say
all of this.  Nothing here talks to a device.
"""

# gym_exploration/envs/nchain.py:15 (NChainEnv.__init__ default n) and :20-23 (init).
DEFAULT_N = 10


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

    def __init__(self, low, high, shape, dtype):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = dtype


class FakeNChainEnv:
    """NChainEnv without numpy: ``reset(seed, options)`` and ``step(action)`` return what the upstream methods do."""

    def __init__(self, n=DEFAULT_N):
        self.n = int(n)
        # nchain.py:17: the action space is Discrete(2).
        self.action_space = Discrete(2)
        # nchain.py:22: Box(low=0, high=1, shape=(n,), dtype=np.uint8).
        self.observation_space = Box(low=[0.0] * self.n, high=[1.0] * self.n, shape=(self.n,), dtype="uint8")
        # nchain.py:23: max_steps = n + 8.
        self.max_steps = self.n + 8
        # nchain.py:16: the agent starts at state 1 (s2).
        self.state = 1
        # nchain.py:33: reset starts the step counter at 0.
        self.steps = 0

    def _get_obs(self, v):
        # nchain.py:26: (v <= state) as uint8.
        return [1 if value <= self.state else 0 for value in v]

    def reset(self, seed=None, options=None):
        # nchain.py:28-34: super().reset(seed=seed); the chain itself has no random numbers.
        del seed, options
        # nchain.py:31-33.
        v = list(range(self.n))
        self.state = 1
        self.steps = 0
        return self._get_obs(v), {}

    def reward(self, s, a):
        # nchain.py:37-42: the reward of the state before the transition.
        if s == self.n - 1 and a == 1:
            return 1.0
        if s == 0 and a == 0:
            return 0.001
        return 0

    def step(self, action):
        # nchain.py:45: the action must belong to the action space.
        if not self.action_space.contains(action):
            raise AssertionError(f"{action!r} ({type(action)}) invalid")
        # nchain.py:46: v = np.arange(self.n).
        v = list(range(self.n))
        # nchain.py:48-54: reward first, then move one state (or stay at an end).
        r = self.reward(self.state, action)
        if action == 1:
            if self.state != self.n - 1:
                self.state += 1
        else:
            if self.state != 0:
                self.state -= 1
        # nchain.py:55-59: terminate at max_steps.
        self.steps += 1
        terminated = self.steps >= self.max_steps
        # nchain.py:60: the observation, reward, terminated, truncated, info tuple.
        return self._get_obs(v), r, terminated, False, {}

    def close(self):
        # nchain.py:65-66: close returns None.
        return None

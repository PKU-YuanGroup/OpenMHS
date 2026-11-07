"""Fake backend of the multi-agent emergence environments driver: a reduced pure Python stand-in for
``mae_envs.envs.base:Base``.

Why a fake: the pinned upstream needs ``mujoco-worldgen``, ``mujoco-py`` and MuJoCo 2.1 binaries
(README.md:7-11) and was tested only on Python 3.6 (README.md:14); the acceptance gate runs without
them and package code never imports or runs the clone.  This module models only the shape of the
upstream environment: ``reset``, ``step``, a Box action space bounded by ``action_lims`` and a Box
observation space.  The class named by ``native`` is ``mae_envs.envs.base:Base``; the public methods
here (``reset`` and ``step``) are names that also occur in the clone, and the remaining members are
instance attributes of the fake, not a claim about the upstream class.

Nothing here talks to a device.  Every number below is fake test data, marked ``# placeholder``: the
pinned clone does not state the raw action dimension, the observation values, the reward or the
physics timestep.  They are not facts and must not be copied into ``driver.py`` facts, limits or the
generated reference.
"""

import random

# The action dimension of the raw Base environment is not stated in the pinned clone: Base passes
# only the action_lims two-tuple to mujoco-worldgen, which builds the Box from the simulation's
# actuators (mae_envs/envs/base.py:31-35).  The fake uses two action values per agent.  # placeholder
ACTION_DIM_PER_AGENT = 2
# Fixed integration constants of the stand-in only.  # placeholder
ACCEL = 0.1
DAMPING = 0.9
START_RANGE = 0.5
POSITION_BOUND = 100.0


class Box:
    """Duck-typed ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, shape=None):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        values = value.tolist() if hasattr(value, "tolist") else value
        if not isinstance(values, (list, tuple)) or len(values) != len(self.low):
            return False
        return all(low <= float(item) <= high
                   for item, low, high in zip(values, self.low, self.high))


class FakeBase:
    """A deterministic stand-in for one ``Base`` environment; ``reset`` and ``step`` mirror its API.

    The upstream ``Base`` inherits ``reset``/``step`` from ``mujoco_worldgen.Env``; the stand-in
    accepts the modern ``seed`` keyword so the Gymnasium bridge can seed it, and returns the legacy
    four-tuple ``(observation, reward, done, info)`` that the same base class returns.
    """

    # Inherited from mujoco_worldgen.Env by Base (mae_envs/envs/base.py:3, :13); the bridge reads them.
    action_space: object
    observation_space: object

    def __init__(self, horizon=250, n_substeps=5, n_agents=2, floor_size=6.0, grid_size=30,
                 action_lims=(-1.0, 1.0), deterministic_mode=False, **kwargs):
        self.horizon = None if horizon is None else int(horizon)     # base.py:27, :39
        self.n_substeps = int(n_substeps)                            # base.py:27, :40
        self.n_agents = int(n_agents)                                # base.py:27, :36
        self.floor_size = float(floor_size)                          # base.py:28
        self.grid_size = int(grid_size)                              # base.py:28
        self.action_lims = (float(action_lims[0]), float(action_lims[1]))  # base.py:29
        self.deterministic_mode = bool(deterministic_mode)           # base.py:29
        self.kwargs = dict(kwargs)
        size = ACTION_DIM_PER_AGENT * self.n_agents
        self.action_space = Box([self.action_lims[0]] * size, [self.action_lims[1]] * size)
        observation_size = 4 * self.n_agents
        self.observation_space = Box([-POSITION_BOUND] * observation_size,
                                     [POSITION_BOUND] * observation_size)
        self._rng = random.Random(0)
        self._seed = 0
        self._next_seed = 0
        self._t = 0
        self._state = [0.0] * observation_size

    def reset(self, force_seed=None, seed=None, options=None):
        """Build a fresh start state; ``seed`` repeats the same start state."""
        if seed is None:
            seed = force_seed if force_seed is not None else self._next_seed
        self._seed = int(seed)
        self._next_seed = self._seed
        self._rng = random.Random(self._seed)
        self._state = []
        for _ in range(self.n_agents):
            self._state.extend([self._rng.uniform(-START_RANGE, START_RANGE),      # placeholder
                                self._rng.uniform(-START_RANGE, START_RANGE),      # placeholder
                                0.0, 0.0])                                          # placeholder
        self._t = 0
        return list(self._state), {"seed": self._seed}

    def step(self, action):
        """Advance one outer step; the action is one continuous value per agent dimension."""
        if self.horizon is not None and self._t >= self.horizon:
            raise AssertionError("the episode has ended; reset it")
        values = action.tolist() if hasattr(action, "tolist") else list(action)
        if not self.action_space.contains(values):
            raise AssertionError(f"action {values!r} is outside {self.action_space.low!r}..{self.action_space.high!r}")
        for agent in range(self.n_agents):
            base = 4 * agent
            for axis in range(ACTION_DIM_PER_AGENT):
                velocity = self._state[base + 2 + axis] * DAMPING + values[agent * ACTION_DIM_PER_AGENT + axis] * ACCEL
                self._state[base + 2 + axis] = velocity
                self._state[base + axis] += velocity
        self._t += 1
        done = self.horizon is not None and self._t >= self.horizon
        return list(self._state), 0.0, done, {"t": self._t}

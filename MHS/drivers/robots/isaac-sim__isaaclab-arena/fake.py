"""Fake backend for the Isaac Lab-Arena Gymnasium driver.

The gate cannot import Isaac Lab-Arena (it needs Isaac Sim, Isaac Lab, Linux and an NVIDIA GPU, README.md:79-80),
so this module is a small, pure Python stand-in for the single-environment part of
``isaaclab_arena.environments.isaaclab_arena_manager_based_env:IsaacLabArenaManagerBasedRLEnv``.  The upstream class
is a vectorized Isaac Lab environment (isaaclab_arena_manager_based_env.py:34): reset takes ``(seed, env_ids,
options)`` (:173-181) and step takes a tensor action and returns ``(observation, reward, terminated, truncated,
extras)`` (:183-189).  A policy receives the observation as a Gymnasium Dict and returns an action tensor shaped like
``env.action_space`` (docs/pages/concepts/policy/index.rst:64-66); the composed embodiment selects the action terms
(docs/pages/concepts/embodiment/index.rst:32-35) and the observation groups come from the observation manager.

The fake keeps one scalar kinematic coordinate so the contract has an observable state, and it records the seed.  Its
unbounded action Box is test data, not a device bound: the bridge therefore publishes no finite action limit.  Every
number below is test data only (each marked ``# placeholder``); none is copied into a Fact, a Limit or the reference.
"""

import random

# No finite bound is claimed: the fake's action Box is unbounded, so the bridge publishes no action limit.
INF = float("inf")


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a low and a high bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeArenaEnv:
    """A one-coordinate stand-in for ``IsaacLabArenaManagerBasedRLEnv``.

    ``reset`` and ``step`` are the two public methods of the upstream class that the Gymnasium bridge calls; both
    are defined by the upstream class (isaaclab_arena_manager_based_env.py:173 and :183), so gate G7 resolves them in
    the clone.  The upstream reset also accepts ``env_ids``; the bridge never passes it.
    """

    def __init__(self, **_options):
        self.action_space = Box([-INF], [INF])                    # one element placeholder
        self.observation_space = Dict({"policy": Box([-INF], [INF])})  # one group placeholder
        self._rng = random.Random()
        self._position = 0.0                                      # placeholder: initial coordinate
        self._tick = 0
        self._episode = 0

    def reset(self, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        # placeholder: the fake's start range; the upstream start state comes from the composed scene
        self._position = self._rng.uniform(-1.0, 1.0)
        self._tick = 0
        self._episode += 1
        return {"policy": [self._position]}, {}

    def step(self, action):
        # placeholder: one scalar action moves the coordinate by a fixed gain; the upstream applies the
        # configured action terms and Isaac Lab physics through the environment step
        value = float(action[0]) if isinstance(action, (list, tuple)) and action else 0.0
        self._position += value * 0.1
        self._tick += 1
        return {"policy": [self._position]}, 0.0, False, False, {"tick": self._tick}

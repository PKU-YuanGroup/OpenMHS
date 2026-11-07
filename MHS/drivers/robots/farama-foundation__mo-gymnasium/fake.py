"""Fake backend of the MO-Gymnasium driver: the FishWood two-state environment in pure Python.

Why a fake: the acceptance gate runs without MO-Gymnasium (the upstream package needs gymnasium, numpy and
pygame-ce, pyproject.toml:24-28), and package code never imports the clone.  This module re-implements
``mo_gymnasium.envs.fishwood.fishwood:FishWood`` (the class the driver names as ``native``): the two states, the
two actions, the Bernoulli reward of the current state, the transition and the 200-step termination.  Every
constant and rule below cites a line of the clone at the pinned commit
(8d280fdc3f517b18090619806843c03f51d775af).  The public members are the ones FishWood has (``reset`` and
``step``; gate G7), and the two space classes duck-type ``gymnasium.spaces.Discrete`` and ``Box`` (the bridge
reads ``n``, ``start``, ``low``, ``high`` and ``shape``).

What this is not: the upstream environment.  Differences, all listed in the fidelity ``gaps`` of the driver:

* MO-Gymnasium returns a reward *vector* (README.md:13), while ``cap.world.step.v1`` has a single scalar ``reward``.
  The two objectives of FishWood are one-hot, so the fake returns their sum (0 or 1, the number of resources
  collected in the step) and keeps the full ``[fish, wood]`` vector in ``info["objectives"]``; the vector is not in
  the standard's step output.
* the Bernoulli draw uses Python's ``random.Random(seed)`` instead of numpy's ``np_random`` generator, so a seed
  gives a different reward sequence on the two.
* there is no rendering and no snapshot/restore.

Numbers in this module are the environment's own constants and probabilities, each cited; no start position or
canned reply is invented.  Nothing here talks to a device.
"""

import random

# mo_gymnasium/envs/fishwood/fishwood.py:45-47: state 0 is fishing, state 1 is in the woods, and the episode ends
# after MAX_TS = 200 steps.
FISH = 0
WOOD = 1
MAX_TS = 200
# fishwood.py:49: the constructor defaults fishproba=0.1 and woodproba=0.9
FISHPROBA = 0.1
WOODPROBA = 0.9


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
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element of a one-value state."""

    def __init__(self, low, high, dtype="int32"):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = dtype


class FakeFishWood:
    """FishWood without numpy: ``reset(seed, options)`` and ``step(action)`` as the class has them."""

    def __init__(self, render_mode=None, fishproba=FISHPROBA, woodproba=WOODPROBA):
        if render_mode is not None:
            raise ValueError("the fake FishWood cannot render; use render_mode=None")
        self.render_mode = render_mode
        self._fishproba = fishproba
        self._woodproba = woodproba
        # fishwood.py:56: Discrete(2), action 0 go fishing and action 1 go collect wood
        self.action_space = Discrete(2)
        # fishwood.py:58: Box(low=0, high=1, shape=(1,), dtype=int32)
        self.observation_space = Box([0], [1])
        # fishwood.py:60-61: reward_space Box(low=[0, 0], high=[1.0, 1.0], float32) with reward_dim 2
        self.reward_dim = 2
        # fishwood.py:63: the fisherman starts in the woods
        self._state = [WOOD]
        self._timestep = 0
        self._rng = random.Random()

    def reset(self, seed=None, **kwargs):
        """``reset`` (fishwood.py:65-73): state WOOD and timestep 0; the seed arms the fake's generator."""
        del kwargs
        self._state = [WOOD]
        self._timestep = 0
        self._rng = random.Random(seed)
        return list(self._state), {}

    def step(self, action):
        """``step`` (fishwood.py:82-97): reward the current state, then move to the action's state."""
        if not self.action_space.contains(action):
            raise ValueError(f"bad action {action!r}: the action space is Discrete(2)")
        rewards = [0.0, 0.0]
        # fishwood.py:84-89: a Bernoulli draw pays the objective of the state the fisherman is leaving.
        if self._state == [WOOD] and self._rng.random() < self._woodproba:
            rewards[WOOD] = 1.0
        elif self._state == [FISH] and self._rng.random() < self._fishproba:
            rewards[FISH] = 1.0
        # fishwood.py:91-93: the action becomes the next state and the timestep advances
        self._state = [int(action)]
        self._timestep += 1
        # fishwood.py:97: both terminated and truncated are true at MAX_TS
        done = self._timestep == MAX_TS
        # The standard's reward is a single number and FishWood's two objectives are one-hot, so the scalar is
        # their sum (the number of resources collected in the step) and the vector stays in info.
        return list(self._state), sum(rewards), done, done, {"objectives": rewards}

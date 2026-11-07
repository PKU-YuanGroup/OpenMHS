"""Fake backend for gh.carlosferrazza/humanoid-bench: a pure Python stand-in for ``humanoid_bench.env:HumanoidEnv``.

The gate cannot import the upstream package (it needs MuJoCo, dm_control, numpy and the pinned
``install`` dependencies, and package code never imports the clone).  This module therefore models the
contract of one registered environment, ``h1-stand-v0``, without MuJoCo:

* the action space is a ``Box`` of the H1 stand model's actuators, normalised to ``[-1, 1]`` by
  ``humanoid_bench/env.py:162-166``;
* the observation is the concatenation of the model's ``qpos`` and ``qvel`` that ``Task.get_obs`` returns
  (``humanoid_bench/tasks.py:32-36``), with the shape of the Stand observation space
  (``humanoid_bench/envs/basic_locomotion_envs.py:40-44``);
* ``reset(seed, options)`` accepts the Gymnasium reset signature and returns ``(observation, info)``;
* ``step(action)`` returns ``(observation, reward, terminated, truncated, info)`` like ``Task.step``
  (``humanoid_bench/tasks.py:60-69``).

What this is not: the MuJoCo model.  The dynamics here are a deliberately simple analytic stand-in, every
numeric constant below is test data marked ``# placeholder``, and the fake was never compared with the
upstream environment.  Episode termination, contacts, actuator forces, the keyframe start state and the
upstream numpy random stream are not modelled; the driver's fidelity ``gaps`` list these omissions.

The public methods are limited to ``reset`` and ``step`` (gate G7 checks them against the AST surface of
the upstream class).  Both also occur in the clone and are inherited by ``HumanoidEnv`` from
``gymnasium.envs.mujoco.MujocoEnv``, which the AST cannot follow, so G7 may report ``MAYBE_ABSENT`` for
them; that warning is expected.
"""

import math
import random

#: Sizes of the h1-stand-v0 model.  Each is test data of this stand-in (the sourced shape formulas are in
#: facts.md); the model itself has 26 qpos values and 19 position actuators.
N_ACTUATORS = 19          # placeholder
N_QPOS = 26               # placeholder
N_QVEL = N_QPOS - 1       # placeholder: a free root joint has nq - 1 velocities
OBSERVATION_SIZE = N_QPOS + N_QVEL  # placeholder

#: Start height and reset noise of the stand-in; the real model's keyframe and DEFAULT_RANDOMNESS differ.
START_HEIGHT = 0.98       # placeholder
RESET_NOISE = 0.01        # placeholder

#: One environment step advances 10 physics frames of 0.002 s, i.e. 20 ms (facts.md).
DT_S = 0.02               # placeholder
ACTION_DECAY = 0.5        # placeholder: the velocity decay of this analytic stand-in


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape=None, dtype=None):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = dtype or "float64"

    def contains(self, value):
        if not isinstance(value, (list, tuple)) or len(value) != self.shape[0]:
            return False
        return all(float(low) <= float(item) <= float(high)
                   for item, low, high in zip(value, self.low, self.high))


class FakeHumanoidStand:
    """A deterministic analytic world with the action and observation contract of ``h1-stand-v0``."""

    def __init__(self, **_options):
        # The two space attributes are the ones HumanoidEnv sets in its __init__ (env.py:162-166 and the
        # observation_space passed at env.py:150-160); the bridge derives the contract from them.
        self.action_space = Box([-1.0] * N_ACTUATORS, [1.0] * N_ACTUATORS,
                                (N_ACTUATORS,), "float32")                    # placeholder
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE,
                                     (OBSERVATION_SIZE,), "float64")          # placeholder
        self._rng = random.Random(0)                                        # placeholder
        self._qpos = [0.0] * N_QPOS
        self._qvel = [0.0] * N_QVEL
        self._tick = 0
        self._reset(None)

    def _reset(self, seed):
        """Set the stand-in's start state; ``seed`` fixes the pseudo-random draw."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        noise = [self._rng.uniform(-RESET_NOISE, RESET_NOISE) for _ in range(N_QPOS)]  # placeholder
        self._qpos = list(noise)
        self._qpos[2] = START_HEIGHT + noise[2]                         # placeholder
        self._qvel = [0.0] * N_QVEL
        self._tick = 0

    def reset(self, seed=None, options=None):
        """Gymnasium reset: return the initial observation and an empty info object."""
        self._reset(seed)
        return list(self._qpos) + list(self._qvel), {}

    def step(self, action):
        """Apply one action and return the next observation, reward, flags and info."""
        values = list(action)
        if len(values) != N_ACTUATORS:
            raise ValueError(f"h1-stand-v0 takes {N_ACTUATORS} action values, got {len(values)}")
        for index, value in enumerate(values):
            self._qvel[index] = ACTION_DECAY * self._qvel[index] + float(value)  # placeholder
        for index in range(N_QVEL):
            self._qpos[index] = self._qpos[index] + DT_S * self._qvel[index]     # placeholder
        self._tick += 1
        reward = 1.0 / (1.0 + sum(abs(float(value)) for value in values))        # placeholder
        return list(self._qpos) + list(self._qvel), reward, False, False, {"tick": self._tick}

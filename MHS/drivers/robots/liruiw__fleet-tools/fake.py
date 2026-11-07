"""Fake backend of the Fleet-Tools driver: a pure Python stand-in for ``env.frankadrakeenv:FrankaDrakeEnv``.

Why a fake: the upstream environment needs a Hydra ``task_config``, pydrake, torch and the bundled object assets
(README.md:5, requirements.txt), none of which is available where the gate runs, and package code never imports or
runs the clone.  This module therefore stands in for the class the driver names as ``native`` with only the public
members that class has (``action_space``, ``observation_space``, ``reset``, ``seed`` and ``step``; gate G7) and
with space objects that duck-type the ``gym.spaces.Box`` the upstream properties return.

The action space follows the upstream code: ``PandaTaskSpace6D`` returns a six-element Box whose first three
bounds are +-the translation scale and whose last three are +-the rotation scale
(core/utils/utils.py:372-396), with both scales taken from ``task_config.env.action_scale``
(env/frankadrakeenv.py:134).  The Hammer teleop configuration sets those scales to 0.04 and 0.4
(experiments/config/task/FrankaDrakeHammerEnvTeleop.yaml:29) and sets numObservations to [9]
(:26); the observation space is Box(-1.0, 1.0) with that shape (env/frankadrakeenv.py:139).

What this is not: the upstream Drake simulation.  It models no rigid body, contact, friction, controller, sensor or
renderer, its base reward is the upstream base's 0 (env/frankadrakeenv.py:415-416), and it never terminates an
episode (the base step sets done to sim_done, env/frankadrakeenv.py:248).  The initial observation values are test
data marked ``# placeholder``; the driver's fidelity ``gaps`` list every difference.  Nothing here talks to a
device.
"""

import random

# Bounds of PandaTaskSpace6D(task_config.env.action_scale); the Hammer teleop config's scales are [0.04, 0.4]
# (core/utils/utils.py:372-396, experiments/config/task/FrankaDrakeHammerEnvTeleop.yaml:29).
TRANSLATION_BOUND = 0.04
ROTATION_BOUND = 0.4
# numObservations [9] of the Hammer teleop config (experiments/config/task/FrankaDrakeHammerEnvTeleop.yaml:26).
OBSERVATION_SIZE = 9
# Test data: the spread of the fake's initial observation only; it is not an upstream value.
INITIAL_JITTER = 1e-3  # placeholder


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape``."""

    def __init__(self, low, high, shape):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = "float32"


class FakeFrankaDrakeEnv:
    """A deterministic stand-in for ``FrankaDrakeEnv`` in the Hammer teleop configuration.

    ``reset`` accepts the legacy ``done`` argument of the upstream method (env/frankadrakeenv.py:362) and returns
    the legacy four-tuple (env/frankadrakeenv.py:380); the Gymnasium bridge calls it without arguments, after
    ``seed`` when a seed is supplied.  ``step`` returns the legacy four-tuple (env/frankadrakeenv.py:250) with the
    base reward 0 (env/frankadrakeenv.py:415-416).  The observation is a nine-value placeholder state: after a step
    it holds the six action values followed by the previous first three values.
    """

    def __init__(self, task_config=None):
        self.task_config = task_config
        self.action_space = Box(
            [-TRANSLATION_BOUND, -TRANSLATION_BOUND, -TRANSLATION_BOUND,
             -ROTATION_BOUND, -ROTATION_BOUND, -ROTATION_BOUND],
            [TRANSLATION_BOUND, TRANSLATION_BOUND, TRANSLATION_BOUND,
             ROTATION_BOUND, ROTATION_BOUND, ROTATION_BOUND],
            (6,),
        )
        self.observation_space = Box([-1.0] * OBSERVATION_SIZE, [1.0] * OBSERVATION_SIZE,
                                     (OBSERVATION_SIZE,))
        self._rng = random.Random(0)
        self._observation = [0.0] * OBSERVATION_SIZE
        self._tick = 0

    def seed(self, seed=None):
        """Mirror the upstream ``seed`` (env/frankadrakeenv.py:141-144): seed the generator and echo it."""
        if seed is None:
            seed = self._rng.randrange(2 ** 31)
        self._rng.seed(seed)
        return [seed]

    def reset(self, done=False):
        """Reset to a seeded placeholder start and return the legacy four-tuple."""
        self._tick = 0
        self._observation = [self._rng.uniform(-INITIAL_JITTER, INITIAL_JITTER)  # placeholder
                             for _ in range(OBSERVATION_SIZE)]
        return list(self._observation), 0, done, {"timestep": 0}

    def step(self, action):
        """Apply the six-value action to the placeholder state and return the legacy four-tuple."""
        values = [float(value) for value in action]
        self._tick += 1
        self._observation = values + self._observation[:3]
        return list(self._observation), 0, False, {"timestep": self._tick}

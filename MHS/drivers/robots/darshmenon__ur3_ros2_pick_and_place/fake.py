"""Package analytic stand-in for the upstream UR5e reach Gymnasium environment.

The upstream ``URReachEnv`` needs MuJoCo and a Menagerie checkout and is never
imported by the gate.  This fake reproduces the interface the Gymnasium bridge
uses: a six-element Box action space, a 15-number Box observation space,
``reset(seed, options)`` and a five-tuple ``step(action)``.  It is a
deterministic analytic stand-in, not a physics simulation.

Action bounds and observation dimensions copy the pinned source declarations.
Transition/state numbers marked ``# placeholder`` are test data, not device facts
or safety limits; they are not used as citation evidence.
"""

import math
import random


class Box:
    """A duck-typed Gymnasium Box space (the class name is what the bridge reads)."""

    def __init__(self, low, high, shape, dtype):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = dtype


class FakeURReachEnv:
    """A small, seeded stand-in for ``URReachEnv`` with no MuJoCo dependency."""

    def __init__(self, **_options):
        self.render_mode = None
        # Source copy: ur_reach_env.py:55,64-66 declares six actions in [-1, 1].
        # The separate transition/state numbers below are placeholders.
        self.action_space = Box([-1.0] * 6, [1.0] * 6, (6,), "float32")
        # Source copy: ur_reach_env.py:55-61,75-79 declares 15 unbounded values.
        self.observation_space = Box([-math.inf] * 15, [math.inf] * 15, (15,), "float32")

        self._rng = random.Random(0)                  # placeholder seed
        self._joint_positions = [0.0] * 6             # placeholder
        self._joint_velocities = [0.0] * 6            # placeholder
        self._ee_position = [0.0, 0.0, 0.0]           # placeholder
        self._target = [0.4, 0.0, 0.4]                # placeholder
        self._steps = 0                               # placeholder
        self._closed = False                          # placeholder

    def _observation(self):
        return [*self._joint_positions, *self._joint_velocities, *self._target]

    def reset(self, seed=None, options=None):
        """Restore the placeholder initial state and resample the target."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._joint_positions = [0.0] * 6             # placeholder
        self._joint_velocities = [0.0] * 6            # placeholder
        self._ee_position = [0.0, 0.0, 0.0]           # placeholder

        radius = self._rng.uniform(0.2, 0.55)         # placeholder
        azimuth = self._rng.uniform(-math.pi / 2, math.pi / 2)   # placeholder
        elevation = self._rng.uniform(0.1, math.pi / 2)          # placeholder
        self._target = [
            radius * math.sin(elevation) * math.cos(azimuth),
            radius * math.sin(elevation) * math.sin(azimuth),
            radius * math.cos(elevation),
        ]                                             # placeholder
        self._steps = 0                               # placeholder
        self._closed = False                          # placeholder
        return self._observation(), {}

    def step(self, action):
        """Apply one placeholder kinematic transition and return the Gymnasium tuple."""
        values = [float(item) for item in action]
        if len(values) != 6:
            raise ValueError("action must have six elements")

        self._joint_velocities = [0.5 * value for value in values]   # placeholder (0.5)
        self._joint_positions = [
            position + 0.01 * velocity                 # placeholder (0.01)
            for position, velocity in zip(self._joint_positions, self._joint_velocities)
        ]
        self._ee_position = [
            position + 0.01 * value for position, value in zip(self._ee_position, values)   # placeholder (0.01)
        ]

        distance = math.dist(self._ee_position, self._target)   # placeholder
        reward = -distance                            # placeholder
        if distance < 0.05:                           # placeholder
            reward += 1.0                             # placeholder
        self._steps += 1                              # placeholder
        return self._observation(), reward, False, False, {"dist": distance}   # placeholder

    def close(self):
        """Close the fake; there is no viewer or MuJoCo data to release."""
        self._closed = True

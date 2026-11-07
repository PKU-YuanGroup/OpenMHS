"""Fake backend of the rex-gym driver: a pure Python stand-in for ``rex_gym.envs.gym.walk_env:RexWalkEnv``.

Why a fake: the clone pins Python 3.7, numpy 1.17.3, pybullet 2.8.3, gym 0.17.1 and TensorFlow 1.15.5
(``requirements.txt:1-7``), none of them importable where the gate runs, and package code never imports the clone.
This module re-implements only the gym surface of ``RexWalkEnv`` that the bridge reads: ``action_space``,
``observation_space``, ``reset``, ``seed``, ``step`` and ``close`` (gate G7 checks those names against the upstream
class and its in-clone base ``rex_gym.envs.rex_gym_env:RexGymEnv``).  The two space classes duck-type
``gym.spaces.Box`` (the bridge reads ``low``, ``high`` and ``shape``).

What this is not: the pybullet environment.  The upstream observation is [roll, pitch, roll_rate, pitch_rate] read
from the simulated robot (``walk_env.py:356-362``); this fake advances those four values by a placeholder kinematic
rule and returns reward 0.0.  It models no URDF, motor, gait, contact, fall or reward, and was never compared with the
pybullet environment.  It uses Python's ``random.Random`` where upstream's reset draws from the global ``random``
module (``walk_env.py:133-146``), so one seed repeats this fake but does not repeat upstream.  The driver's fidelity
``gaps`` say all of this.  Nothing here talks to a device.
"""

import math
import random

# rex_gym/envs/gym/walk_env.py:34-35, rex_gym/envs/rex_gym_env.py:170-173: the default control step 0.005 s divided
# by action_repeat 5.
PHYSICS_TIME_STEP = 0.001
# rex_gym/envs/gym/walk_env.py:104-114: the 'ik' action bounds and dimension.
ACTION_MAX = 0.4
ACTION_DIM = 2
# rex_gym/envs/gym/walk_env.py:364-378: 2*pi for roll and pitch, 2*pi/time_step for the rates, plus OBSERVATION_EPS
# (rex_gym/envs/rex_gym_env.py:277-282).
OBSERVATION_EPS = 0.01
ANGLE_BOUND = 2 * math.pi + OBSERVATION_EPS
RATE_BOUND = 2 * math.pi / PHYSICS_TIME_STEP + OBSERVATION_EPS
# rex_gym/playground/__init__.py:24-29: max_episode_steps of RexWalk-v0, applied by the TimeLimit wrapper that
# gym.make adds.  The bridge drives a pre-built environment object, so the fake applies the limit itself.
MAX_EPISODE_STEPS = 2500

# The start values and the motion rule are placeholder test data, not the clone's physics.
START_AMPLITUDE = 0.01                                         # placeholder
ROLL_RESPONSE = 0.01                                           # placeholder
PITCH_RESPONSE = 0.01                                          # placeholder
RATE_RESPONSE = 0.1                                            # placeholder


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"

    def contains(self, value):
        try:
            values = list(value)
        except TypeError:
            return False
        return len(values) == len(self.low) and all(
            low <= float(item) <= high for item, low, high in zip(values, self.low, self.high))


class FakeRexWalkEnv:
    """``RexWalkEnv`` without pybullet, numpy or gym: ``reset``, ``seed``, ``step`` and ``close``."""

    metadata = {"render.modes": ["human", "rgb_array"], "video.frames_per_second": 66}  # walk_env.py:27

    def __init__(self, **_options):
        self.action_space = Box([-ACTION_MAX] * ACTION_DIM, [ACTION_MAX] * ACTION_DIM)  # walk_env.py:104-114
        self.observation_space = Box([-ANGLE_BOUND, -ANGLE_BOUND, -RATE_BOUND, -RATE_BOUND],
                                     [ANGLE_BOUND, ANGLE_BOUND, RATE_BOUND, RATE_BOUND])  # walk_env.py:364-378
        self._rng = random.Random(0)                           # placeholder: repeatable fake, not a device seed
        self._observation = [0.0, 0.0, 0.0, 0.0]               # placeholder
        self._backwards = False
        self._target_position = None
        self._tick = 0
        self._closed = False
        self.reset()

    def seed(self, seed=None):
        """``rex_gym_env.py:359-361``: replace the generator and return ``[seed]``."""
        self._rng = random.Random(seed)
        return [seed]

    def reset(self):
        """``walk_env.py:125-154``: draw the episode flags and target, restart the observation and return it."""
        if self._closed:
            raise RuntimeError("the environment is closed")
        self._backwards = self._rng.choice([True, False])      # placeholder draw, mirrors walk_env.py:133-136
        bound = -3 if self._backwards else 3                   # walk_env.py:144-146
        self._target_position = self._rng.uniform(bound // 2, bound)  # placeholder draw
        self._observation = [self._rng.uniform(-START_AMPLITUDE, START_AMPLITUDE) for _ in range(4)]
        self._tick = 0
        return list(self._observation)

    def step(self, action):
        """Advance the four placeholder values by one control step and apply the registered 2500-step limit."""
        if self._closed:
            raise RuntimeError("the environment is closed")
        roll, pitch, roll_rate, pitch_rate = self._observation
        first, second = float(action[0]), float(action[1])
        # Placeholder motion: a bounded oscillation driven by the two action values, not pybullet.
        roll = math.sin(roll + ROLL_RESPONSE * first)
        pitch = math.cos(pitch + PITCH_RESPONSE * second)
        roll_rate = RATE_RESPONSE * first
        pitch_rate = RATE_RESPONSE * second
        self._observation = [roll, pitch, roll_rate, pitch_rate]
        self._tick += 1
        truncated = self._tick >= MAX_EPISODE_STEPS
        # The bridge reads the gymnasium 5-tuple; the upstream class returns the legacy (observation, reward, done,
        # info) and gym.make's TimeLimit carries truncation in info instead.
        return list(self._observation), 0.0, False, truncated, {}

    def close(self):
        """``rex_gym_env.py:287-290``: the upstream close terminates the simulation; this fake has none."""
        self._closed = True

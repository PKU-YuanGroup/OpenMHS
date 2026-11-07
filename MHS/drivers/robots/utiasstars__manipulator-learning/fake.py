"""Fake backend of the manipulator-learning driver: a pure Python stand-in for the insert-tray Panda environment.

Why a fake: the acceptance gate runs without pybullet, numpy, gym, transforms3d or liegroups, and package code never
imports the clone.  This module implements the public surface the Gymnasium bridge needs from
``manipulator_learning.sim.envs.panda_play:PandaPlayInsertTrayXYZState`` (the class the driver names as ``native``):
``reset``, ``seed`` and ``step``, plus duck-typed action and observation spaces (the bridge reads ``low``, ``high``
and ``shape``).  The action size, observation size, action multiplier, substep count and workspace bounds are the
upstream configuration at the lines cited below.

What this is not: the upstream environment.  It is an analytic kinematic stand-in:

* there are no pybullet rigid bodies, joints, contacts, friction, actuator response, sensor model or rendering;
* it integrates the three translation values directly and treats the fourth value as the open/close command of the
  two-finger gripper, with no IK or arm model;
* the 59-value observation layout is the upstream layout (``panda_play.py:419-428``), but only the end-effector
  position, velocity, gripper positions and their previous values are modelled; the object and force-torque slots are
  zeros;
* the reward is the placeholder ``0.0`` and is not the upstream insert reward;
* the initial end-effector position is a placeholder near the workspace centre, jittered with Python's
  ``random.Random``; upstream draws its start with numpy's generator;
* the episode ends after the upstream 360-step time limit but is reported as the legacy ``done`` flag, like upstream.

Every start position, start jitter, gripper width and reward below is test data, marked ``# placeholder``; none of them
is a Fact or a Limit of the package.  Nothing here talks to a device.
"""

import math
import random

# PandaPlayInsertTrayXYZState documents "obs space is 59, act space is 4" (panda_play.py:419).
ACTION_SIZE = 4                         # panda_play.py:419
OBSERVATION_SIZE = 59                   # panda_play.py:419
# The class defaults are n_substeps=5 and action_multiplier=0.002, and its comment says a full-magnitude action
# moves the desired position by 2 mm * 5 = 1 cm (panda_play.py:429-430).
N_SUBSTEPS = 5                          # panda_play.py:430
ACTION_MULTIPLIER = 0.002               # panda_play.py:430
# The PBEnv default simulation step is 0.01 s (pb_env.py:69); ManipulatorEnv computes real_t_per_ts from it and
# _max_episode_steps = round(max_real_time / real_t_per_ts) (manipulator_env_generic.py:88-89).
TIME_STEP_S = 0.01                      # pb_env.py:69
MAX_REAL_TIME_S = 18                    # panda_play.py:430
MAX_EPISODE_STEPS = round(MAX_REAL_TIME_S / (TIME_STEP_S * N_SUBSTEPS))   # 360; upstream formula at :88-89
# The insert-tray workspace bounds in world coordinates (panda_play.py:443).
POS_LOW = (0.85, -0.35, 0.665)          # panda_play.py:443
POS_HIGH = (1.15, -0.05, 0.8)           # panda_play.py:443
# The default Panda workspace centre (configs/panda_default.py:39) is a convenient stand-in start.
START_POS = (1.0, -0.2, 0.7)            # placeholder
START_JITTER = 0.01                     # placeholder
GRIP_OPEN = 0.0                         # placeholder
GRIP_CLOSED = 1.0                       # placeholder


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


def _flat(values):
    out = []
    for value in values:
        if isinstance(value, (list, tuple)):
            out.extend(_flat(value))
        else:
            out.append(float(value))
    return out


class FakePandaPlayInsertTrayXYZState:
    """The insert-tray Panda environment without pybullet: a bounded kinematic stand-in.

    ``reset(mb_base_angle, reset_dict)`` and ``seed(seed)`` keep the upstream method names, while ``step(action)``
    returns the legacy four-tuple ``(observation, reward, done, info)``.  The bridge calls ``reset()`` and falls back
    to ``seed(seed)`` because the upstream ``reset`` does not take a Gymnasium ``seed`` parameter.
    """

    def __init__(self, **_options):
        self.action_space = Box([-1.0] * ACTION_SIZE, [1.0] * ACTION_SIZE)          # panda_play.py:419-420
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE,
                                     [math.inf] * OBSERVATION_SIZE)                  # panda_play.py:419
        self._rng = random.Random()
        self._pos = list(START_POS)                                                 # placeholder
        self._vel = [0.0, 0.0, 0.0]                                                 # placeholder
        self._grip = [GRIP_OPEN, GRIP_OPEN]                                         # placeholder
        self._prev_grip = [GRIP_OPEN, GRIP_OPEN, GRIP_OPEN, GRIP_OPEN]              # placeholder
        self._tick = 0
        self._closed = False

    def seed(self, seed=None):
        """Set the fake's generator; upstream delegates to ``gym.utils.seeding.np_random`` (pb_env.py:390-393)."""
        self._rng = random.Random(seed)
        return [seed]

    def reset(self, mb_base_angle=None, reset_dict=None):
        """Start an episode and return the initial 59-value observation (upstream reset at :550-573)."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        self._pos = [START_POS[index] + self._rng.uniform(-START_JITTER, START_JITTER)
                     for index in range(3)]                                        # placeholder
        self._vel = [0.0, 0.0, 0.0]                                                # placeholder
        self._grip = [GRIP_OPEN, GRIP_OPEN]                                        # placeholder
        self._prev_grip = [GRIP_OPEN, GRIP_OPEN, GRIP_OPEN, GRIP_OPEN]             # placeholder
        self._tick = 0
        return self._observation()

    def step(self, action):
        """Apply one bounded action and return ``(observation, reward, done, info)`` (upstream :171-238)."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        values = _flat(action)
        if len(values) != ACTION_SIZE:
            raise ValueError(f"the action has {ACTION_SIZE} values, got {len(values)}")
        delta = [ACTION_MULTIPLIER * N_SUBSTEPS * value for value in values[:3]]   # panda_play.py:429
        self._pos = [min(max(position + change, low), high)
                     for position, change, low, high in zip(self._pos, delta, POS_LOW, POS_HIGH)]
        self._vel = [change / (TIME_STEP_S * N_SUBSTEPS) for change in delta]      # placeholder units
        self._prev_grip = [self._grip[0], self._grip[1], self._prev_grip[0], self._prev_grip[1]]
        closed = GRIP_CLOSED if values[3] >= 0 else GRIP_OPEN                      # manipulator_env_generic.py:190-194
        self._grip = [closed, closed]
        self._tick += 1
        done = self._tick >= MAX_EPISODE_STEPS                                     # manipulator_env_generic.py:229-232
        return self._observation(), 0.0, done, {"tick": self._tick}                # placeholder reward

    def _observation(self):
        """The upstream 59-value layout with only the end-effector and gripper slots modelled (panda_play.py:419-428)."""
        observation = [0.0] * OBSERVATION_SIZE                                     # placeholder for unmodelled slots
        observation[0:3] = self._pos
        observation[3:6] = self._vel
        observation[6:8] = self._grip
        observation[8:12] = self._prev_grip
        return observation

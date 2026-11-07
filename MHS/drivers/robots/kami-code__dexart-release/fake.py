"""Fake backend of the DexArt driver: a pure-Python kinematic stand-in for ``BaseRLEnv`` at the pinned commit.

Why a fake: the upstream environment imports ``gym``, ``numpy``, ``sapien`` and ``transforms3d`` and loads assets
that are downloaded separately (README.md:35-37); the gate cannot import that stack, and package code never imports or
runs the clone.  This module implements only the public surface of ``dexart.env.rl_env.base:BaseRLEnv`` that the
Gymnasium bridge uses: ``reset``, ``step``, ``action_space`` and ``observation_space`` (gate G7).  The space class
duck-types ``gym.spaces.Box`` so the bridge can derive the JSON schema and the per-element action limits
(``low``, ``high``, ``shape``).

The fake mirrors the legacy Gym contract of the laptop task:

* ``reset()`` returns only the observation (``laptop_env.py:104-123``);
* ``step(action)`` returns the four-value ``(obs, reward, done, info)`` tuple (``base.py:216-229``);
* the action is the 22-element vector of a 6-DoF arm plus a 16-DoF hand (``base.py:91-92``,
  ``common_robot_utils.py:53-56``);
* the observation is the 32-value laptop oracle vector: 22 joint positions plus three palm velocities, three palm
  angular velocities, three palm positions and the progress fraction (``laptop_env.py:71-75``).

What it is not: the upstream simulator.  It does not run Sapien, models no contacts, friction, inverse kinematics,
motors, grasp physics or articulated-object constraints, and it returns a constant reward.  The episode ends at the
laptop horizon of 250 steps (``laptop_env.py:146-148``); the upstream task also ends early on task success, which the
fake does not model.  It was never compared with an upstream run.

Every number below is test data, not a device fact: it is marked ``# placeholder`` and none of it is used in a Fact,
a Limit or a reference.  The simulation is R0: nothing here talks to a physical device.
"""

import math
import random

# Test data (placeholders), not device facts: the real lengths come from the robot info and the oracle layout cited
# in the module docstring.  They are marked placeholder because the fake must not be read as a second source.
ACTION_DIM = 22                              # placeholder: 6 arm + 16 hand DoF
OBS_DIM = ACTION_DIM + 10                    # placeholder: 22 joints + 3 + 3 + 3 palm values + 1 progress
HORIZON = 250                                # placeholder: laptop_env.py:147-148
INITIAL_RANGE = 0.2                          # placeholder: initial joint draw
ACTION_SCALE = 0.01                          # placeholder: integration scale of one action value
JOINT_LIMIT = 3.14                           # placeholder: a symmetric joint stand-in
CONTROL_STEP_S = 0.04                        # placeholder: frame_skip 10 times the 0.004 s physics step
REWARD = 0.0                                 # placeholder: the fake has no task reward model


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape``."""

    def __init__(self, low, high, shape=None):
        self.low = list(low) if isinstance(low, (list, tuple)) else low
        self.high = list(high) if isinstance(high, (list, tuple)) else high
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = "float32"


class FakeDexArtLaptop:
    """A kinematic stand-in for ``BaseRLEnv``: ``reset(seed, options)``, ``step(action)`` and the two spaces."""

    def __init__(self, **_options):
        self.action_space = Box([-1.0] * ACTION_DIM, [1.0] * ACTION_DIM)          # placeholder bounds
        self.observation_space = Box([-math.inf] * OBS_DIM, [math.inf] * OBS_DIM)  # placeholder bounds
        self._rng = random.Random(0)                                          # placeholder: default generator
        self._qpos = [0.0] * ACTION_DIM                                       # placeholder: start state
        self._tick = 0
        self._reset(seed=None, options=None)

    def reset(self, *, seed=None, return_info=False, options=None):
        """Start an episode and return the observation, as the laptop ``reset`` does."""
        self._reset(seed=seed, options=options)
        return self._observation()

    def step(self, action):
        """Advance one control step and return the legacy ``(obs, reward, done, info)`` four-tuple."""
        values = _action_values(action)
        if len(values) != ACTION_DIM:
            raise ValueError(f"the action must have {ACTION_DIM} values, got {len(values)}")
        previous = self._qpos
        self._qpos = [_clip(previous[index] + ACTION_SCALE * values[index], JOINT_LIMIT)
                      for index in range(ACTION_DIM)]
        self._tick += 1
        done = self._tick >= HORIZON
        info = {}
        if done:
            # base.py:226-228 records TimeLimit.truncated as not done; the fake has no early-done condition, so the
            # horizon termination reports False.
            info["TimeLimit.truncated"] = False
        return self._observation(previous), REWARD, done, info

    # -- internals ---------------------------------------------------------------
    def _reset(self, *, seed, options):
        """Draw the joint state; ``options`` is accepted but not read, as in the upstream signature."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._qpos = [self._rng.uniform(-INITIAL_RANGE, INITIAL_RANGE) for _ in range(ACTION_DIM)]
        self._tick = 0

    def _observation(self, previous=None):
        if previous is None:
            velocity = [0.0] * ACTION_DIM
        else:
            velocity = [(self._qpos[index] - previous[index]) / CONTROL_STEP_S
                        for index in range(ACTION_DIM)]
        palm_v = velocity[0:3]                                                # placeholder layout
        palm_w = velocity[3:6]                                                # placeholder layout
        palm_pose = self._qpos[6:9]                                           # placeholder layout
        progress = self._tick / HORIZON
        return list(self._qpos) + palm_v + palm_w + palm_pose + [progress]


def _action_values(action):
    """The action as a list of floats; the bridge passes a list of numbers."""
    if isinstance(action, (str, bytes)) or action is None:
        raise ValueError("the action must be a sequence of numbers")
    if hasattr(action, "tolist"):
        action = action.tolist()
    try:
        return [float(value) for value in action]
    except (TypeError, ValueError) as exc:
        raise ValueError("the action must be a sequence of numbers") from exc


def _clip(value, limit):
    return max(-limit, min(limit, value))

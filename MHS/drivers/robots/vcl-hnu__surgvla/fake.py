"""Fake backend for the SurgVLA ECMReach-v0 environment (a pure Python kinematic stand-in).

The gate must not import the upstream clone, and the upstream environment needs PyBullet, numpy and its URDF
assets, so this module re-implements the parts of ``surrol.tasks.ecm_reach:ECMReach`` that the Gymnasium bridge
uses: ``reset``, ``step``, ``seed``, ``close`` and the duck-typed action/observation spaces.  The public members are
the ones the upstream class and its SurRoL bases have (gate G7).  Every constant cites the line of the clone at the
pinned commit (9446d6544757830c8ad184a5faadcde5cd2e4905).

What this is not, and the driver's fidelity ``gaps`` also say it:

* the end effector moves kinematically by ``action * 0.01`` metres; the upstream ``dmove`` path sends that delta
  through the ECM inverse kinematics and PyBullet rigid-body dynamics with contacts (surrol/tasks/ecm_env.py:138-145);
* the orientation part of the robot state is held at zero (marked ``# placeholder`` below); the upstream reports the
  ECM pose from PyBullet;
* the goal is drawn with Python's ``random.Random``; upstream draws it with ``numpy.random`` and its ``seed()`` stores
  a generator that ``_sample_goal`` does not use;
* there is no rendering and no asset loading.

Nothing here talks to a device.
"""

import math
import random

# ECMReach.WORKSPACE_LIMITS (surrol/tasks/ecm_reach.py:12); EcmEnv.__init__ multiplies by SCALING 1.0
# (surrol/tasks/ecm_env.py:30-31, :35-36).
WORKSPACE_LIMITS = ((0.45, 0.55), (-0.05, 0.05), (0.60, 0.70))
# ECMReach._env_setup places the ECM at (workspace_limits[0][0], workspace_limits[1][1],
# workspace_limits[2][1]) (surrol/tasks/ecm_reach.py:12, :18-22).
START_POSITION = (0.45, 0.05, 0.70)
# EcmEnv._set_action in dmove mode scales every action by 0.01 * SCALING (surrol/tasks/ecm_env.py:140).
ACTION_SCALE_M = 0.01
# EcmEnv.DISTANCE_THRESHOLD = 0.005 and SCALING = 1.0 (surrol/tasks/ecm_env.py:27, :31), used at :51.
DISTANCE_THRESHOLD = 0.005
# ECMReach-v0 is registered with max_episode_steps=50 (surrol/gym/__init__.py:43-47); gym.make adds the TimeLimit.
MAX_EPISODE_STEPS = 50
# The action space is Box(-1., 1., shape=(self.action_size,)) (surrol/gym/surrol_env.py:77) and EcmEnv.ACTION_SIZE
# is 3 (surrol/tasks/ecm_env.py:25).
ACTION_SIZE = 3
# ECMReach's robot state is 6 values (position and Euler angles) and it has no object, so the observation vector is
# 6 values (surrol/tasks/ecm_env.py:93-116).
OBSERVATION_SIZE = 6


class Box:
    """Duck-typed ``gym.spaces.Box``: one lower and one upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gym.spaces.Dict``: named sub-spaces (the bridge reads ``spaces``)."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeECMReachEnv:
    """``ECMReach-v0`` without PyBullet: reset returns an observation and step returns gym.make's 5-tuple."""

    def __init__(self):
        self.action_space = Box((-1.0,) * ACTION_SIZE, (1.0,) * ACTION_SIZE)          # surrol_env.py:77
        self.observation_space = Dict({
            "desired_goal": Box((-math.inf,) * 3, (math.inf,) * 3),                   # surrol_env.py:84
            "achieved_goal": Box((-math.inf,) * 3, (math.inf,) * 3),                  # surrol_env.py:85
            "observation": Box((-math.inf,) * OBSERVATION_SIZE, (math.inf,) * OBSERVATION_SIZE),  # :86
        })
        self._rng = random.Random()
        self._seed = None
        self._pending_seed = None
        self._closed = False
        self._position = list(START_POSITION)
        self._goal = self._sample_goal()
        self._steps = 0
        self._truncated = False

    def _sample_goal(self):
        """``np.random.rand(3) * (workspace upper - lower) + lower`` (surrol/tasks/ecm_reach.py:32-34)."""
        return [self._rng.uniform(low, high) for low, high in WORKSPACE_LIMITS]

    def _get_obs(self):
        # The upstream robot state is a 3-D RCM position plus a 3-D Euler orientation
        # (surrol/tasks/ecm_env.py:93-99).  The fake keeps the world position in the first three values and a zero
        # orientation in the last three (a placeholder for the PyBullet pose).
        orientation = [0.0, 0.0, 0.0]  # placeholder
        return {
            "observation": list(self._position) + orientation,
            "achieved_goal": list(self._position),
            "desired_goal": list(self._goal),
        }

    def _is_success(self, achieved_goal, desired_goal):
        """Euclidean goal distance below ``distance_threshold`` (surrol/tasks/ecm_env.py:51, :153-157)."""
        distance = math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(achieved_goal, desired_goal)))
        return 1.0 if distance < DISTANCE_THRESHOLD else 0.0

    def compute_reward(self, achieved_goal, desired_goal, info):
        """Sparse reward: ``_is_success(...) - 1`` (surrol/tasks/ecm_env.py:73-77)."""
        return self._is_success(achieved_goal, desired_goal) - 1.0

    def seed(self, seed=None):
        """Store the seed used by the next reset; returns ``[seed]`` (surrol/gym/surrol_env.py:160-162)."""
        self._pending_seed = None if seed is None else int(seed)
        if seed is not None:
            self._seed = int(seed)
        return [seed]

    def reset(self, seed=None, options=None):
        """Reset the end effector and draw a new goal; the old gym API returns the observation (surrol_env.py:121-141).

        ``seed``/``options`` are accepted for the Gymnasium bridge: the upstream ``reset`` takes neither, and the
        bridge calls the legacy ``seed()`` fallback when a reset rejects the keyword.  ``options`` is ignored because
        ECMReach declares no scenario options.
        """
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        if seed is None:
            seed, self._pending_seed = self._pending_seed, None
        if seed is not None:
            self._rng = random.Random(int(seed))
            self._seed = int(seed)
        self._position = list(START_POSITION)
        self._goal = self._sample_goal()
        self._steps = 0
        self._truncated = False
        return self._get_obs()

    def step(self, action):
        """Apply a 3-D dmove action; return the 5-tuple ``gym.make`` produces.

        SurRoLEnv.step returns ``(obs, reward, done, info)`` (surrol/gym/surrol_env.py:109-119); gym.make wraps
        ECMReach-v0 in a TimeLimit of 50 steps (surrol/gym/__init__.py:46), which turns that into
        ``(obs, reward, done, truncated, info)``.  The bridge accepts both shapes, and the 5-tuple is the one a
        caller of the registered environment sees.
        """
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        if self._truncated:
            raise RuntimeError("the episode is over; call reset() first")
        values = [float(value) for value in action]
        if len(values) != ACTION_SIZE:
            raise ValueError(f"ECMReach takes {ACTION_SIZE} action values, got {len(values)}")
        # SurRoLEnv.step clips to the action space before applying it (surrol/gym/surrol_env.py:97).
        values = [max(-1.0, min(1.0, value)) for value in values]
        self._position = [position + value * ACTION_SCALE_M for position, value in zip(self._position, values)]
        self._steps += 1
        self._truncated = self._steps >= MAX_EPISODE_STEPS
        observation = self._get_obs()
        success = self._is_success(observation["achieved_goal"], observation["desired_goal"])
        reward = self.compute_reward(observation["achieved_goal"], observation["desired_goal"], {})
        info = {"is_success": success}
        return observation, reward, False, self._truncated, info

    def close(self):
        """Mark the environment closed; the upstream disconnects the PyBullet client (surrol_env.py:143-146)."""
        self._closed = True

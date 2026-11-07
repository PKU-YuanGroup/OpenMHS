"""Fake backend of the iCubReach driver: a pure Python stand-in for the PyBullet iCubReach-v0 environment.

Why a fake: the acceptance gate runs without Gym, PyBullet or the upstream package, and package code never imports the
clone.  The upstream package is a 2019 legacy-Gym environment (``step`` returns a four-tuple, ``reset()`` takes no
arguments); the bridge accepts that shape, so this module mirrors ``iCubReachGymEnv.reset``, ``step`` and ``seed`` and
the two Box spaces.  The public members are the ones the upstream class has (``reset``, ``step`` and ``seed``; gate
G7), and the two space classes duck-type ``gym.spaces.Box`` (the bridge reads ``low``, ``high`` and ``shape``).

The constants below are test data of this fake, not facts of the device; every one is marked ``# placeholder``.  The
observation keeps the upstream 31-element shape (a 6D hand pose, 3D linear velocity, 10 controlled joints, a 6D object
pose and a 6D object pose in the hand frame, icub_reach_gym_env.py:151-180), but the orientation, velocity, joint and
relative-orientation channels are zeros.  Nothing here talks to a device and nothing here was compared with a real
PyBullet run.
"""

import math
import random


class _Box:
    """Duck-typed ``gym.spaces.Box``: one lower and one upper bound per flattened element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


# icub_reach_gym_env.py:103-107: the action Box is bounded by -1 and 1 on every element.
_ACTION_BOUND = 1.0
# icub_reach_gym_env.py:151-180: the observation has 31 elements and is rescaled to -1..1 (utils.py:78-92).
_OBSERVATION_SIZE = 31
# icub_env.py:62: the workspace bounds before the table height adjusts the z minimum.
_WORKSPACE = [[0.1, 0.45], [-0.3, 0.3], [0.5, 1.0]]
# icub_reach_gym_env.py:52: the success threshold of the reach task.
_TARGET_DISTANCE = 0.03
# icub_reach_gym_env.py:207: a position action is multiplied by 0.005 before it is added to the hand pose.
_ACTION_SCALE = 0.005
# icub_reach_gym_env.py:67: the left-arm home hand position.
_HOME_HAND = [0.3, 0.26, 0.8]  # placeholder
# This stand-in's object pose; it is not a device fact.
_OBJECT_POSE = [0.3, 0.26, 0.7]  # placeholder
# The registration passes max_steps=1000 (pybullet_robot_envs/__init__.py:15); the fake keeps the same bound.
_MAX_STEPS = 1000  # placeholder


def _clamp(value, low, high):
    return min(high, max(low, value))


def _distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


class FakeiCubReachEnv:
    """Legacy-Gym iCubReach-v0 without Gym, PyBullet or numpy: ``reset()``, ``step(action)`` and ``seed(seed)``."""

    def __init__(self, **options):
        # The options the family driver passes are not part of the upstream environment contract; ignore them.
        del options
        self._rng = random.Random()
        self.action_space = _Box([-_ACTION_BOUND] * 3, [_ACTION_BOUND] * 3)
        self.observation_space = _Box([-_ACTION_BOUND] * _OBSERVATION_SIZE,
                                      [_ACTION_BOUND] * _OBSERVATION_SIZE)
        self._hand_position = list(_HOME_HAND)
        self._object_position = list(_OBJECT_POSE)
        self._env_step_counter = 0
        self._max_steps = _MAX_STEPS
        self.terminated = 0
        self._last_reward = 0.0
        self.reset()

    def reset(self):
        # The start jitter is test data of this fake; it makes one seed repeat a start state.
        jitter_x = self._rng.uniform(-0.01, 0.01)  # placeholder
        jitter_y = self._rng.uniform(-0.01, 0.01)  # placeholder
        self._hand_position = list(_HOME_HAND)
        self._object_position = [_OBJECT_POSE[0] + jitter_x, _OBJECT_POSE[1] + jitter_y, _OBJECT_POSE[2]]
        self._env_step_counter = 0
        self._max_steps = _MAX_STEPS
        self.terminated = 0
        self._last_reward = 0.0
        return self._observation()

    def step(self, action):
        # icub_reach_gym_env.py:204-229: scale the action, add it to the hand position and clamp to the workspace.
        for index in range(3):
            target = self._hand_position[index] + _ACTION_SCALE * float(action[index])
            self._hand_position[index] = _clamp(target, _WORKSPACE[index][0], _WORKSPACE[index][1])
        self._env_step_counter += 1

        distance = _distance(self._hand_position, self._object_position)
        success = distance <= _TARGET_DISTANCE
        if success:
            self.terminated = 1
        done = success or bool(self.terminated) or self._env_step_counter > self._max_steps

        # icub_reach_gym_env.py:319-330: the reward is minus the distance plus the success bonus.
        reward = -distance
        if success:
            reward += 1000.0 + (100.0 - distance * 80.0)
        self._last_reward = reward

        # icub_reach_gym_env.py:248-259: the legacy Gym four-tuple.
        return self._observation(), reward, bool(done), {}

    def seed(self, seed=None):
        # icub_reach_gym_env.py:261-265: the upstream seeds its generators and returns the seed in a list.
        self._rng = random.Random() if seed is None else random.Random(int(seed))
        return [seed]

    def _observation(self):
        """The 31-element observation shape of icub_reach_gym_env.py:151-180, with the unmodelled channels at zero."""
        relative = [self._object_position[index] - self._hand_position[index] for index in range(3)]
        observation = list(self._hand_position)
        observation.extend([0.0, 0.0, 0.0])                 # hand Euler orientation (placeholder)
        observation.extend([0.0, 0.0, 0.0])                 # hand linear velocity (placeholder)
        observation.extend([0.0] * 10)                      # controlled torso and arm joints (placeholder)
        observation.extend(self._object_position)
        observation.extend([0.0, 0.0, 0.0])                 # object Euler orientation (placeholder)
        observation.extend(relative)
        observation.extend([0.0, 0.0, 0.0])                 # relative Euler orientation (placeholder)
        return observation

"""Fake backend of the MIKASA-Robo BunchOfColors3-v0 driver: a pure Python kinematic stand-in.

Why a fake: the upstream class inherits ManiSkill's ``BaseEnv`` and imports ``sapien``, ``torch`` and ``mani_skill``
(bunch_of_colors.py:4-15), and those packages are not importable where the gate runs; package code never imports the
clone either.  This module implements only the members the bridge and the driver need (``reset`` and ``step``; gate
G7 checks them against ``BunchOfColors3Env``), plus duck-typed ``Box`` spaces for the bridge.

What is modelled and what is not:

* the registered step limit of 120 transitions (bunch_of_colors.py:381) is modelled;
* the action is the seven-value normalised Panda ``pd_ee_delta_pose`` command documented by the clone, each value in
  ``[-1, 1]`` (docs/source/observation_space.rst:147-172);
* the observation is a seven-value kinematic stand-in in the documented proprioception layout: absolute TCP xyz,
  roll/pitch/yaw and the gripper opening in metres (docs/source/observation_space.rst:109-129, :174-176).  The toy
  integration maps one normalized xyz command to 0.1 m and one rotation command to 0.1 rad per step, the mapping the
  clone documents (docs/source/observation_space.rst:158-165), and maps the normalized gripper command to ``[0, 0.08]``
  m (:167-176).  There is no rigid-body physics, no Panda robot, no cube scene and no ManiSkill task or reward logic.

Every number below is either cited from the clone above or marked ``# placeholder`` as fake test data.  Nothing here
talks to a device.
"""

import math
import random

# docs/source/observation_space.rst:147-149, :158-172: the 7D normalized pd_ee_delta_pose action
ACTION_SIZE = 7
ACTION_LOW, ACTION_HIGH = -1.0, 1.0
# docs/source/observation_space.rst:158-165: one xyz command maps to 0.1 m and one rotation command to 0.1 rad
XYZ_STEP_M = 0.1
ROTATION_STEP_RAD = 0.1
# docs/source/observation_space.rst:174-176: the summed finger opening is 0 to 0.08 m
GRIPPER_OPEN_M = 0.08
# mikasa_robo_suite/rl/memory_envs/bunch_of_colors.py:381: register_env("BunchOfColors3-v0", max_episode_steps=120)
MAX_EPISODE_STEPS = 120
# placeholder: the initial TCP jitter, the zero start pose and the reward are fake test data, not upstream facts
INITIAL_JITTER_M = 0.05
START_POSE = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

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
        if len(values) != len(self.low):
            return False
        return all(
            isinstance(item, (int, float)) and not isinstance(item, bool) and low <= item <= high
            for item, low, high in zip(values, self.low, self.high)
        )


def _wrap(angle, low, high):
    """Keep an angle inside its documented interval; the kinematics here are a stand-in, not a controller."""
    while angle < low:
        angle += 2.0 * math.pi
    while angle > high:
        angle -= 2.0 * math.pi
    return angle


class FakeBunchOfColors3Env:
    """The BunchOfColors3-v0 interface without ManiSkill: ``reset(seed, options)`` and ``step(action)``.

    The action space follows the documented Panda ``pd_ee_delta_pose`` controller; the observation space follows the
    documented seven-value proprioception.  ``reset`` seeds a local ``random.Random`` for the initial pose jitter only,
    so a seed repeats a trajectory of this fake; it is not ManiSkill's RNG stream.
    """

    def __init__(self, **_options):
        self.action_space = Box([ACTION_LOW] * ACTION_SIZE, [ACTION_HIGH] * ACTION_SIZE)
        # docs/source/observation_space.rst:109-129: absolute xyz (no finite clamp), rpy and gripper opening
        self.observation_space = Box(
            [-math.inf, -math.inf, -math.inf, -math.pi, -math.pi / 2.0, -math.pi, 0.0],
            [math.inf, math.inf, math.inf, math.pi, math.pi / 2.0, math.pi, GRIPPER_OPEN_M],
        )
        self._rng = random.Random()
        self._seed = None
        self._pose = list(START_POSE)                         # placeholder
        self._elapsed_steps = 0

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
                raise ValueError(f"seed must be a non-negative integer, got {seed!r}")
            self._seed = seed
            self._rng = random.Random(seed)
        # placeholder: the initial TCP jitter is fake test data; upstream perturbs the robot qpos and cube poses
        self._pose = list(START_POSE)
        self._pose[0:3] = [self._rng.uniform(-INITIAL_JITTER_M, INITIAL_JITTER_M) for _ in range(3)]
        self._elapsed_steps = 0
        return list(self._pose), {"elapsed_steps": 0}

    def step(self, action):
        if not self.action_space.contains(action):
            raise ValueError(f"action {action!r} is outside the action space")
        pose = list(self._pose)
        for index in range(3):
            pose[index] += float(action[index]) * XYZ_STEP_M
        pose[3] = _wrap(pose[3] + float(action[3]) * ROTATION_STEP_RAD, -math.pi, math.pi)
        pose[4] = _wrap(pose[4] + float(action[4]) * ROTATION_STEP_RAD, -math.pi / 2.0, math.pi / 2.0)
        pose[5] = _wrap(pose[5] + float(action[5]) * ROTATION_STEP_RAD, -math.pi, math.pi)
        pose[6] = ((float(action[6]) + 1.0) / 2.0) * GRIPPER_OPEN_M
        self._pose = pose
        self._elapsed_steps += 1
        truncated = self._elapsed_steps >= MAX_EPISODE_STEPS
        # placeholder: the reward is fake test data; the upstream reward depends on ManiSkill scene state
        return list(pose), 0.0, False, truncated, {"elapsed_steps": self._elapsed_steps}

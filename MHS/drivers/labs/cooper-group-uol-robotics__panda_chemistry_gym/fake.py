"""Fake backend of the Capping driver: a pure Python stand-in for ``custom_envs.envs:Capping_Env``.

Why a fake: the acceptance gate runs without PyBullet, gym, gym_robotics or numpy, and package code never imports the
clone.  The class name and the public members mirror the upstream class the driver names as ``native`` (``reset``,
``step`` and ``close`` of ``panda_chemistry_gym.core:RobotTaskEnv``; gate G7).  The two space helpers duck-type
``gym.spaces.Dict`` and ``gym.spaces.Box``: the bridge reads ``spaces``, ``low``, ``high`` and ``shape``.

What this is: a small kinematic model with the upstream observation layout (7 robot values + 9 cap values = 16, and
two 6-value goal vectors, ``panda.py:83-93`` and ``Capping_Task.py:152-166``) and the upstream success rule
(``distance < distance_threshold``, ``Capping_Task.py:198-201``).  It follows the old Gym API of the upstream class:
``reset`` returns an observation, ``step`` returns ``(observation, reward, done, info)`` with ``done`` only when the
registered 100-step limit is reached (``custom_envs/__init__.py:18``).

What this is not: the upstream environment.  The cap, the goal and the end-effector start are placeholders, there is
no PyBullet contact dynamics, collision response, mass, friction or mesh scene, so the cap-holder contact reward
(``Capping_Task.py:206-220``) is not modelled.  The numbers below are test data and are marked ``# placeholder``;
they are not facts, limits or references (see ``facts.md``).

Nothing here talks to a device.
"""

import math
import random

# placeholder: the end-effector start and the reachable end-effector target, in metres
EE_START = [0.0, 0.0, 0.2]
EE_TARGET = [0.1, 0.0, 0.2]
# placeholder: the fixed cap pose in the fake scene
CAP_POSITION = [0.0, 0.0, 0.05]
CAP_ROTATION = [0.0, 0.0, 0.0]
CAP_VELOCITY = [0.0, 0.0, 0.0]
# placeholder: reset jitter bound (the upstream draw is random.random() * 0.05, Capping_Task.py:172-173)
JITTER_MAX = 0.05
# placeholder: finger width start, gripper step scale and width bound
FINGER_START = 0.04
FINGER_SCALE = 0.2                                  # upstream scale: panda.py:57
FINGER_MAX = 0.08
# placeholder: end-effector displacement per action unit (upstream scale: panda.py:66)
EE_SCALE = 0.05
# placeholder: success tolerance (the upstream Capping default: Capping_Task.py:21)
DISTANCE_THRESHOLD = 0.015
# placeholder: registration max_episode_steps (custom_envs/__init__.py:18)
MAX_EPISODE_STEPS = 100


class Box:
    """Duck-typed ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = [float(value) for value in low]
        self.high = [float(value) for value in high]
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gym.spaces.Dict``: a name-to-space mapping (the bridge reads ``spaces``)."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _distance(left, right):
    return math.sqrt(sum((a - b) * (a - b) for a, b in zip(left, right)))


class FakeCappingEnv:
    """Capping without PyBullet: ``reset(seed, options)`` and ``step(action)`` return what the old Gym env returns."""

    def __init__(self, render=False, reward_type="sparse", control_type="ee"):
        if render:
            raise ValueError("the fake Capping environment cannot render; use render=False")
        if control_type != "ee":
            raise ValueError("the fake Capping environment serves the ee control variant only")
        if reward_type not in ("sparse", "dense"):
            raise ValueError("reward_type must be 'sparse' or 'dense'")
        self.reward_type = reward_type
        self.control_type = control_type
        # placeholder shape: the ee/sparse Capping-v1 action space (panda.py:22-24, core.py:253)
        self.action_space = Box([-1.0] * 4, [1.0] * 4)
        # placeholder shape: the upstream Dict observation space (core.py:245-251)
        self.observation_space = Dict({
            "observation": Box([-200.0] * 16, [200.0] * 16),
            "desired_goal": Box([-200.0] * 6, [200.0] * 6),
            "achieved_goal": Box([-200.0] * 6, [200.0] * 6),
        })
        self._rng = random.Random(0)
        self._ee = list(EE_START)
        self._fingers = FINGER_START
        self._cap = list(CAP_POSITION)
        self._goal = list(CAP_POSITION) + list(EE_TARGET)
        self._tick = 0
        self._closed = False

    def reset(self, seed=None, options=None):
        """Reset the fake scene; ``seed`` reseeds the placement jitter and ``options`` is accepted and ignored."""
        if self._closed:
            raise RuntimeError("the fake Capping environment is closed")
        if seed is not None:
            if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
                raise ValueError("seed must be a non-negative integer")
            self._rng = random.Random(seed)
        # options is accepted because the bridge offers it; the upstream reset has no options parameter
        jitter = [self._rng.uniform(0.0, JITTER_MAX), self._rng.uniform(0.0, JITTER_MAX), 0.0]
        self._cap = [CAP_POSITION[axis] + jitter[axis] for axis in range(3)]
        # the achieved goal's first three values are the cap position, so only the end effector must reach the goal
        self._goal = list(self._cap) + list(EE_TARGET)
        self._ee = list(EE_START)
        self._fingers = FINGER_START
        self._tick = 0
        return self._obs()

    def step(self, action):
        """Apply one action in the fake scene and return the old Gym four-tuple."""
        if self._closed:
            raise RuntimeError("the fake Capping environment is closed")
        values = [float(value) for value in action]
        if len(values) != 4:
            raise AssertionError(f"the Capping action has 4 values, got {len(values)}")
        for value in values:
            if not -1.0 <= value <= 1.0:
                raise AssertionError(f"action value {value!r} is outside the Box(-1, 1) action space")
        for axis in range(3):
            self._ee[axis] += EE_SCALE * values[axis]
        self._fingers = min(FINGER_MAX, max(0.0, self._fingers + FINGER_SCALE * values[3]))
        self._tick += 1
        observation = self._obs()
        distance = _distance(observation["achieved_goal"], observation["desired_goal"])
        success = distance < DISTANCE_THRESHOLD
        reward = 1.0 if success else -distance
        done = self._tick >= MAX_EPISODE_STEPS
        info = {"is_success": success, "TimeLimit.truncated": done}
        return observation, float(reward), done, info

    def close(self):
        self._closed = True

    def _obs(self):
        """The upstream observation layout: 7 robot values, 9 cap values, and two 6-value goals."""
        robot = list(self._ee) + [0.0, 0.0, 0.0] + [self._fingers]
        cap = list(self._cap) + list(CAP_ROTATION) + list(CAP_VELOCITY)
        return {
            "observation": robot + cap,
            "achieved_goal": list(self._cap) + list(self._ee),
            "desired_goal": list(self._goal),
        }

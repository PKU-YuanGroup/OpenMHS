"""Analytic fake backend for the MARA-v0 environment of gh.acutronicrobotics/gym-gazebo2.

``MARAEnv`` is a legacy OpenAI Gym environment (gym_gazebo2/envs/MARA/mara.py:40).
The fake preserves that native surface before the SDK bridge adapts it: ``reset()``
returns one observation, ``step(action)`` returns ``(obs, reward, done, info)``,
``seed(seed)`` returns ``[seed]``, and ``close()`` exists.  The bridge in
``mhs.bridge.gymnasium`` recognizes the legacy four-tuple and the observation-only
reset, so the adaptation lives in the production adapter, not here.

This fake is an analytic kinematic stand-in, not a recording: it replays no
captured Gazebo or ROS 2 traffic.  It implements no Gazebo, ROS 2, URDF, KDL or
physics; it moves each joint a placeholder fraction toward the commanded
position and builds a 24-value
observation in the upstream concatenation order (mara.py:272-276).  Every number
below is test data: the action-space bounds copy the upstream Box(-pi, pi)
(mara.py:169-172), and the driver cites that line as ``action_space_ref``; the
rest are marked ``# placeholder`` and are never facts, limits or references.
"""

import math
import random

# placeholder: MARA has six joints in the environment's joint order (mara.py:123-124)
JOINT_COUNT = 6
# placeholder: the upstream observation dimension for those six joints (mara.py:164)
OBSERVATION_SIZE = 24
# placeholder: fraction of the remaining distance to the commanded position a fake joint covers per step;
# upstream sends the action as absolute JointTrajectoryPoint.positions (ut_mara.py:84-102)
TRACKING_FRACTION = 0.5
# placeholder: the random joint offset a fresh episode starts from
RESET_JITTER = 0.02
# placeholder: reward the fake reports; the upstream reward is ut_math.computeReward
REWARD = -1.0
# placeholder: the upstream default max_episode_steps (mara.py:77-77)
MAX_EPISODE_STEPS = 1024


class Box:
    """Duck-typed ``gym.spaces.Box``: flat ``low``/``high`` and a shape."""

    def __init__(self, low, high):
        self.low = low
        self.high = high
        self.shape = (len(low),)
        self.dtype = "float32"


class FakeGymGazebo2:
    """The public surface of ``MARAEnv`` with a small kinematic model instead of Gazebo.

    The action space is the upstream ``Box(-pi, pi)`` over six joints
    (mara.py:169-172).  The observation space is the upstream infinite Box over
    the 24-value observation (mara.py:164, 174-176).  One ``step`` is one
    environment transition, not one Gazebo physics step.
    """

    def __init__(self, **_options):
        self._options = dict(_options)
        self.action_space = Box([-math.pi] * JOINT_COUNT, [math.pi] * JOINT_COUNT)
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE)
        self.max_episode_steps = MAX_EPISODE_STEPS
        self.iterator = 0
        self._seed = None
        self._rng = random.Random(0)  # placeholder
        self._joints = [0.0] * JOINT_COUNT  # placeholder
        self._closed = False

    def reset(self):
        """Reset the fake episode and return the observation only, as the upstream reset does."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        self.iterator = 0
        self._joints = [self._rng.uniform(-RESET_JITTER, RESET_JITTER) for _ in range(JOINT_COUNT)]
        return self._observation()

    def seed(self, seed=None):
        """Seed the placeholder reset generator; the upstream returns ``[seed]``."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        self._seed = seed
        self._rng = random.Random(seed)
        return [seed]

    def step(self, action):
        """Apply one action and return the legacy ``(obs, reward, done, info)`` tuple."""
        if self._closed:
            raise RuntimeError("the fake environment is closed")
        values = list(action.tolist() if hasattr(action, "tolist") else action)
        if len(values) != JOINT_COUNT:
            raise ValueError(f"action has {len(values)} values; the action space has {JOINT_COUNT}")
        for index, value in enumerate(values):
            number = float(value)
            if not math.isfinite(number):
                raise ValueError("action values must be finite")
            self._joints[index] += (number - self._joints[index]) * TRACKING_FRACTION
        self.iterator += 1
        done = self.iterator == self.max_episode_steps  # upstream compares with == (mara.py:325)
        return self._observation(), REWARD, done, {}

    def close(self):
        self._closed = True

    def _observation(self):
        """A 24-value placeholder in the upstream concatenation order (mara.py:272-276)."""
        joints = list(self._joints)
        ee_error = [self._joints[0], self._joints[1], 0.0]  # placeholder
        ee_velocities = [0.0, 0.0, 0.0]  # placeholder
        current_ee = [0.25, 0.0, 0.25]  # placeholder
        rotation = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]  # placeholder identity
        return joints + ee_error + ee_velocities + current_ee + rotation

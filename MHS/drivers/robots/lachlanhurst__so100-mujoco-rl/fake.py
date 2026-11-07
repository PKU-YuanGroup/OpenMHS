"""Fake backend of the Gymnasium driver: a pure-Python stand-in for the upstream ``Env01`` (Env01-v1).

Why a fake: the acceptance gate runs without the upstream package (it needs mujoco, gymnasium, numpy and Python 3.11
or newer, pyproject.toml:4-18), and package code never imports the clone.  This module is a kinematic stand-in for
``so100_mujoco_rl.envs.env01_v1:Env01`` (the class the driver names as ``native``): it implements the two public
methods the bridge calls (``reset`` and ``step``), the six-element ``Box(-1, 1)`` action space and the fifteen-element
observation space of the clone.  Gate G7 checks the fake's public members against the upstream class.

What this is not: the upstream MuJoCo environment.  The differences are listed in the fidelity ``gaps`` of the driver:

* the joint motion is a direct increment with the clone's scale (utils.py:9), not a position-actuator response in a
  rigid-body simulation;
* the end effector comes from a small forward-kinematics stand-in, not from MuJoCo body poses;
* the fake seeds Python's ``random.Random(seed)`` for the reset draws, while the clone uses numpy's global generator
  (env01_v1.py:45-55), so the fake repeats a trajectory for a seed and the upstream model does not;
* every number in this file is test data (``# placeholder``), not a fact about the device.

Nothing here talks to a device.
"""

import math
import random

# placeholder: the six joint names, in the order the clone's joints_from_model keeps them (utils.py:64-89 and the
# joint declarations in so_arm100_camera.xml:75, :82, :89, :96, :103, :115).
JOINT_NAMES = ("Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll", "Jaw")
# placeholder: the joint ranges of so_arm100_camera.xml:35, :38, :41, :44, :47 and :50.
JOINT_LOW = (-2.2, -3.14158, 0.0, -2.0, -3.14158, -0.2)
JOINT_HIGH = (2.2, 0.2, 3.14158, 1.8, 3.14158, 2.0)
# placeholder: JOINT_STEP_SCALE from utils.py:9.
JOINT_STEP_SCALE = 0.075
# placeholder: max_episode_steps of Env01-v1 from src/so100_mujoco_rl/__init__.py:8.
MAX_EPISODE_STEPS = 4000
# placeholder: the block-distance bounds of env01_v1.py:45.
BLOCK_DISTANCE_MIN = 0.18
BLOCK_DISTANCE_MAX = 0.42
# placeholder: the start poses of VALID_START_POSITIONS (utils.py:13-50), reduced to six representative rows.
START_POSITIONS = [
    [0.116, -2.848, 1.84, 1.198, -1.598, 0.191],
    [0.11504855751991272, -3.0602917671203613, 2.4727771282196045, -0.5859806537628174, -1.5968739986419678,
     0.18762288987636566],
    [0.11658254265785217, -3.049553871154785, 2.420621633529663, 0.09817477315664291, -1.5846021175384521,
     0.19053177535533905],
    [0.03374757617712021, -2.932971239089966, 0.03067961521446705, 0.5905826091766357, -2.4190876483917236,
     0.18907733261585236],
    [1.0154953002929688, -3.1293208599090576, 0.5046796798706055, -1.3406991958618164, -1.7195924520492554,
     0.19198621809482574],
    [-0.5077476501464844, -2.7765052318573, 0.00920388475060463, -1.0860583782196045, -1.718058466911316,
     0.19198621809482574],
]


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element (the bridge reads low/high)."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeEnv01:
    """A kinematic Env01-v1 stand-in: ``reset(seed, options)`` and ``step(action)`` return what gymnasium's do."""

    def __init__(self, **options):
        # placeholder: the six-element action space of env_base_01.py:77-83.
        self.action_space = Box([-1.0] * 6, [1.0] * 6)
        # placeholder: observation bounds of env_base_01.py:63-75 (six joint ranges, three +-1 offsets and six +-0.5
        # positions).
        low = [*JOINT_LOW, -1.0, -1.0, -1.0, -0.5, -0.5, -0.5, -0.5, -0.5, -0.5]
        high = [*JOINT_HIGH, 1.0, 1.0, 1.0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        self.observation_space = Box(low, high)
        self._rng = random.Random(0)
        self._joints = [0.0] * 6
        self._block = [0.0, 0.0, 0.0]
        self._end = [0.0, 0.0, 0.0]
        self._steps = 0

    # placeholder: a small forward-kinematics stand-in; the upstream end effector comes from MuJoCo body poses
    # (env_base_01.py:118-127).  It is not a model of the arm geometry.
    def _end_effector(self):
        a0, a1, a2 = self._joints[0], self._joints[1], self._joints[2]
        reach = 0.18 + 0.08 * math.cos(a1) + 0.06 * math.cos(a1 + a2)
        x = reach * math.cos(a0)
        y = reach * math.sin(a0) - 0.10
        z = 0.10 + 0.10 * math.sin(a1) + 0.08 * math.sin(a1 + a2)
        return [x, y, z]

    def _get_obs(self):
        block = self._block
        end = self._end
        return [
            *self._joints,
            block[0] - end[0],
            block[1] - end[1],
            block[2] - end[2],
            *block,
            *end,
        ]

    def reset(self, *, seed=None, options=None):
        """Like ``Env01.reset`` through ``MujocoEnv.reset``: a full reset returns ``(observation, {})``."""
        if seed is not None:
            self._rng = random.Random(int(seed))
        distance = self._rng.uniform(BLOCK_DISTANCE_MIN, BLOCK_DISTANCE_MAX)
        theta = -0.5 * math.pi + self._rng.uniform(-0.25 * math.pi, 0.25 * math.pi)
        self._block = [distance * math.cos(theta), distance * math.sin(theta), 0.0]
        start = START_POSITIONS[self._rng.randrange(len(START_POSITIONS))]
        self._joints = [float(start[i]) for i in range(6)]
        self._steps = 0
        self._end = self._end_effector()
        return self._get_obs(), {}

    def step(self, action):
        """Like ``Env01.step``: advance one environment step and return gymnasium's five-tuple."""
        values = list(action)
        if len(values) != 6:
            raise ValueError(f"Env01 expects six action values, got {len(values)}")
        for index, value in enumerate(values):
            target = self._joints[index] + float(value) * JOINT_STEP_SCALE
            self._joints[index] = min(JOINT_HIGH[index], max(JOINT_LOW[index], target))
        self._steps += 1
        self._end = self._end_effector()
        distance = math.sqrt(
            (self._block[0] - self._end[0]) ** 2
            + (self._block[1] - self._end[1]) ** 2
            + (self._block[2] - self._end[2]) ** 2
        )
        reward = -distance                      # placeholder: the clone's reward is BASE:180-239
        terminated = False                      # the clone always returns terminated=False (env01_v1.py:29-37)
        truncated = self._steps >= MAX_EPISODE_STEPS
        return self._get_obs(), reward, terminated, truncated, {}

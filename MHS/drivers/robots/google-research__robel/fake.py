"""Fake backend of the ROBEL DClaw pose driver: a pure Python stand-in for ``DClawPoseFixed-v0``.

Why a fake: the acceptance gate runs without MuJoCo, mujoco-py, gym and numpy (the upstream package needs all of
them, ``setup.py`` and ``requirements.txt``), and package code never imports the clone.  This module mirrors the
public surface the Gymnasium bridge needs, not the upstream package: ``reset``, ``step``, ``seed``, ``close`` and
``dt`` are the public members of ``robel.dclaw.pose:DClawPoseFixed`` and its bases that this fake re-implements
(gate G7).  The two space classes duck-type the parts of ``gym.spaces.Box`` the bridge reads (``low``, ``high``,
``shape`` and ``dtype``).

What is modelled, each from a line of the clone at commit 5b0fd3704629931712c6e0f7268ace1c2154dc83:

* the action space is normalized to ``[-1.0, 1.0]`` over nine joints (``robel/dclaw/base_env.py:118-121``);
* a normalized action is mapped to the joint-position range, then clipped to the joint and velocity ranges
  (``robel/components/robot/robot.py:218-228`` and ``:242-261``);
* the default observation is qpos, last_action and qpos_error concatenated (``robel/dclaw/pose.py:33-38``,
  ``robel/dclaw/pose.py:98-105``, ``robel/robot_env.py:511-517``);
* the pose reward is ``-||qpos_error|| - 0.1 * ||qvel[abs(qvel) >= pi]||`` (``robel/dclaw/pose.py:112-126``);
* a reset draws a random initial pose and a random desired pose (``robel/dclaw/pose.py:168-172``), with the
  middle joints' upper bound clamped to zero (``robel/dclaw/pose.py:148-156``);
* the step duration is the 2.5 ms timestep of the pose episode times the default frame_skip 20
  (``robel/dclaw/__init__.py:24``, ``robel/dclaw/pose.py:52-56``).

What is not: MuJoCo.  The fake integrates the clipped desired joint velocity directly; it resolves no contacts,
actuator forces, gear friction, sensors or observation noise, and it does not reproduce the numpy random stream.
Those differences are in the driver's fidelity ``gaps``.  Every number that is a model choice rather than a line
of the clone is marked ``# placeholder``.
"""

import math
import random

# robel/dclaw/__init__.py:24: _POSE_EPISODE_LEN = 80  # 80*20*2.5ms = 4s
TIMESTEP = 0.0025
# robel/dclaw/pose.py:55: frame_skip: int = 20
FRAME_SKIP = 20
# robel/robot_env.py:174-177: the step duration is sim_scene.step_duration = model timestep * frame_skip
STEP_DURATION = TIMESTEP * FRAME_SKIP

# robel/dclaw/base_env.py:101-105: the position range of each of the three servos, repeated for three fingers.
QPOS_RANGES = [(-0.48, 0.48), (-math.pi / 3, math.pi / 3), (-math.pi / 2, math.pi / 2)] * 3
# robel/dclaw/base_env.py:106: qvel_range=[(-2 * PI / 3, 2 * PI / 3)] * 9
QVEL_LIMIT = 2 * math.pi / 3
# robel/dclaw/base_env.py:121: make_box_space(-1.0, 1.0, shape=(qpos_indices.size,))
ACTION_LOW, ACTION_HIGH = -1.0, 1.0
# robel/dclaw/pose.py:34-38: the three observation keys concatenated into the flat observation.
OBSERVATION_KEYS = ("qpos", "last_action", "qpos_error")
JOINTS = len(QPOS_RANGES)


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class FakeDClawPoseFixed:
    """A kinematic stand-in for ``DClawPoseFixed`` that returns the legacy gym 4-tuple from ``step``."""

    def __init__(self):
        self.action_space = Box([ACTION_LOW] * JOINTS, [ACTION_HIGH] * JOINTS)
        # robel/robot_env.py:425-438: the observation space is a Box from -inf to +inf with the observation shape.
        self.observation_space = Box([-math.inf] * (JOINTS * len(OBSERVATION_KEYS)),
                                     [math.inf] * (JOINTS * len(OBSERVATION_KEYS)))
        # seed(None) picks an arbitrary start; the value is test data, not a device fact.  # placeholder
        self._rng = random.Random()
        self._qpos = None
        self._qvel = None
        self._last_action = None
        self._desired = None
        self._steps = 0

    @property
    def dt(self):
        """The step duration in seconds (``robel/robot_env.py:174-177``)."""
        return STEP_DURATION

    def seed(self, seed=None):
        """Seeds the generator used by the next reset (``robel/robot_env.py:196-204``)."""
        if seed is None:
            seed = self._rng.randrange(0, 2 ** 31)  # placeholder: any non-negative seed
        self._rng = random.Random(int(seed))
        return [int(seed)]

    def _make_random_pose(self):
        """Draws a pose the way ``_make_random_pose`` does (``robel/dclaw/pose.py:148-156``)."""
        ranges = list(QPOS_RANGES)
        # pose.py:154: random_range[[1, 4, 7], 1] = 0, the middle joints only go outwards.
        for index in (1, 4, 7):
            low, high = ranges[index]
            ranges[index] = (low, min(high, 0.0))
        return [self._rng.uniform(low, high) for low, high in ranges]

    def _observation(self):
        """The flat qpos + last_action + qpos_error observation (``robel/dclaw/pose.py:33-38``)."""
        last_action = [0.0] * JOINTS if self._last_action is None else list(self._last_action)
        qpos_error = [desired - position for desired, position in zip(self._desired, self._qpos)]
        return list(self._qpos) + last_action + qpos_error

    def reset(self):
        """Starts an episode: a random initial pose and a random desired pose (``robel/dclaw/pose.py:168-172``)."""
        self._qpos = self._make_random_pose()
        self._desired = self._make_random_pose()
        self._qvel = [0.0] * JOINTS
        self._last_action = None  # robel/robot_env.py:216: reset clears the last action.
        self._steps = 0
        return self._observation()

    def step(self, action):
        """Applies one normalized action and returns the legacy ``(obs, reward, done, info)`` tuple."""
        if self._qpos is None:
            raise AssertionError("Call reset before using step method.")
        values = [float(value) for value in action]
        if len(values) != JOINTS:
            raise AssertionError(f"expected {JOINTS} action values, got {len(values)}")
        # robel/robot_env.py:486 and robel/components/robot/robot.py:227: clip to the normalized action space.
        values = [max(ACTION_LOW, min(ACTION_HIGH, value)) for value in values]
        # robel/components/robot/robot.py:228: center + action * half-range.
        targets = []
        for value, (low, high) in zip(values, QPOS_RANGES):
            center = 0.5 * (low + high)
            half_range = 0.5 * (high - low)
            target = center + value * half_range
            # robel/components/robot/robot.py:245-246: clip the joint-position command to the qpos range.
            targets.append(max(low, min(high, target)))
        # robel/components/robot/robot.py:255-261: clip the desired velocity to the qvel range.  This is the
        # placeholder integration: MuJoCo would drive the joint toward the target through its actuator model.
        velocity = []
        for position, target in zip(self._qpos, targets):
            speed = (target - position) / STEP_DURATION
            velocity.append(max(-QVEL_LIMIT, min(QVEL_LIMIT, speed)))
        self._qpos = [position + speed * STEP_DURATION for position, speed in zip(self._qpos, velocity)]
        self._qvel = velocity
        self._last_action = values
        self._steps += 1

        observation = self._observation()
        # robel/dclaw/pose.py:120-124: the pose error cost plus the high-velocity cost.
        qpos_error = observation[2 * JOINTS:]
        pose_error_cost = -math.sqrt(sum(value * value for value in qpos_error))
        joint_vel_cost = -0.1 * math.sqrt(
            sum(value * value for value in self._qvel if abs(value) >= math.pi))
        reward = pose_error_cost + joint_vel_cost
        return observation, reward, False, {}

    def close(self):
        """Releases the fake state (``robel/robot_env.py:332-337``)."""
        self._qpos = None
        self._qvel = None
        self._last_action = None
        self._desired = None

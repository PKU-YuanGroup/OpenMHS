"""Fake backend of the dexterous-gym driver: a pure Python stand-in for the registered ``EggHandOver-v0``.

Why a fake: the upstream environment needs old Gym 0.15.3 and MuJoCo 2.0 (README.md:4-15), which are not installed
where the gate runs, and package code never imports the clone.  This module models the registered environment's
interface, not its physics: the action space is ``Box(-1, 1, shape=(40,))`` (``two_hand_robot_env.py:45`` with
``two_hands_env.py:54-57``), the observation is the dictionary ``observation``/``achieved_goal``/``desired_goal``
(``two_hands_env.py:228-263``), and a step advances one 40 ms control period (model timestep 0.002 s at
``egg_handover.xml:4`` times the default 20 substeps at ``two_hands_env.py:20``).

The public members are the ones the upstream class has (``reset``, ``step``, ``seed``, ``close``, the ``dt`` property;
gate G7); the two space classes duck-type ``gym.spaces.Box`` and ``gym.spaces.Dict``.  Numbers below are test data, not
sources: every one is marked ``# placeholder``.  They are not facts and nothing here is evidence about the real
environment.

What this is not (all listed in the driver's fidelity ``gaps``):

* no MuJoCo: hands are driven kinematically and the object does not move;
* the initial rotation and goal are drawn with Python's ``random.Random``, upstream uses gym's numpy generator;
* the legacy Gym API returns a 4-tuple from ``step`` and no truncation; this fake returns the Gymnasium 5-tuple and
  applies the registered 75-step limit itself;
* observations are plain lists, not float32 numpy arrays.

Nothing here talks to a device.
"""

import math
import random

# placeholder: the 40 actuators of the two fixed hands (upstream two_hands_env.py:54-57)
N_ACTIONS = 40
# placeholder: 24 joints and 20 actuated joints per hand in egg_handover.xml, used only to shape the fake observation
N_JOINTS = 24
N_ACTUATED = 20
# placeholder: 2 hands x (24 qpos + 24 qvel) + object 7 qpos + 6 qvel
OBS_SIZE = 109
GOAL_SIZE = 7
# placeholder: registered max_episode_steps (dexterous_gym/__init__.py:9)
MAX_EPISODE_STEPS = 75
# placeholder: model timestep 0.002 s (egg_handover.xml:4) and default n_substeps 20 (two_hands_env.py:20)
TIMESTEP_S = 0.002
N_SUBSTEPS = 20
# placeholder: a joint-position delta per unit of action, chosen for the fake only
ACTION_SCALE = 0.5
# placeholder: upstream default dist_multiplier 20.0 (egg_hand_over.py:14) and thresholds 0.01/0.1 (lines 13-14)
DIST_MULTIPLIER = 20.0
DISTANCE_THRESHOLD = 0.01
ROTATION_THRESHOLD = 0.1
# placeholder: upstream default goal ranges (egg_hand_over.py:8-9), used as fake test data
RANGE_1 = ((0.96, 1.04), (0.81, 0.89), (0.20, 0.26))
RANGE_2 = ((0.96, 1.04), (0.60, 0.68), (0.20, 0.26))
# placeholder: an object start pose for the fake only
OBJECT_START = (1.0, 0.75, 0.23, 1.0, 0.0, 0.0, 0.0)


class Box:
    """Duck-typed one-dimensional ``gym.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, shape=None, dtype="float32"):
        if shape is None:
            shape = (len(low),) if isinstance(low, (list, tuple)) else ()
        self.shape = tuple(int(item) for item in shape)
        count = 1
        for item in self.shape:
            count *= item
        self.low = list(low) if isinstance(low, (list, tuple)) else [float(low)] * count
        self.high = list(high) if isinstance(high, (list, tuple)) else [float(high)] * count
        self.dtype = dtype


class Dict:
    """Duck-typed ``gym.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _dot(a, b):
    return sum(left * right for left, right in zip(a, b))


def _norm(a):
    return math.sqrt(_dot(a, a))


def _quat_from_angle_and_axis(angle, axis):
    """The quaternion [w, x, y, z] of an angle about an axis (two_hands_env.py:11-16)."""
    length = _norm(axis)
    if length == 0.0:
        axis = [0.0, 0.0, 1.0]
        length = 1.0
    axis = [item / length for item in axis]
    half = angle / 2.0
    quat = [math.cos(half), *(math.sin(half) * item for item in axis)]
    norm = _norm(quat)
    return [item / norm for item in quat]


def _quat_conjugate(quat):
    return [quat[0], -quat[1], -quat[2], -quat[3]]


def _quat_mul(a, b):
    """Hamilton product in [w, x, y, z] order (the gym rotations convention)."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return [
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    ]


def _distance(a, b):
    return math.sqrt(sum((left - right) ** 2 for left, right in zip(a, b)))


class FakeEggHandOver:
    """Pure Python stand-in for ``gym.make("EggHandOver-v0")`` on the legacy Gym API plus its time limit."""

    def __init__(self, **options):
        if options:
            raise ValueError(f"the fake EggHandOver takes no options, got {sorted(options)}")
        self.action_space = Box([-1.0] * N_ACTIONS, [1.0] * N_ACTIONS, shape=(N_ACTIONS,), dtype="float32")
        self.observation_space = Dict({
            "desired_goal": Box([-math.inf] * GOAL_SIZE, [math.inf] * GOAL_SIZE, shape=(GOAL_SIZE,)),
            "achieved_goal": Box([-math.inf] * GOAL_SIZE, [math.inf] * GOAL_SIZE, shape=(GOAL_SIZE,)),
            "observation": Box([-math.inf] * OBS_SIZE, [math.inf] * OBS_SIZE, shape=(OBS_SIZE,)),
        })
        self._rng = random.Random(0)                 # placeholder
        self._hand = [[0.0] * N_JOINTS for _ in range(2)]       # placeholder
        self._hand_qvel = [[0.0] * N_JOINTS for _ in range(2)]  # placeholder
        self._object = list(OBJECT_START)
        self._object_qvel = [0.0] * 6                # placeholder
        self._goal = list(OBJECT_START)
        self._elapsed = 0

    @property
    def dt(self):
        return TIMESTEP_S * N_SUBSTEPS

    def seed(self, seed=None):
        self._rng = random.Random(seed)
        return [seed]

    def reset(self):
        self._elapsed = 0
        self._hand = [[0.0] * N_JOINTS for _ in range(2)]       # placeholder
        self._hand_qvel = [[0.0] * N_JOINTS for _ in range(2)]  # placeholder
        self._object = list(OBJECT_START)
        self._object_qvel = [0.0] * 6                # placeholder
        angle = self._rng.uniform(-math.pi, math.pi)
        axis = [self._rng.uniform(-1.0, 1.0) for _ in range(3)]
        self._object[3:] = _quat_mul(self._object[3:], _quat_from_angle_and_axis(angle, axis))
        self._goal = self._sample_goal()
        return self._observation()

    def step(self, action):
        values = list(action)
        if len(values) != N_ACTIONS:
            raise ValueError(f"the action must have {N_ACTIONS} values, got {len(values)}")
        # placeholder: a kinematic response only; the upstream action drives MuJoCo actuator ctrlranges
        for hand in range(2):
            for joint in range(N_ACTUATED):
                target = max(-1.0, min(1.0, values[hand * N_ACTUATED + joint])) * ACTION_SCALE
                self._hand_qvel[hand][joint] = (target - self._hand[hand][joint]) / self.dt
                self._hand[hand][joint] = target
        self._elapsed += 1
        success = self._success()
        reward = self._reward()
        return self._observation(), reward, False, self._elapsed >= MAX_EPISODE_STEPS, {"is_success": success}

    def close(self):
        self._elapsed = 0

    def _observation(self):
        hand_1 = self._hand[0] + self._hand_qvel[0]
        hand_2 = self._hand[1] + self._hand_qvel[1]
        obj = self._object + self._object_qvel
        return {
            "observation": hand_1 + hand_2 + obj,
            "achieved_goal": list(self._object),
            "desired_goal": list(self._goal),
        }

    def _sample_goal(self):
        # placeholder: the upstream mean-of-range side choice (two_hands_env.py:184-197), with fake test data
        positions = ([1.0, 0.85, 0.23], [1.0, 0.64, 0.23])
        distances = [_distance(self._object[:3], item) for item in positions]
        ranges = RANGE_1 if distances[0] > distances[1] else RANGE_2
        position = [self._rng.uniform(low, high) for low, high in ranges]
        angle = self._rng.uniform(-math.pi, math.pi)
        axis = [self._rng.uniform(-1.0, 1.0) for _ in range(3)]
        return position + _quat_from_angle_and_axis(angle, axis)

    def _goal_distance(self):
        d_pos = _distance(self._object[:3], self._goal[:3])
        quat = _quat_mul(self._object[3:], _quat_conjugate(self._goal[3:]))
        d_rot = 2.0 * math.acos(max(-1.0, min(1.0, quat[0])))
        return d_pos, d_rot

    def _success(self):
        d_pos, d_rot = self._goal_distance()
        return d_pos < DISTANCE_THRESHOLD and d_rot < ROTATION_THRESHOLD

    def _reward(self):
        d_pos, d_rot = self._goal_distance()
        return math.exp(-(DIST_MULTIPLIER * d_pos + d_rot))

"""Fake backend of the SIMPLE Gymnasium driver: a pure Python kinematic stand-in for ``TabletopGraspEnv``.

The upstream environment (``simple.envs.tabletop_grasp:TabletopGraspEnv``) builds a MuJoCo simulator and, when the
mode contains ``isaac``, an Isaac Sim application; it needs Python 3.10, MuJoCo 3.3.6, IsaacSim 4.5 and an RTX GPU
(pyproject.toml, README.md).  The gate has none of that and package code never imports the clone, so this module
implements the public environment interface of ``TabletopGraspEnv`` in plain Python: ``reset``, ``step`` and
``close`` (gate G7 checks those names against the upstream class), plus the ``action_space`` and
``observation_space`` instance attributes that ``BaseDualSim.__init__`` sets.

The action space mirrors the upstream controller configuration: a ``Dict`` with one ``arm`` entry, a 7-joint
``Box`` bounded by -1.0 and 1.0, and the observation space mirrors the task's scalar observation entries
(``agent`` and ``joint_qpos`` with 9 entries in [-pi, pi], ``eef_pose`` with 7 entries).  Those numbers are cited in
the facts of ``driver.py``; every other number in this module is placeholder test data of the stand-in and is not a
device fact.

What this is not: the upstream environment.  It has no MuJoCo dynamics, contacts, rendering, camera images,
domain randomisation, assets or scenes.  The real camera observations are 640 x 360 for ``front_stereo_left``,
``front_stereo_right`` and ``side_left`` and 480 x 270 for ``wrist`` and ``wrist_left`` (the task's sensor configs);
this fake returns only the scalar state entries and does not declare the camera spaces.  The differences are listed
in the fidelity ``gaps`` of the driver.  Nothing here talks to a device.
"""

import math
import random

# Action and observation space shape of the upstream configuration (facts in driver.py): the arm controller has
# joint1..joint7, the robot has 9 degrees of freedom (7 arm joints and 2 finger joints) and each arm action is
# bounded by -1.0 and 1.0.
ARM_JOINTS = 7
ROBOT_DOF = 9
ARM_LOW, ARM_HIGH = -1.0, 1.0
OBS_LOW, OBS_HIGH = -math.pi, math.pi

# Placeholder test data of the kinematic stand-in; none of these is a device fact.
ARM_START = [0.0] * ARM_JOINTS                       # placeholder
FINGER_START = [0.04, 0.04]                          # placeholder
JOINT_DELTA = 0.01                                   # placeholder
LIFT_DELTA = 0.004                                   # placeholder
JITTER = 0.001                                       # placeholder
LIFT_HEIGHT = 0.02                                   # placeholder (the reward scale used by the fake)
EEF_X, EEF_Y, EEF_Z = 0.4, 0.0, 0.5                  # placeholder


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: named subspaces (the bridge reads ``spaces``)."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.dtype = "dict"


class FakeTabletopGraspEnv:
    """The scalar part of ``TabletopGraspEnv`` without MuJoCo: ``reset(seed, options)`` and ``step(action)``.

    The observation is the subset of the upstream ``_get_obs`` result that does not need rendering:
    ``agent``, ``joint_qpos`` and ``eef_pose``.  The info maps the target object to its pose, as the upstream
    ``_get_info`` maps every MuJoCo object to ``[x, y, z, qw, qx, qy, qz]``.
    """

    def __init__(self, **options):
        # The upstream __init__ takes task, sim_mode, headless and more; the fake ignores them and builds no engine.
        self._options = dict(options)
        self.action_space = Dict({"arm": Box([ARM_LOW] * ARM_JOINTS, [ARM_HIGH] * ARM_JOINTS)})
        self.observation_space = Dict({
            "agent": Box([OBS_LOW] * ROBOT_DOF, [OBS_HIGH] * ROBOT_DOF),
            "joint_qpos": Box([OBS_LOW] * ROBOT_DOF, [OBS_HIGH] * ROBOT_DOF),
            "eef_pose": Box([-math.inf] * 7, [math.inf] * 7),
        })
        self._qpos = list(ARM_START) + list(FINGER_START)   # placeholder
        self._target_z = 0.0                                # placeholder
        self._init_target_z = 0.0                           # placeholder
        self._steps = 0
        self._success = False
        self._closed = False
        self._rng = random.Random(0)

    def reset(self, *, seed=None, options=None):
        """Start a new episode; a seed fixes the placeholder jitter of the initial state."""
        self._rng = random.Random(seed if seed is not None else 0)
        self._qpos = [value + self._rng.uniform(-JITTER, JITTER)    # placeholder
                      for value in list(ARM_START) + list(FINGER_START)]
        self._target_z = self._rng.uniform(-JITTER, JITTER)         # placeholder
        self._init_target_z = self._target_z
        self._steps = 0
        self._success = False
        self._closed = False
        return self._obs(), self._info()

    def step(self, action):
        """Advance the placeholder kinematic state by one control step and return the upstream step tuple."""
        if not isinstance(action, dict) or "arm" not in action:
            raise ValueError("the fake action must be an object with an 'arm' array")
        arm = [float(value) for value in action["arm"]]
        if len(arm) != ARM_JOINTS:
            raise ValueError(f"the arm action has {len(arm)} values, expected {ARM_JOINTS}")
        for index, value in enumerate(arm):
            self._qpos[index] += JOINT_DELTA * value                # placeholder
        self._target_z += LIFT_DELTA * sum(arm)                     # placeholder
        self._steps += 1
        reward = max(0.0, min(1.0, (self._target_z - self._init_target_z) / LIFT_HEIGHT))
        terminated = reward >= 1.0
        self._success = terminated
        return self._obs(), reward, terminated, False, self._info()

    def close(self):
        """Close the fake: no engine exists, so only the closed flag changes."""
        self._closed = True

    def _obs(self):
        return {
            "agent": list(self._qpos),
            "joint_qpos": list(self._qpos),
            "eef_pose": [EEF_X, EEF_Y, EEF_Z + self._target_z, 1.0, 0.0, 0.0, 0.0],  # placeholder
        }

    def _info(self):
        return {"target": [0.0, 0.0, self._target_z, 1.0, 0.0, 0.0, 0.0]}  # placeholder

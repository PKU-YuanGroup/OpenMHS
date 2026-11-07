"""Fake backend of the Robot Control Stack driver: a pure Python stand-in for ``gymnasium.make("rcs/fr3")``.

Why a fake: the acceptance gate runs without the clone's package, MuJoCo or the compiled ``rcs._core`` extension,
and package code never imports the clone.  This module models the interface of the environment that
``EmptyWorldFR3()`` builds: a single robot named ``right`` with a relative Cartesian TQuat action and a binary
gripper action, and an observation of tquat, joints, xyzrpy, tquat_flange and gripper width.  The public members are
the ones ``rcs.envs.base:SimEnv`` has (``reset`` and ``step``; gate G7); ``Dict`` and ``Box`` duck-type the two
gymnasium spaces the bridge reads (``spaces``, ``low``, ``high``, ``shape``).

What this is not: the upstream MuJoCo environment.  The fake is a kinematic stand-in: a relative offset moves the
pose directly, the quaternion is copied from the action and normalized, the joints follow a placeholder coupling and
the gripper value is thresholded.  There are no rigid bodies, contacts, actuators, sensors, cameras or physics
timestep, and no trajectory was compared with an upstream run.  The driver's fidelity ``gaps`` say all of this.

Every numeric constant and canned state value below is test data, marked ``# placeholder``: none of it is a Fact or
a Limit, and none of it is copied into the driver, facts.md or the reference.
"""

import random

# All constants in this block are test data.  # placeholder
HOME_TRANSLATION = [0.40, 0.0, 0.40]                     # placeholder
HOME_JOINTS = [0.0, -0.5, 0.0, -1.5, 0.0, 1.0, 0.0]     # placeholder
RESET_JITTER = 0.01                                     # placeholder
WORKSPACE_LOW = [-0.50, -0.50, -0.50]                   # placeholder
WORKSPACE_HIGH = [0.50, 0.50, 0.50]                     # placeholder
JOINT_LOW = [-2.9, -1.8, -2.9, -3.0, -2.9, -1.8, -3.0]  # placeholder
JOINT_HIGH = [2.9, 1.8, 2.9, -0.1, 2.9, 3.6, 3.0]       # placeholder
JOINT_COUPLING = 0.10                                   # placeholder
GRIPPER_CLOSED_BELOW = 0.5                              # placeholder
# The action bounds below mirror the relative Cartesian action space; the quaternion vector bound is narrowed from
# the upstream's unlimited range so every element can be probed by the gate.  # placeholder
ACTION_TQUAT_LOW = [-0.50, -0.50, -0.50, -1.0, -1.0, -1.0, -1.0]   # placeholder
ACTION_TQUAT_HIGH = [0.50, 0.50, 0.50, 1.0, 1.0, 1.0, 1.0]         # placeholder
ACTION_GRIPPER_LOW = [0.0]                              # placeholder
ACTION_GRIPPER_HIGH = [1.0]                             # placeholder
# Observation bounds are only structure for the bridge; they are test data.  # placeholder
OBS_POSE_LOW = [-2.0, -2.0, -2.0, -1.0, -1.0, -1.0, -1.0]          # placeholder
OBS_POSE_HIGH = [2.0, 2.0, 2.0, 1.0, 1.0, 1.0, 1.0]                # placeholder
OBS_JOINT_LOW = [-4.0] * 7                             # placeholder
OBS_JOINT_HIGH = [4.0] * 7                             # placeholder
OBS_RPY_LOW = [-4.0, -4.0, -4.0, -3.2, -3.2, -3.2]     # placeholder
OBS_RPY_HIGH = [4.0, 4.0, 4.0, 3.2, 3.2, 3.2]          # placeholder
OBS_GRIPPER_LOW = [0.0]                                # placeholder
OBS_GRIPPER_HIGH = [1.0]                               # placeholder


def _flatten(value):
    """The numbers of a scalar or a flat list, as floats."""
    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            out.extend(_flatten(item))
        return out
    return [float(value)]


def _clamp(value, low, high):
    return low if value < low else high if value > high else value


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = _flatten(low)
        self.high = _flatten(high)
        if len(self.low) != len(self.high):  # pragma: no cover - a definition mistake, never reached
            raise ValueError("Box low and high need the same number of elements")
        self.shape = (len(self.low),)
        self.dtype = "float64"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: a mapping of names to spaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = ()
        self.dtype = None


class FakeFr3Env:
    """The ``right`` FR3 entry of ``rcs/fr3`` without MuJoCo: ``reset`` and ``step`` mirror ``SimEnv``.

    ``reset`` starts from a home pose with a small seed-dependent offset (test data), and ``step`` applies a relative
    TQuat offset and a binary gripper value.  The observation keeps the nested ``right`` dict of the registered
    environment's robot wrapper, but carries no camera frames.
    """

    def __init__(self):
        self.action_space = Dict({
            "right": Dict({
                "tquat": Box(ACTION_TQUAT_LOW, ACTION_TQUAT_HIGH),      # placeholder
                "gripper": Box(ACTION_GRIPPER_LOW, ACTION_GRIPPER_HIGH),  # placeholder
            }),
        })
        self.observation_space = Dict({
            "right": Dict({
                "tquat": Box(OBS_POSE_LOW, OBS_POSE_HIGH),             # placeholder
                "joints": Box(OBS_JOINT_LOW, OBS_JOINT_HIGH),          # placeholder
                "xyzrpy": Box(OBS_RPY_LOW, OBS_RPY_HIGH),              # placeholder
                "tquat_flange": Box(OBS_POSE_LOW, OBS_POSE_HIGH),      # placeholder
                "gripper": Box(OBS_GRIPPER_LOW, OBS_GRIPPER_HIGH),     # placeholder
            }),
        })
        self._rng = random.Random(0)                                # placeholder
        self._pose = [float(value) for value in HOME_TRANSLATION] + [1.0, 0.0, 0.0, 0.0]  # placeholder
        self._joints = [float(value) for value in HOME_JOINTS]      # placeholder
        self._gripper = 1.0                                         # placeholder
        self._tick = 0                                              # placeholder

    def reset(self, *, seed=None, options=None):
        """Start a new episode; ``options`` is accepted and ignored, as the upstream wrappers do for empty options."""
        self._rng = random.Random(0 if seed is None else int(seed))  # placeholder
        jitter = [self._rng.uniform(-RESET_JITTER, RESET_JITTER) for _ in range(3)]  # placeholder
        self._pose = [
            HOME_TRANSLATION[0] + jitter[0],                        # placeholder
            HOME_TRANSLATION[1] + jitter[1],                        # placeholder
            HOME_TRANSLATION[2] + jitter[2],                        # placeholder
            1.0, 0.0, 0.0, 0.0,                                    # placeholder
        ]
        self._joints = [
            value + self._rng.uniform(-RESET_JITTER, RESET_JITTER)  # placeholder
            for value in HOME_JOINTS
        ]
        self._gripper = 1.0                                        # placeholder
        self._tick = 0                                             # placeholder
        return self._observation(), {"platform": "simulation"}

    def step(self, action):
        """Apply one relative pose action and one gripper action, then return the SimEnv-style step tuple."""
        if not isinstance(action, dict) or not isinstance(action.get("right"), dict):
            raise ValueError("the fake FR3 environment expects an action keyed by 'right'")
        right = action["right"]
        offset = _flatten(right.get("tquat", [0.0] * 7))            # placeholder
        gripper = _flatten(right.get("gripper", [1.0]))             # placeholder
        if len(offset) != 7 or len(gripper) != 1:
            raise ValueError("the fake FR3 environment expects a 7-value tquat and one gripper value")
        for index in range(3):
            self._pose[index] = _clamp(
                self._pose[index] + offset[index], WORKSPACE_LOW[index], WORKSPACE_HIGH[index]
            )                                                       # placeholder
        quaternion = [offset[3], offset[4], offset[5], offset[6]]  # placeholder
        norm = sum(value * value for value in quaternion) ** 0.5   # placeholder
        if norm > 0.0:                                             # placeholder
            self._pose[3:] = [
                _clamp(value / norm, -1.0, 1.0) for value in quaternion  # placeholder
            ]
        for index, value in enumerate(self._joints):
            coupled = offset[index % 3] * JOINT_COUPLING           # placeholder
            self._joints[index] = _clamp(value + coupled, JOINT_LOW[index], JOINT_HIGH[index])  # placeholder
        self._gripper = 1.0 if gripper[0] >= GRIPPER_CLOSED_BELOW else 0.0  # placeholder
        self._tick += 1                                            # placeholder
        return self._observation(), 0.0, False, False, {"platform": "simulation"}  # placeholder

    def _observation(self):
        pose = [float(value) for value in self._pose]
        return {
            "right": {
                "tquat": pose,
                "joints": [float(value) for value in self._joints],
                "xyzrpy": [pose[0], pose[1], pose[2], 0.0, 0.0, 0.0],  # placeholder
                "tquat_flange": list(pose),
                "gripper": [float(self._gripper)],
            },
        }

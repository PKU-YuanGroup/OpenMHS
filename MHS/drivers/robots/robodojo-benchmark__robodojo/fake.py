"""Fake backend of the RoboDojo driver: a pure Python stand-in for ``env.environment.task_env:TaskEnv``.

Why a fake: the acceptance gate runs without Isaac Sim, Isaac Lab or gymnasium, and package code never imports the
clone.  The upstream ``TaskEnv`` is an Isaac Sim task environment; this module keeps only the surface the Gymnasium
bridge needs (``reset``, ``step``, ``close``) and duck-types the two Gymnasium spaces the bridge reads.  The action
space follows the policy convention of the eval client for the common dual-X5 embodiment: one six-joint arm command
and one normalized gripper command per arm (``src/eval_client/eval_env.py:377-400``).  The observation is the matching
joint/gripper state (``env/observation_manager/obs_manager.py:168-207``).

Every number below is test data of this stand-in, marked ``# placeholder``; the facts and limits of the package are
in ``driver.py`` and cite the clone.  The stand-in is not the upstream environment: it has no Isaac Sim, no physics,
no task scene, no camera and no task reward or success check.  Those differences are also listed in the driver's
fidelity ``gaps``.

Nothing here talks to a device.
"""

import math
import random

# The eval client forwards arm_joint_state values as joint position targets without clipping
# (src/eval_client/eval_env.py:381-384); the articulation limits live in the downloaded USD asset
# (README.md:63), which is not in the clone.  The fake therefore leaves the arm command unbounded and bounds only the
# normalized gripper command, which the eval client clips to 0..1 (src/eval_client/eval_env.py:388-389).  Test data of
# this stand-in, not a Fact or Limit here.
ARM_LOW = [-math.inf] * 6                                # placeholder (unbounded: limits are in the USD asset)
ARM_HIGH = [math.inf] * 6                                # placeholder
GRIPPER_LOW, GRIPPER_HIGH = 0.0, 1.0                      # placeholder
ARM_JOINTS = 6                                            # placeholder
STATE_SIZE = 14                                           # placeholder (2 arms x (6 joints + 1 gripper))
START_JITTER = 0.001                                      # placeholder, only to make a seed observable
START_GRIPPER = 1.0                                       # placeholder (0.044 m normalized to the gripper scale)


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: named subspaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.dtype = "object"


class FakeTaskEnv:
    """A joint-space stand-in for ``TaskEnv`` with the dual-X5 policy action and state convention.

    ``reset(seed=..., options=...)`` returns the 14-number state; ``step(action)`` expects the four arm/gripper
    command keys and returns the standard five-tuple; ``close`` makes teardown observable.  The upstream class gives
    these public members (``TaskEnv.reset``, ``.step`` and ``.close``); gate G7 checks that.
    """

    def __init__(self, **_options):
        self.action_space = Dict({
            "left_arm_joint_state": Box(ARM_LOW, ARM_HIGH),
            "left_ee_joint_state": Box([GRIPPER_LOW], [GRIPPER_HIGH]),
            "right_arm_joint_state": Box(ARM_LOW, ARM_HIGH),
            "right_ee_joint_state": Box([GRIPPER_LOW], [GRIPPER_HIGH]),
        })
        self.observation_space = Box(
            ARM_LOW + [GRIPPER_LOW] + ARM_LOW + [GRIPPER_LOW],
            ARM_HIGH + [GRIPPER_HIGH] + ARM_HIGH + [GRIPPER_HIGH],
        )
        self._rng = random.Random(0)
        self._seed = None
        self._tick = 0
        self._closed = False
        self._left_arm = [0.0] * ARM_JOINTS             # placeholder
        self._left_gripper = START_GRIPPER              # placeholder
        self._right_arm = [0.0] * ARM_JOINTS            # placeholder
        self._right_gripper = START_GRIPPER             # placeholder

    def _observation(self):
        return list(self._left_arm) + [self._left_gripper] + list(self._right_arm) + [self._right_gripper]

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        # placeholder initial pose: X5 init_state has 0 for joints 1-6 and 0.044 for the gripper joints
        # (env/robot_manager/robot_config/x5.py:23-33); the small jitter is this stand-in's seed hook only.
        self._left_arm = [self._rng.uniform(-START_JITTER, START_JITTER) for _ in range(ARM_JOINTS)]
        self._right_arm = [self._rng.uniform(-START_JITTER, START_JITTER) for _ in range(ARM_JOINTS)]
        self._left_gripper = START_GRIPPER
        self._right_gripper = START_GRIPPER
        self._tick = 0
        return self._observation(), {}

    def step(self, action):
        if not isinstance(action, dict):
            raise ValueError("the RoboDojo action is a dict of arm and gripper commands")
        parts = (
            ("left_arm_joint_state", ARM_JOINTS, "_left_arm"),
            ("left_ee_joint_state", 1, "_left_gripper"),
            ("right_arm_joint_state", ARM_JOINTS, "_right_arm"),
            ("right_ee_joint_state", 1, "_right_gripper"),
        )
        for key, size, attribute in parts:
            if key not in action:
                raise ValueError(f"the action has no {key!r}")
            values = list(action[key])
            if len(values) != size:
                raise ValueError(f"{key!r} expects {size} values, got {len(values)}")
            if size == 1:
                setattr(self, attribute, float(values[0]))
            else:
                setattr(self, attribute, [float(value) for value in values])
        self._tick += 1
        # placeholder reward: the real reward is task-specific (the 42 task classes own it)
        return self._observation(), 0.0, False, False, {"tick": self._tick}

    def close(self):
        self._closed = True

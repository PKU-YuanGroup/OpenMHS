"""Fake backend for the DuoBench ball_maze package: a pure Python stand-in for the registered environment.

Why a fake: the acceptance gate runs without MuJoCo, RCS or numpy (``pyproject.toml:9-15`` and ``:23``), and package
code never imports the clone.  This module implements the environment's Gymnasium surface (``reset``, ``step`` and the
spaces the bridge reads; gate G7 checks these against ``BallMazeTaskWrapper``) and a small kinematic stage machine
whose numbers are placeholders.

The action shape is the one the clone's own example sends to ``duobench/ball_maze``
(``scripts/gym_make.py:31-34``): a dict with ``left`` and ``right`` arms, each carrying a seven-number ``tquat`` and a
one-number ``gripper``.  The clone shows no bounds for that space, so the Box bounds below are placeholders, not a
device limit.  The fake's observation is a short placeholder vector; the real RCS observation (cameras and robot
state) is not described in the clone, so it is not modelled.  Every placeholder is marked.

Nothing here talks to a device.
"""

import random

#: The task instruction and stage texts of the clone (src/duobench/tasks/ball_maze.py:28 and :85-105).
INSTRUCTION = "pick up the board and tilt it so the ball rolls onto the red square"
STAGE_TEXTS = {
    0: "make contact with the maze",
    1: "grasp the maze with both arms",
    2: "lift the maze and move the ball out of the start area",
    3: "guide the ball from the start area toward the goal",
    4: "task completed; the ball has reached the goal",
}
#: BallMazeStage.max_stage is 4 (src/duobench/tasks/ball_maze.py:87).
MAX_STAGE = 4

# Placeholder action bounds: the example action uses tquat values around 0.01 and a 0/1 gripper
# (scripts/gym_make.py:31-34), but no bound is stated in the clone.  These are test data only.
TQUAT_LOW, TQUAT_HIGH = -1.0, 1.0
GRIPPER_LOW, GRIPPER_HIGH = 0.0, 1.0
# The fake opens the grippers with 1 and closes them with 0, the two values the example uses.
GRIPPER_OPEN = 1.0


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: one lower and upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: named member spaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = ()
        self.dtype = None


def _action_space():
    """The action dict of the clone's example (``scripts/gym_make.py:31-34``) with placeholder bounds."""

    def arm():
        return Dict({
            "tquat": Box([TQUAT_LOW] * 7, [TQUAT_HIGH] * 7),
            "gripper": Box([GRIPPER_LOW], [GRIPPER_HIGH]),
        })

    return Dict({"left": arm(), "right": arm()})


class FakeBallMazeEnv:
    """A kinematic stand-in for ``duobench/ball_maze``: ``reset(seed, options)`` and ``step(action)``.

    The stage machine follows the clone's ordering (stage 1 on contact, 2 when both arms lift the maze, 3 and 4 as the
    board tilts), but its thresholds and the arm positions are placeholders.  The fake does not run MuJoCo, does not
    model contacts, the ball or the cameras, and does not model the tquat quaternion.
    """

    def __init__(self, **_options):
        self.action_space = _action_space()
        self._rng = random.Random(0)                    # placeholder: replaced by reset(seed)
        self._left = [0.0, 0.0, 0.0]                    # placeholder
        self._right = [0.0, 0.0, 0.0]                   # placeholder
        self._left_gripper = GRIPPER_OPEN
        self._right_gripper = GRIPPER_OPEN
        self._stage = 0
        self._steps = 0

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(seed)
        # placeholder start positions: the clone draws the board placement from np_random
        # (src/duobench/utils/helper_wrappers.py:187-204) but does not state the arm start state.
        self._left = [self._rng.uniform(-0.01, 0.01) for _ in range(3)]
        self._right = [self._rng.uniform(-0.01, 0.01) for _ in range(3)]
        self._left_gripper = GRIPPER_OPEN
        self._right_gripper = GRIPPER_OPEN
        self._stage = 0
        self._steps = 0
        return self._observation(), self._info()

    def step(self, action):
        left = action["left"]
        right = action["right"]
        for index in range(3):
            self._left[index] += float(left["tquat"][index])
            self._right[index] += float(right["tquat"][index])
        self._left_gripper = float(left["gripper"][0])
        self._right_gripper = float(right["gripper"][0])
        self._steps += 1
        self._advance_stage()
        reward = self._stage / MAX_STAGE                  # TaskStage.normalized_stage (tasks/__init__.py:41-42)
        terminated = self._stage == MAX_STAGE             # TaskStage.success (tasks/__init__.py:36-38)
        return self._observation(), reward, terminated, False, self._info()

    def _advance_stage(self):
        left_closed = self._left_gripper <= 0.5           # placeholder threshold
        right_closed = self._right_gripper <= 0.5         # placeholder threshold
        if left_closed or right_closed:
            self._stage = max(self._stage, 1)             # stage 1: arm contact (ball_maze.py:195-196)
        if left_closed and right_closed:
            if min(self._left[2], self._right[2]) > 0.20:  # placeholder lift threshold
                self._stage = max(self._stage, 2)         # stage 2: maze lifted (ball_maze.py:193-194)
            tilt = abs(self._left[2] - self._right[2])
            if tilt > 0.05:                               # placeholder tilt threshold
                self._stage = max(self._stage, 3)         # stage 3: ball leaves the start (ball_maze.py:191-192)
            if tilt > 0.10:                               # placeholder tilt threshold
                self._stage = max(self._stage, 4)         # stage 4: ball at the goal (ball_maze.py:189-190)

    def _observation(self):
        # placeholder 8-element vector; the real RCS observation is not described in the clone.
        return [*self._left, *self._right, self._left_gripper, self._right_gripper]

    def _info(self):
        # TaskStage.info (src/duobench/tasks/__init__.py:44-55)
        return {
            "success": self._stage == MAX_STAGE,
            "stage": self._stage,
            "max_stage": MAX_STAGE,
            "current_subinstruction": STAGE_TEXTS[self._stage],
            "stage_to_subinstructions": {str(stage): text for stage, text in STAGE_TEXTS.items()},
            "instruction": INSTRUCTION,
        }

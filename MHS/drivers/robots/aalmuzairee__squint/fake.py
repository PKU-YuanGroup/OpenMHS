"""Fake backend of the squint driver: a pure-Python stand-in for the ManiSkill LiftCube environment.

Why a fake: the acceptance gate runs without ManiSkill, SAPIEN or a GPU (``environment.yaml`` of the clone names the
simulation stack; the card's ``install`` block is empty), and package code never imports the clone.  This module
re-implements only the surface the Gymnasium bridge needs from ``envs.lift:LiftCube`` (the class the driver names as
``native``): ``reset``, ``step``, ``close`` and duck-typed action/observation spaces.  The bridge derives the step
contract from these spaces.  The action space is the one ManiSkill serves for the ``pd_joint_target_delta_pos``
controller of ``envs/robot/so101.py:97-109``, -1 to 1 per joint, and ``step`` scales an action to that controller's
joint deltas as ManiSkill does; the truncation mirrors ``max_episode_steps=50`` of ``envs/lift.py:407``.

What this is not: the upstream environment.  It is an analytic kinematic stand-in with no rigid-body dynamics,
contacts, friction, actuator response, camera render or domain randomization.  The observation state is a 10-number
placeholder vector and the RGB frame is a 4x4x3 placeholder array, while the upstream wrist camera renders 128x128
(``envs/base_random_env.py:521-527``).  All such numbers are test data, marked ``# placeholder``; they are not facts,
limits or references of this package.  The action space, its width and the joint deltas are the upstream's and carry
no mark.  The differences are also listed in the driver's fidelity ``gaps``.

Nothing here talks to a device.
"""

import math
import random

# The SO101's six active joints, five arm joints and the gripper (envs/robot/so101.py:73-82), which the controller
# config below bounds one by one.
JOINTS = 6

# The pd_joint_target_delta_pos controller config (envs/robot/so101.py:97-109) bounds the joint deltas of one control
# step: 0.1 for the five arm joints and 0.2 for the gripper.  It does not set normalize_action, and ManiSkill's default
# is True: a normalised controller serves Box(-1, 1) of its shape and scales each action value to these deltas.  That
# code is ManiSkill's, not this clone's (mani_skill/agents/controllers/pd_joint_pos.py:131,
# mani_skill/agents/controllers/base_controller.py:70-72 and mani_skill/utils/gym_utils.py:104-112, read in
# robots/mani-skill/maniskill at 62ff3a58, since environment.yaml:15 installs an unpinned mani_skill_nightly), so the
# driver cites no line for the step bounds.
ACTION_LOW = [-1.0] * JOINTS
ACTION_HIGH = [1.0] * JOINTS
DELTA_LOW = [-0.1, -0.1, -0.1, -0.1, -0.1, -0.2]
DELTA_HIGH = [0.1, 0.1, 0.1, 0.1, 0.1, 0.2]

# SO101LiftCube-v1 is registered with max_episode_steps=50 (envs/lift.py:407); the stand-in truncates at the same
# step count.  Test data of this stand-in, not a Fact or Limit here.
MAX_EPISODE_STEPS = 50   # placeholder

# The upstream wrist camera renders 128x128 (envs/base_random_env.py:523-525); the stand-in returns a tiny frame.
RGB_SIZE = 4             # placeholder (real default 128)
STATE_SIZE = 10          # placeholder (the fake's analytic state vector)


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high, shape=None):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: named subspaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.dtype = "object"


class FakeSO101LiftCube:
    """A small analytic stand-in for ``envs.lift:LiftCube`` (``SO101LiftCube-v1``).

    ``reset(seed=..., options=...)`` initialises the joint and item state from the seed, exactly as a seeded
    environment should; ``step(action)`` scales a six-value action in -1..1 to the joint deltas, applies them and
    returns a five-tuple.  ``close`` is a no-op that makes teardown observable.
    """

    def __init__(self, **_options):
        self.action_space = Box(ACTION_LOW, ACTION_HIGH, shape=(JOINTS,))       # the normalised space (above)
        self.observation_space = Dict({
            "rgb": Box([0] * (RGB_SIZE * RGB_SIZE * 3), [255] * (RGB_SIZE * RGB_SIZE * 3),
                       shape=(RGB_SIZE, RGB_SIZE, 3)),                         # placeholder frame size
            "state": Box([-math.inf] * STATE_SIZE, [math.inf] * STATE_SIZE, shape=(STATE_SIZE,)),
        })
        self._rng = random.Random()
        self._qpos = [0.0] * JOINTS                                            # placeholder
        self._item = [0.0, 0.0, 0.0]                                           # placeholder
        self._grasped = False                                                  # placeholder
        self._tick = 0
        self._seed = None
        self._done = False
        self._closed = False

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(int(seed))
        self._seed = seed
        # placeholder starting pose: the upstream SO101 start keyframe is the rest pose (envs/robot/so101.py:55-60)
        self._qpos = [self._rng.uniform(-0.02, 0.02) for _ in range(JOINTS)]
        # placeholder item spawn box (the upstream default is 0.2 m wide, envs/lift.py:66-67)
        self._item = [self._rng.uniform(-0.1, 0.1), self._rng.uniform(-0.1, 0.1), 0.0]
        self._grasped = False
        self._tick = 0
        self._done = False
        return self._observation(), {}

    def _observation(self):
        # placeholder RGB frame (the upstream wrist camera is 128x128, envs/base_random_env.py:523-525)
        depth = min(255, 20 + self._tick * 4)
        rgb = [[[depth, 0, 0] for _ in range(RGB_SIZE)] for _ in range(RGB_SIZE)]
        # placeholder state vector standing in for the ManiSkill state observation (envs/lift.py:328-341)
        state = list(self._qpos) + list(self._item) + [float(self._grasped)]
        return {"rgb": rgb, "state": state}

    def step(self, action):
        values = [float(item) for item in action]
        if len(values) != JOINTS:
            raise ValueError(f"expected a {JOINTS}-joint action, got {len(values)} values")
        # As the normalised controller does: clip each value to [-1, 1] and scale it to the joint delta
        # (clip_and_scale_action, mani_skill/utils/gym_utils.py:104-107).  The target variant adds the deltas to the
        # previous joint targets (use_target=True, envs/robot/so101.py:108-109), which this stand-in reaches at once.
        deltas = [0.5 * (high + low) + 0.5 * (high - low) * max(-1.0, min(1.0, value))
                  for value, low, high in zip(values, DELTA_LOW, DELTA_HIGH)]
        self._qpos = [qpos + delta for qpos, delta in zip(self._qpos, deltas)]
        # placeholder analytic grasp: the last joint (gripper) closing moves the item
        self._grasped = deltas[-1] < 0.0
        if self._grasped:
            self._item[2] = max(self._item[2], 0.001)
        self._tick += 1
        # placeholder reward, not the upstream compute_dense_reward (envs/lift.py:385-397)
        reward = -sum(abs(qpos) for qpos in self._qpos) / JOINTS
        self._done = self._tick >= MAX_EPISODE_STEPS
        return self._observation(), reward, False, self._done, {"tick": self._tick}

    def close(self):
        self._closed = True

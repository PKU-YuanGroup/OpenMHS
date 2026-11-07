"""Fake backend of the REALRobot driver: a pure Python stand-in for ``real_robots.envs.env:REALRobotEnv``.

Why a fake: the acceptance gate runs without ``gym``, ``pybullet`` or the
upstream package (the gate never installs or imports the clone), so the
``fake`` backend re-implements the parts of the environment the bridge uses:
the action space of the default ``action_type='joints'`` configuration, the
legacy ``reset()``/``step(action)`` methods, and the observation dictionary.
The public members are the ones ``REALRobotEnv`` has (``reset`` and ``step``,
gate G7).  The bridge derives the action schema and the per-element limits
from the fake's ``action_space``, exactly as it would from the environment's.

What this is not: the upstream PyBullet simulation.  The joint state is a
kinematic integration of the commanded positions with the upstream per-step
change clamp; there is no rigid-body dynamics, no contact, no object physics
and no rendered camera.  The image, depth and mask arrays are a 24 x 32
stand-in for the environment's 240 x 320 arrays (``Kuka.eye_width`` and
``Kuka.eye_height``, robot.py:30-31), so receipts stay small.  The differences
are listed in the driver's fidelity ``gaps`` and in RESULT.json notes.

Every constant below is either transcribed from a cited upstream line (the
action-space bounds and the per-step joint clamp) or is test data marked
``# placeholder``.  No placeholder number is used as a Fact, a Limit or a
reference.
"""

import math
import random

#: Kuka.eye_width / Kuka.eye_height (robot.py:30-31) are 320 / 240; the fake
#: returns this smaller stand-in (see the fidelity gaps in driver.py).
FAKE_EYE_WIDTH = 32      # placeholder
FAKE_EYE_HEIGHT = 24     # placeholder

#: The action-space bounds are min_joints/max_joints of Kuka (robot.py:58-71):
#: joint 0 is limited to +-0.666*pi, joints 1 and 3 to +-0.666*pi, joints 2
#: and 4 keep the initial +-0.944*pi, joint 6 to +-0.972*pi, and the two
#: gripper joints (7 and 8) to 0 .. pi/2.  These are transcribed upstream
#: bounds, not invented test values.
MIN_JOINTS = [
    -0.666 * math.pi, -0.666 * math.pi, -0.944 * math.pi, -0.666 * math.pi,
    -0.944 * math.pi, -0.666 * math.pi, -0.972 * math.pi, 0.0, 0.0,
]
MAX_JOINTS = [
    0.666 * math.pi, 0.666 * math.pi, 0.944 * math.pi, 0.666 * math.pi,
    0.944 * math.pi, 0.666 * math.pi, 0.972 * math.pi, math.pi / 2, math.pi / 2,
]

#: env.py:316-317: the largest change of each joint that limitActionByJoint
#: accepts in one step.
MAX_CHANGE = [0.2, 0.2, 0.2, 0.2, 0.2, 0.3, 0.3, 0.1, 0.1]

#: The start poses of the tabletop objects (robot.py:19-24), jittered by the
#: reset seed.  Test data only.
OBJECT_POSES = {                        # placeholder
    "cube": [-0.1, 0.0, 0.45],          # placeholder
    "tomato": [-0.1, -0.3, 0.45],       # placeholder
    "mustard": [-0.1, 0.3, 0.45],       # placeholder
}
JITTER = 0.02                           # placeholder

_FLOAT32_MAX = 3.4028234663852886e38    # np.finfo(np.float32).max, robot.py:76-78


class Box:
    """Duck-typed ``gym.spaces.Box``: ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape=None, dtype=None):
        self.low = low
        self.high = high
        self.shape = tuple(shape) if shape is not None else _infer_shape(low, high)
        self.dtype = dtype or "float64"


class MultiBinary:
    """Duck-typed ``gym.spaces.MultiBinary``: ``n`` values, each 0 or 1."""

    def __init__(self, n):
        self.n = int(n)
        self.shape = (self.n,)
        self.dtype = "int8"


class Dict:
    """Duck-typed ``gym.spaces.Dict``: a mapping of named subspaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _infer_shape(low, high):
    if isinstance(low, (list, tuple)):
        if low and isinstance(low[0], (list, tuple)):
            return (len(low), len(low[0]))
        return (len(low),)
    return ()


def _zeros_3d(height, width):
    return [[[0, 0, 0] for _ in range(width)] for _ in range(height)]


def _zeros_2d(height, width):
    return [[0 for _ in range(width)] for _ in range(height)]


class FakeREALRobotEnv:
    """``REALRobotEnv`` without gym, pybullet or numpy: legacy ``reset`` and ``step``.

    The constructor mirrors the upstream signature and defaults (env.py:36-37).
    The fake implements the default ``action_type='joints'`` configuration
    (env.py:57-61); the other two action types need the upstream inverse
    kinematics or macro planner and are refused here.  ``reset`` also accepts
    the bridge's ``seed`` and ``options`` keywords and uses ``seed`` for the
    synthetic tabletop object positions, which the upstream ``reset()`` does
    not do (see the fidelity gaps).
    """

    #: Upstream class constants (env.py:32-34; robot.py:26-31).
    intrinsic_timesteps = int(15e6)
    extrinsic_timesteps = int(10e3)
    extrinsic_trials = int(50)
    num_joints = 9
    num_gripper_joints = 2
    num_touch_sensors = 4
    eye_width = 320
    eye_height = 240

    def __init__(self, render=False, objects=3, action_type="joints", additional_obs=True):
        if action_type != "joints":
            raise ValueError("the fake REALRobotEnv implements only action_type='joints'")
        self.render = bool(render)
        self.objects = int(objects)
        self.action_type = action_type
        self.additional_obs = bool(additional_obs)
        self.object_names = ["cube", "tomato", "mustard"][:self.objects]

        # env.py:57-61: the default action space is a Dict with the 9-joint Box
        # (robot.py:69-71) and MultiBinary(1) render flag.
        self.action_space = Dict({
            "joint_command": Box(MIN_JOINTS, MAX_JOINTS, shape=(9,)),
            "render": MultiBinary(1),
        })

        eye_3d = (FAKE_EYE_HEIGHT, FAKE_EYE_WIDTH, 3)
        eye_2d = (FAKE_EYE_HEIGHT, FAKE_EYE_WIDTH)
        self.observation_space = Dict({
            "joint_positions": Box([-math.inf] * 9, [math.inf] * 9, shape=(9,)),
            "touch_sensors": Box([0.0] * 4, [math.inf] * 4, shape=(4,)),
            "retina": Box(0, 255, shape=eye_3d, dtype="uint8"),
            "depth": Box(0, 1, shape=eye_2d),
            "goal": Box(0, 255, shape=eye_3d, dtype="uint8"),
        })
        if self.additional_obs:
            self.observation_space.spaces.update({
                "mask": Box(0, 255, shape=eye_2d, dtype="int32"),
                "object_positions": Dict({
                    name: Box([-_FLOAT32_MAX] * 3, [_FLOAT32_MAX] * 3, shape=(3,))
                    for name in self.object_names
                }),
                "goal_mask": Box(0, 255, shape=eye_2d, dtype="int32"),
                "goal_positions": Dict({
                    name: Box([-_FLOAT32_MAX] * 3, [_FLOAT32_MAX] * 3, shape=(3,))
                    for name in self.object_names
                }),
            })

        self._seed = 0
        self._rng = random.Random(self._seed)
        self._joints = [0.0] * 9
        self._objects = {}
        self._tick = 0
        self._goal_idx = -1
        self._reset_objects()

    # -- native surface: reset() and step(action) only (gate G7) ----------------
    def reset(self, seed=None, options=None):
        """Reset the joint state, the objects and the step counter; return the observation."""
        self._seed = 0 if seed is None else int(seed)
        self._rng = random.Random(self._seed)
        self._joints = [0.0] * 9
        self._tick = 0
        self._goal_idx = -1
        self._reset_objects()
        return self._observation(True)

    def step(self, action):
        """Apply one joint command and return ``(observation, reward, done, info)`` (env.py:356)."""
        joint_command = action.get("joint_command")
        render = action.get("render")
        camera_on = bool(render[0]) if isinstance(render, (list, tuple)) and render else bool(render)
        if joint_command is None:
            joint_command = [0.0] * 9
        target = [float(value) for value in joint_command]
        if len(target) != 9:
            raise ValueError("joint_command must have 9 joint positions")
        # env.py:314-321: clamp the change of each joint in one step.
        self._joints = [
            current + max(-delta, min(delta, wanted - current))
            for current, wanted, delta in zip(self._joints, target, MAX_CHANGE)
        ]
        self._tick += 1
        if self._goal_idx < 0:
            done = self._tick >= self.intrinsic_timesteps
        else:
            done = self._tick >= self.extrinsic_timesteps
        return self._observation(camera_on), 0.0, bool(done), {}

    # -- helpers (private: not part of the checked fake surface) ----------------
    def _reset_objects(self):
        self._objects = {}
        for name in self.object_names:
            x, y, z = OBJECT_POSES[name]
            self._objects[name] = [
                x + self._rng.uniform(-JITTER, JITTER),     # placeholder
                y + self._rng.uniform(-JITTER, JITTER),     # placeholder
                z,
            ]

    def _observation(self, camera_on):
        observation = {
            "joint_positions": list(self._joints),
            "touch_sensors": [0.0] * 4,                       # placeholder
            "retina": self._image(camera_on),
            "depth": [[0.0] * FAKE_EYE_WIDTH for _ in range(FAKE_EYE_HEIGHT)],   # placeholder
            "goal": _zeros_3d(FAKE_EYE_HEIGHT, FAKE_EYE_WIDTH),
        }
        if self.additional_obs:
            observation["mask"] = _zeros_2d(FAKE_EYE_HEIGHT, FAKE_EYE_WIDTH)
            observation["object_positions"] = {
                name: list(position) for name, position in self._objects.items()
            }
            # The upstream goal is a camera image with no final_state/mask until
            # set_goal() (env.py:97-98 and :307-309); the fake publishes zero
            # arrays so the declared observation space stays well formed.
            observation["goal_mask"] = _zeros_2d(FAKE_EYE_HEIGHT, FAKE_EYE_WIDTH)
            observation["goal_positions"] = {
                name: [0.0, 0.0, 0.0] for name in self.object_names
            }
        return observation

    def _image(self, camera_on):
        if not camera_on:
            return _zeros_3d(FAKE_EYE_HEIGHT, FAKE_EYE_WIDTH)
        joint = int(round(self._joints[0] * 10))               # placeholder
        return [
            [
                [(self._tick * 3 + x * 5 + y * 7 + channel + joint) % 256    # placeholder
                 for channel in range(3)]
                for x in range(FAKE_EYE_WIDTH)
            ]
            for y in range(FAKE_EYE_HEIGHT)
        ]

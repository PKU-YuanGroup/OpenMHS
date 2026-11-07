"""Fake backend of the Ravens driver: a pure-Python stand-in for ``Environment`` at the pinned commit.

Why a fake: the upstream environment imports ``gym``, ``pybullet``, ``numpy`` and the Ravens asset tree, and package
code never imports or runs the clone.  This module therefore implements only the public surface of
``ravens.environments.environment:Environment`` that the gymnasium bridge uses: ``reset()``, ``step(action=None)``,
``seed(seed=None)``, ``close()``, ``action_space`` and ``observation_space`` (gate G7).  The space classes duck-type
``gym.spaces.Dict``, ``Tuple`` and ``Box`` so the bridge can derive the JSON schemas (``spaces``, ``low``, ``high``,
``shape``).

What it is not: the upstream simulator.  It does not run PyBullet, does not model contacts, grasps or task rewards,
and returns a 2x2 placeholder for each of the three 480x640 RGB-D cameras.  It was never compared with an upstream
run.  Every number below is test data (marked ``# placeholder``) and is not a fact, a limit or a reference.

The environment is simulated: nothing here talks to a physical device.
"""

import random


class Dict:
    """Duck-typed ``gym.spaces.Dict``: the bridge reads ``spaces`` as a mapping of name to space."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class Tuple:
    """Duck-typed ``gym.spaces.Tuple``: the bridge reads ``spaces`` as the ordered item spaces."""

    def __init__(self, spaces):
        self.spaces = tuple(spaces)


class Box:
    """Duck-typed ``gym.spaces.Box``: the bridge reads ``low``, ``high`` and ``shape``."""

    def __init__(self, low, high, shape=None, dtype=None):
        self.low = list(low) if isinstance(low, (list, tuple)) else low
        self.high = list(high) if isinstance(high, (list, tuple)) else high
        self.shape = tuple(shape) if shape is not None else (len(self.low),)
        self.dtype = dtype or "float32"


# The position and rotation bounds mirror environment.py:89-103 so the derived action schema has the upstream
# shape; the numbers are the space's test data in this fake.  # placeholder
POSITION_LOW = [0.25, -0.5, 0.0]                     # placeholder (environment.py:89-93)
POSITION_HIGH = [0.75, 0.5, 0.28]                    # placeholder (environment.py:89-93)
ROTATION_LOW = [-1.0, -1.0, -1.0, -1.0]              # placeholder (environment.py:98)
ROTATION_HIGH = [1.0, 1.0, 1.0, 1.0]                 # placeholder (environment.py:98)
# The upstream camera images are 480x640 (cameras.py:27-28); the fake only publishes that shape and returns 2x2.
CAMERA_SHAPE = (480, 640, 3)                         # placeholder
DEPTH_SHAPE = (480, 640)                             # placeholder
IMAGE_SIDE = 2                                       # placeholder
CAMERA_COUNT = 3                                     # placeholder


class FakeRavensEnvironment:
    """Stand-in for ``Environment``: ``reset()``, ``step(action)``, ``seed(seed)`` and ``close()``."""

    def __init__(self, **options):
        self.options = dict(options)                                     # placeholder: ignored by the fake
        position_bounds = Box(POSITION_LOW, POSITION_HIGH)
        rotation_bounds = Box(ROTATION_LOW, ROTATION_HIGH)
        color = Box(0, 255, shape=CAMERA_SHAPE, dtype="uint8")           # placeholder
        depth = Box(0.0, 20.0, shape=DEPTH_SHAPE, dtype="float32")       # placeholder
        self.observation_space = Dict({
            "color": Tuple([color] * CAMERA_COUNT),                       # placeholder
            "depth": Tuple([depth] * CAMERA_COUNT),                       # placeholder
        })
        self.action_space = Dict({
            "pose0": Tuple((position_bounds, rotation_bounds)),
            "pose1": Tuple((position_bounds, rotation_bounds)),
        })
        self._rng = random.Random()
        self._tick = 0
        self._episode = 0
        self._target = [0.5, 0.0, 0.05]                                   # placeholder: start target

    def seed(self, seed=None):
        """Install the fake's generator and return the seed (the upstream method's contract)."""
        self._rng = random.Random(seed)
        return seed

    def reset(self):
        """Start an episode and return the observation, as the upstream legacy ``reset()`` does."""
        self._tick = 0
        self._episode += 1
        self._target = [
            self._rng.uniform(0.25, 0.75),                                # placeholder
            self._rng.uniform(-0.5, 0.5),                                 # placeholder
            self._rng.uniform(0.0, 0.28),                                 # placeholder
        ]
        return self._observation()

    def step(self, action=None):
        """Advance one tick and return the legacy ``(obs, reward, done, info)`` four-tuple."""
        if action is not None:
            target = _pose_position(action)
            if target is not None:
                self._target = target
        self._tick += 1
        return self._observation(), 0.0, False, {}

    def close(self):
        """Release the fake's episode state (no PyBullet client exists)."""
        self._tick = 0

    def _observation(self):
        x, y, z = self._target
        red = _clamp_byte((x - 0.25) / 0.5 * 255.0)                        # placeholder: encode the target
        green = _clamp_byte((y + 0.5) / 1.0 * 255.0)                       # placeholder
        blue = self._tick % 256                                            # placeholder
        color = [[[0, 0, 0] for _ in range(IMAGE_SIDE)] for _ in range(IMAGE_SIDE)]
        color[0][0] = [red, green, blue]
        depth = [[0.0 for _ in range(IMAGE_SIDE)] for _ in range(IMAGE_SIDE)]
        depth[0][0] = float(z)
        return {
            "color": tuple([color] * CAMERA_COUNT),
            "depth": tuple([depth] * CAMERA_COUNT),
        }


def _pose_position(action):
    """The position of ``pose1`` from the bridge's native action, or ``None`` when it is not present."""
    if not isinstance(action, dict):
        return None
    pose = action.get("pose1")
    if not isinstance(pose, (list, tuple)) or not pose:
        return None
    position = pose[0]
    if not isinstance(position, (list, tuple)) or len(position) < 3:
        return None
    try:
        return [float(position[0]), float(position[1]), float(position[2])]
    except (TypeError, ValueError):
        return None


def _clamp_byte(value):
    return max(0, min(255, int(round(value))))

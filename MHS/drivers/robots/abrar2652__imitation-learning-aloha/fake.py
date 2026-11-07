"""Fake backend of the Gym Aloha driver: a pure Python stand-in for the insertion environment.

Why a fake: the acceptance gate runs without gymnasium, dm_control or MuJoCo (the upstream pyproject.toml declares all
three), and package code never imports the clone.  This module mirrors the public surface of
``gym_aloha.env:AlohaEnv`` (the class the driver names as ``native``) and of the registration
``gym_aloha/AlohaInsertion-v0``: ``reset(seed, options)``, ``step(action)``, ``render()`` and ``close()``, a 14-element
``Box`` action space and a ``Dict`` observation space with one ``top`` image.  Every public method exists on
``AlohaEnv`` (gate G7); the two space classes duck-type ``gymnasium.spaces.Box`` and ``Dict`` (the bridge reads
``low``, ``high``, ``shape``, ``dtype`` and ``spaces``).

What this is not: MuJoCo, dm_control or the upstream environment.  The model is kinematic: the action drives a score
and a small stand-in image, not the ViperX physics.  The real observation is 480 x 640 x 3 (env.py:56-66); the fake
returns 4 x 4 x 3 so a receipt stays small.  The differences are listed in the fidelity ``gaps`` of ``driver.py``.

Nothing here talks to a device.
"""

import random

# gym-aloha/gym_aloha/gym_aloha/__init__.py:3-10: the registered environment's step limit and action count.
# The insertion task is bimanual (env.py:126-132) and ACTIONS has 14 entries (constants.py:30-48).
ACTION_COUNT = 14
MAX_EPISODE_STEPS = 300
# placeholder: the fake's small stand-in image, its success rule and its score target are test data, not facts.
IMAGE_SHAPE = (4, 4, 3)
SCORE_TARGET = 4
SUCCESS_ACTION_THRESHOLD = 0.5


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape=None, dtype="float32"):
        if shape is None:
            if isinstance(low, (list, tuple)):
                shape = (len(low),)
            elif isinstance(high, (list, tuple)):
                shape = (len(high),)
            else:
                shape = ()
        self.shape = tuple(int(item) for item in shape)
        count = 1
        for item in self.shape:
            count *= item
        self.low = list(low) if isinstance(low, (list, tuple)) else [low] * count
        self.high = list(high) if isinstance(high, (list, tuple)) else [high] * count
        self.dtype = dtype


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces`` as a mapping of names to spaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _copy_image(image):
    return [row[:] for row in image]


def _make_image(seed, tick, action):
    """A deterministic small stand-in for the top camera frame (placeholder test data)."""
    rng = random.Random(0 if seed is None else seed)
    base = rng.randrange(256)
    lift = 0 if not action else int(round((sum(action) / len(action) + 1.0) * 40.0))
    return [
        [
            [(base + tick * 3 + row * 17 + col * 29 + lift) % 256 for _ in range(IMAGE_SHAPE[2])]
            for col in range(IMAGE_SHAPE[1])
        ]
        for row in range(IMAGE_SHAPE[0])
    ]


class FakeAlohaEnv:
    """The insertion environment of ``gym_aloha/AlohaInsertion-v0`` without MuJoCo, gymnasium or numpy."""

    def __init__(
        self,
        task="insertion",
        obs_type="pixels",
        render_mode="rgb_array",
        observation_width=640,
        observation_height=480,
        visualization_width=640,
        visualization_height=480,
    ):
        self.task = task
        self.obs_type = obs_type
        self.render_mode = render_mode
        self.observation_width = observation_width
        self.observation_height = observation_height
        self.visualization_width = visualization_width
        self.visualization_height = visualization_height
        self.action_space = Box([-1.0] * ACTION_COUNT, [1.0] * ACTION_COUNT, dtype="float32")
        self.observation_space = Dict(
            {"top": Box(0, 255, shape=(observation_height, observation_width, 3), dtype="uint8")}
        )
        self._seed = None
        self._elapsed = 0
        self._score = 0
        self._image = _make_image(None, 0, None)
        self._closed = False

    def reset(self, seed=None, options=None):
        self._seed = seed
        self._elapsed = 0
        self._score = 0
        self._image = _make_image(seed, 0, None)
        return {"top": _copy_image(self._image)}, {"is_success": False}

    def step(self, action):
        if not isinstance(action, (list, tuple)) or len(action) != ACTION_COUNT:
            raise ValueError(f"the action must have {ACTION_COUNT} values")
        values = [float(item) for item in action]
        if any(item < -1.0 or item > 1.0 for item in values):
            raise ValueError("the action is outside the Box(-1, 1) action space")
        self._elapsed += 1
        # placeholder: the fake's success rule, not the upstream insertion contact test (sim.py:177-222).
        if values[0] > SUCCESS_ACTION_THRESHOLD and values[6] > SUCCESS_ACTION_THRESHOLD:
            self._score += 1
        else:
            self._score = 0
        reward = float(self._score)
        terminated = reward == float(SCORE_TARGET)  # env.py:240: terminated is reward == 4
        truncated = self._elapsed >= MAX_EPISODE_STEPS
        self._image = _make_image(self._seed, self._elapsed, values)
        info = {"is_success": terminated}
        return {"top": _copy_image(self._image)}, reward, terminated, truncated, info

    def render(self):
        return _copy_image(self._image)

    def close(self):
        self._closed = True

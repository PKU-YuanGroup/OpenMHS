"""Fake backend of the VIMA-Bench driver: a pure Python stand-in for ``vima_bench.env.base:VIMAEnvBase``.

Why a fake: the acceptance gate runs without pybullet, gym 0.21.0 or the clone's assets (``requirements.txt:1-2``),
and package code never imports the clone.  This module mirrors the *interface* of the upstream class (the class the
driver names as ``native``): ``reset(workspace_only=False)``, ``step(action=None, skip_oracle=True)``, ``seed(seed)``,
``close()`` and ``get_prompt_and_assets``, plus the ``action_space``, ``observation_space``, ``prompt``,
``prompt_assets``, ``meta_info`` and ``_env_seed`` attributes the upstream class has (gate G7).

The public members are the upstream class's members (gate G7).  The action-space bounds are the upstream's real
bounds (``vima_bench/env/base.py:181-196``) and the observation modalities/views are the upstream defaults
(``vima_bench/env/base.py:69-106``, ``vima_bench/tasks/task_suite/base.py:67-114``).  Everything else here is test
data, marked ``# placeholder``: the start positions, the target, the success radius, the prompt text, the ee value
and the small image arrays.  The fake never uses PyBullet, the UR5, the assets or a task's success/failure logic, so
it cannot reproduce the upstream environment; it was not compared with it.  The real observation arrays are
3 x 128 x 256 rgb and 128 x 256 segm per view by the task defaults, while the fake uses 3 x 2 x 2 and 2 x 2
placeholders to keep receipts small (named in the driver's fidelity gaps and RESULT.json).

Nothing here talks to a device.
"""

import random

# vima_bench/env/base.py:181-196: the upstream action-space Box bounds.
POSITION_LOW = (0.25, -0.5)
POSITION_HIGH = (0.75, 0.50)
ROTATION_LOW = -1.0
ROTATION_HIGH = 1.0
# vima_bench/env/base.py:69-106 and tasks/task_suite/base.py:67-114: the default modalities and views.
MODALITIES = ("rgb", "segm")
VIEWS = ("front", "top")
# placeholder: the fake's small image shape (the task default is (128, 256), tasks/task_suite/base.py:67).
IMAGE_SIZE = (2, 2)  # placeholder
# placeholder: the fake's start draw, target and success radius.
START_LOW = (0.30, -0.40)  # placeholder
START_HIGH = (0.45, -0.25)  # placeholder
TARGET_XY = (0.60, 0.20)  # placeholder
SUCCESS_RADIUS = 0.05  # placeholder
# placeholder: the fake's prompt text and end-effector indicator.
PROMPT = "put the object into the object"  # placeholder
EE_SUCTION = 0  # placeholder


class Box:
    """Duck-typed ``gym.spaces.Box``: a low/high bound per element of a fixed shape."""

    def __init__(self, low, high, shape):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = "float32"

    @staticmethod
    def _flat(value):
        if isinstance(value, (list, tuple)):
            out = []
            for item in value:
                out.extend(Box._flat(item))
            return out
        return [value]

    def contains(self, value):
        flat = self._flat(value)
        count = 1
        for size in self.shape:
            count *= size
        if len(flat) != count:
            return False
        if len(self.low) == count and len(self.high) == count:
            bounds = list(zip(self.low, self.high))
        else:  # a scalar channel bound, as gymnasium broadcasts it over the array
            bounds = [(min(self.low), max(self.high))] * count
        for item, (low, high) in zip(flat, bounds):
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                return False
            if not low <= item <= high:
                return False
        return True


class Discrete:
    """Duck-typed ``gym.spaces.Discrete``: the integers ``0 .. n - 1``."""

    def __init__(self, n):
        self.n = int(n)
        self.start = 0
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value):
        return isinstance(value, int) and not isinstance(value, bool) and 0 <= value < self.n


class Dict:
    """Duck-typed ``gym.spaces.Dict``: the same keys, each value in its own space."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)
        self.shape = ()
        self.dtype = None

    def contains(self, value):
        if not isinstance(value, dict) or set(value) != set(self.spaces):
            return False
        return all(self.spaces[key].contains(value[key]) for key in self.spaces)


class _Task:
    """Placeholder task stamp: only the seed and the name are stored (no upstream task logic)."""

    def __init__(self):
        self.task_name = "visual_manipulation"  # placeholder
        self.seed = None


class FakeVIMAEnv:
    """Stand-in for ``VIMAEnvBase``: the same public methods and spaces, with placeholder kinematics."""

    def __init__(self, **_options):
        self.modalities = list(MODALITIES)
        self.agent_cams = {view: {"image_size": IMAGE_SIZE} for view in VIEWS}  # placeholder image config
        position_bounds = Box(POSITION_LOW, POSITION_HIGH, (2,))
        self.action_space = Dict({
            "pose0_position": position_bounds,
            "pose0_rotation": Box((ROTATION_LOW,) * 4, (ROTATION_HIGH,) * 4, (4,)),
            "pose1_position": position_bounds,
            "pose1_rotation": Box((ROTATION_LOW,) * 4, (ROTATION_HIGH,) * 4, (4,)),
        })
        self.observation_space = Dict({
            "rgb": Dict({view: Box((0,) * 3, (255,) * 3, (3, *IMAGE_SIZE)) for view in VIEWS}),
            "segm": Dict({view: Box((0,), (255,), IMAGE_SIZE) for view in VIEWS}),
            "ee": Discrete(2),
        })
        self.task = _Task()
        self._env_seed = None
        self._rng = random.Random()
        self._tick = 0
        self._episode = 0
        self._object_xy = list(START_LOW)  # placeholder
        self._success = False
        self._failure = False
        self.prompt = None
        self.prompt_assets = None
        self.meta_info = {}

    def seed(self, seed=None):
        """``base.py:224-229``: make a fresh generator and store the seed."""
        self._rng = random.Random(seed)
        self._env_seed = seed
        self.task.seed = seed
        return seed

    def reset(self, workspace_only=False):
        """``base.py:248-389``: reload the scene and task and return the first observation."""
        self._tick = 0
        self._episode += 1
        self._object_xy = [
            self._rng.uniform(START_LOW[0], START_HIGH[0]),  # placeholder
            self._rng.uniform(START_LOW[1], START_HIGH[1]),  # placeholder
        ]
        self._success = False
        self._failure = False
        self.prompt = PROMPT  # placeholder
        self.prompt_assets = {}  # placeholder
        self.meta_info = {
            "end_effector_type": "suction",  # placeholder
            "n_objects": 1,  # placeholder
            "difficulty": "easy",  # placeholder
            "views": list(VIEWS),
            "modalities": list(self.modalities),
            "seed": self.task.seed,
        }
        observation = self._get_obs()
        assert self.observation_space.contains(observation)
        return observation

    def step(self, action=None, skip_oracle=True):
        """``base.py:391-455``: apply one primitive and return (obs, reward, done, info)."""
        if action is not None:
            assert self.action_space.contains(action), f"got {action} instead, action space {self.action_space}"
            self._object_xy = [float(action["pose1_position"][0]), float(action["pose1_position"][1])]
        self._tick += 1
        self._success = (
            (self._object_xy[0] - TARGET_XY[0]) ** 2 + (self._object_xy[1] - TARGET_XY[1]) ** 2
        ) ** 0.5 < SUCCESS_RADIUS  # placeholder dynamics
        observation = self._get_obs()
        assert self.observation_space.contains(observation)
        return observation, 0, bool(self._success), self._get_info()

    def get_prompt_and_assets(self):
        """``base.py:238-246``: the prompt and its assets, kept out of the Gym return."""
        return self.prompt, self.prompt_assets

    def close(self):
        """``base.py:221-222``: the fake has no PyBullet client to disconnect."""
        return None

    def _get_obs(self):
        """A small placeholder observation with the upstream nested Dict shape (base.py:663-673)."""
        tick = self._tick
        offset = int(self._object_xy[0] * 1_000_000 + self._object_xy[1] * 1_000) % 256  # placeholder
        rgb = {}
        segm = {}
        for index, view in enumerate(VIEWS):
            rgb[view] = [
                [[(tick * 11 + offset + index * 7 + row * 3 + col) % 256 for col in range(IMAGE_SIZE[1])]
                 for row in range(IMAGE_SIZE[0])]
                for _channel in range(3)
            ]
            segm[view] = [
                [(tick * 5 + offset + index * 9 + row + col) % 256 for col in range(IMAGE_SIZE[1])]
                for row in range(IMAGE_SIZE[0])
            ]
        return {"rgb": rgb, "segm": segm, "ee": EE_SUCTION}

    def _get_info(self):
        """``base.py:675-682``: the same three info keys as the upstream class."""
        return {"prompt": self.prompt, "success": bool(self._success), "failure": bool(self._failure)}

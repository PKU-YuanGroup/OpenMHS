"""Fake backend of the InternUtopia driver: a pure-Python stand-in for ``internutopia.core.gym_env:Env``.

Why a fake: the upstream Env constructor requires a ``Config`` and starts ``isaacsim.SimulationApp``
(internutopia/core/runner.py:477-486), and the acceptance gate has neither Isaac Sim nor a GPU.  This module
re-implements the parts of the class the Gymnasium bridge uses (``reset``, ``step``, ``close``; gate G7) and the two
spaces that ``internutopia/core/util/space.py:11-34`` hardcodes.  It is a kinematic stand-in, not Isaac Sim: it sets
the pose from the supplied path points and has no physics, actuator, sensor, contact or noise model.  Nothing here
talks to a device.

Every number that is this fake's test data rather than a value from the clone is marked ``# placeholder``.  The
space shapes and the ``-inf``/``inf`` bounds are taken from ``space.py:11-34``; the identity start pose is a
placeholder, not a fact about the upstream environment.
"""

import math
from collections.abc import Mapping

INF = math.inf


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: the bridge reads ``low``, ``high``, ``shape`` and ``dtype``."""

    def __init__(self, low, high, shape=()):
        self.low = low
        self.high = high
        self.shape = tuple(shape)
        self.dtype = "float32"


class Tuple:
    """Duck-typed ``gymnasium.spaces.Tuple``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = list(spaces)


class Sequence:
    """Duck-typed ``gymnasium.spaces.Sequence``; the bridge keeps a Sequence member unstructured."""

    def __init__(self, feature_space):
        self.feature_space = feature_space


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the bridge reads ``spaces``."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


def _action_space():
    """``get_action_space_by_task`` (space.py:11-25): one Sequence of (x, y, z) tuples with infinite bounds."""

    point = Tuple((Box(-INF, INF, shape=()), Box(-INF, INF, shape=()), Box(-INF, INF, shape=())))
    return Dict({"move_along_path": Sequence(point)})


def _observation_space():
    """``get_observation_space_by_task`` (space.py:28-34): position (3,) and orientation (4,), infinite bounds."""

    return Dict({
        "position": Box((-INF, -INF, -INF), (INF, INF, INF), shape=(3,)),
        "orientation": Box((-INF, -INF, -INF, -INF), (INF, INF, INF, INF), shape=(4,)),
    })


def _points(action):
    """The path points carried by an action, or ``None`` when the action carries none.

    The action space names ``move_along_path`` and the demo passes ``{name: [path]}`` (tests/h1_locomotion.py:58-61),
    so both a flat sequence of triples and that one-element wrapper are accepted.  This is the fake's own parsing;
    the upstream controller receives the raw action from ``Env.step`` (gym_env.py:130).
    """

    value = action.get("move_along_path") if isinstance(action, Mapping) else action
    if not isinstance(value, (list, tuple)):
        return None
    if len(value) == 1 and isinstance(value[0], (list, tuple)) and value[0] \
            and isinstance(value[0][0], (list, tuple)):
        value = value[0]
    points = []
    for item in value:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            return None
        try:
            points.append([float(item[0]), float(item[1]), float(item[2])])
        except (TypeError, ValueError):
            return None
    return points or None


class FakeInternUtopiaEnv:
    """A kinematic ``Env`` stand-in: ``reset`` and ``step`` return the Gymnasium tuple shapes of gym_env.py:100-140."""

    def __init__(self, **_options):
        self.action_space = _action_space()
        self.observation_space = _observation_space()
        # placeholder: the fake's start pose and the identity orientation; no upstream value states these
        self._position = [0.0, 0.0, 0.0]
        self._orientation = [0.0, 0.0, 0.0, 1.0]
        self._path = []
        self._path_index = 0
        self._tick = 0  # placeholder: the fake's step counter starts at zero
        self._seed = None
        self._closed = False

    def _observation(self):
        return {"position": list(self._position), "orientation": list(self._orientation)}

    def reset(self, *, seed=None, options=None):
        """``Env.reset(seed=None, options=None)`` (gym_env.py:62-87): the fake returns a fixed start pose.

        The seed and options are accepted because the upstream signature accepts them, but the upstream method
        uses neither (gym_env.py:62-87); the fake also keeps the start pose fixed.
        """

        self._seed = seed
        self._path = []
        self._path_index = 0
        self._tick = 0
        # placeholder: the fake's start pose, not a pose of any upstream scene
        self._position = [0.0, 0.0, 0.0]
        self._orientation = [0.0, 0.0, 0.0, 1.0]
        return self._observation(), {}

    def step(self, action):
        """One kinematic step: move to the next supplied path point, if any (gym_env.py:100-140 shape)."""

        points = _points(action)
        if points is not None and points != self._path:
            # The upstream controller resets its index only when the path changes
            # (internutopia_extension/controllers/move_along_path_points_controller.py:41-46).
            self._path = points
            self._path_index = 0
        if self._path_index < len(self._path):
            point = self._path[self._path_index]
            self._position = [float(point[0]), float(point[1]), float(point[2])]
            self._path_index += 1
        self._tick += 1
        # placeholder: the fake has no task, reward or termination model; 0.0 / False are its stand-ins
        return self._observation(), 0.0, False, False, {}

    def close(self):
        """``Env.close`` (gym_env.py:180-183): the fake has no SimulationApp to close."""

        self._closed = True

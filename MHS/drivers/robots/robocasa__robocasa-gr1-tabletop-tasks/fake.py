"""Fake backend of the RoboCasa GR-1 Tabletop driver: a pure Python stand-in for ``GrootRoboCasaEnv``.

Why a fake: the gate runs without robosuite, robocasa, MuJoCo or the downloaded tabletop assets, and package code never
imports the clone.  This module re-implements only the public surface of
``robocasa.utils.gym_utils.gymnasium_groot:GrootRoboCasaEnv`` that the Gymnasium bridge needs -- ``reset``, ``step``,
``render``, ``close``, ``action_space`` and ``observation_space`` -- with plain Python lists.  The spaces keep the
upstream shape: a ``spaces.Dict`` of five ``spaces.Box`` members in ``[-1, 1]`` named after the GR-1 arms-and-waist
mapping (``robocasa/models/robots/__init__.py:312-320``).  The upstream wrapper derives the keys with an ``action.``
prefix (``:203-213``), but the Gymnasium bridge addresses a Dict member as ``action.<key>``, so a key that already
starts with ``action.`` produces an unresolvable limit path; the fake drops that prefix and the driver's fidelity
``gaps`` say so.  The two space classes below duck-type ``gymnasium.spaces.Dict`` and ``gymnasium.spaces.Box`` (the
bridge reads ``spaces``, ``low``, ``high``, ``shape``); the ``Text`` class duck-types the language field
(``gymnasium_basic.py:176``).

What this is not: the upstream environment.  There is no MuJoCo, no robosuite, no controller, no contact or actuator
model and no rendering; the state transition is a placeholder first-order filter, the part dimensions are the default
GR-1 sizes named by the clone (a different controller configuration can change them), and the image is a 2 x 2 x 3
stand-in for the upstream 256 x 256 x 3 frame (``gymnasium_groot.py:19`` and ``:29``).  The driver's fidelity ``gaps`` say all of this.  Nothing here talks to a
device.
"""

import random

# Default GR-1 arms-and-waist part sizes named by the clone; a different composite controller configuration at run time
# can change them.  The arm count is the seven-value arm arrays (gr1_robot.py:50-53), the hand count is the six Fourier
# indices (robocasa/models/robots/__init__.py:24-25), and the waist count is the three values before the right arm.
_ARM_SIZE = 7
_HAND_SIZE = 6
_WAIST_SIZE = 3
_IMAGE_SHAPE = (2, 2, 3)   # placeholder for the upstream (256, 256, 3) frame (gymnasium_groot.py:19)
_START = 0.01              # placeholder bound of the initial state draw
_GAIN = 0.05               # placeholder scale of one action
_DECAY = 0.5               # placeholder memory of the first-order filter


class Box:
    """Duck-typed ``gymnasium.spaces.Box`` with a flat bound per element."""

    def __init__(self, low, high, shape):
        self.shape = tuple(int(value) for value in shape)
        count = 1
        for value in self.shape:
            count *= value
        self._count = count
        # scalar bounds: the bridge then derives one min/max pair instead of a per-element array, so a limit row does
        # not enumerate the element positions
        self.low = float(low)
        self.high = float(high)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: a mapping of names to subspaces."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class Text:
    """Duck-typed ``gymnasium.spaces.Text``: a bounded string field."""

    def __init__(self, max_length=256):
        self.max_length = int(max_length)
        self.shape = ()


class FakeRoboCasaEnv:
    """The public surface of ``GrootRoboCasaEnv`` without robosuite.

    ``reset(seed, options)`` returns ``(observation, info)`` and ``step(action)`` returns a five-tuple, as the
    Gymnasium API and the upstream wrapper do (``gymnasium_groot.py:120-128`` and ``:125-156``).
    """

    def __init__(self, **_options):
        self.action_space = Dict({
            "left_hand": Box(-1.0, 1.0, (_HAND_SIZE,)),
            "right_hand": Box(-1.0, 1.0, (_HAND_SIZE,)),
            "left_arm": Box(-1.0, 1.0, (_ARM_SIZE,)),
            "right_arm": Box(-1.0, 1.0, (_ARM_SIZE,)),
            "waist": Box(-1.0, 1.0, (_WAIST_SIZE,)),
        })
        self.observation_space = Dict({
            "state.left_arm": Box(-1.0, 1.0, (_ARM_SIZE,)),
            "state.right_arm": Box(-1.0, 1.0, (_ARM_SIZE,)),
            "state.left_hand": Box(-1.0, 1.0, (_HAND_SIZE,)),
            "state.right_hand": Box(-1.0, 1.0, (_HAND_SIZE,)),
            "state.waist": Box(-1.0, 1.0, (_WAIST_SIZE,)),
            "video.ego_view_pad_res256_freq20": Box(0.0, 255.0, _IMAGE_SHAPE),
            "annotation.human.coarse_action": Text(),
        })
        self._rng = random.Random()
        self._state = None
        self._frame = None
        self._tick = 0
        self._seed = None

    def _draw(self):
        return {name: [self._rng.uniform(-_START, _START) for _ in range(size)] for name, size in (
            ("left_hand", _HAND_SIZE),
            ("right_hand", _HAND_SIZE),
            ("left_arm", _ARM_SIZE),
            ("right_arm", _ARM_SIZE),
            ("waist", _WAIST_SIZE),
        )}

    def _observation(self):
        return {
            "state.left_arm": list(self._state["left_arm"]),
            "state.right_arm": list(self._state["right_arm"]),
            "state.left_hand": list(self._state["left_hand"]),
            "state.right_hand": list(self._state["right_hand"]),
            "state.waist": list(self._state["waist"]),
            "video.ego_view_pad_res256_freq20": self._frame,
            "annotation.human.coarse_action": "",
        }

    def _frame_value(self):
        # placeholder frame: a small constant image, not the upstream camera render
        return [[[0, 0, 0] for _ in range(_IMAGE_SHAPE[1])] for _ in range(_IMAGE_SHAPE[0])]

    def reset(self, seed=None, options=None):
        if seed is not None:
            self._rng = random.Random(seed)
            self._seed = int(seed)
        self._state = self._draw()
        self._frame = self._frame_value()
        self._tick = 0
        return self._observation(), {"success": False, "grasp_distractor_obj": False}

    def step(self, action):
        if self._state is None:
            raise RuntimeError("reset() must be called before step()")
        if not isinstance(action, dict):
            raise ValueError("the action must be a dict keyed by the controller parts")
        for name, space in self.action_space.spaces.items():
            values = action.get(name)
            if not isinstance(values, (list, tuple)) or len(values) != space._count:
                raise ValueError(f"action {name!r} must be a list of {space._count} numbers")
        for name in self.action_space.spaces:
            old = self._state[name]
            self._state[name] = [_DECAY * value + _GAIN * float(act)
                                 for value, act in zip(old, action[name])]
        self._tick += 1
        return self._observation(), 0.0, False, False, {"success": False, "grasp_distractor_obj": False}

    def render(self):
        if self._frame is None:
            raise RuntimeError("Must run reset or step before render.")
        return self._frame

    def close(self):
        self._state = None
        self._frame = None

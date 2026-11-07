"""Fake backend of the RoboCasa-G1 driver: a pure Python stand-in for ``GrootRoboCasaEnv``.

Why a fake: the gate does not install robosuite_g1, MuJoCo, gymnasium or the tabletop assets (README.md:29-42), and
package code never imports the clone.  This module models the public surface the driver uses -- ``reset(seed, options)``,
``step(action)`` and ``close()`` -- of ``GrootRoboCasaEnv`` (gymnasium_groot.py:23).  The action dict uses the upstream
keys ``action.<part>`` that ``G1ArmsAndWaistKeyConverter.unmap_action`` reads (robocasa/models/robots/__init__.py:
402-410); the observation dict uses the Groot keys ``state.<part>``, the four ``video.*`` camera keys and
``annotation.human.coarse_action`` (gymnasium_groot.py:106-153).

What this is not: the upstream environment.  There is no MuJoCo, robosuite, controller, contact, friction, actuator,
sensor or task-success model.  The state transition is a placeholder low-pass update, the camera frames are 2x2x3
placeholders while the observation space declares 256x256x3 (gymnasium_groot.py:20,29-30), and the initial state comes
from Python's ``random.Random`` while upstream seeds numpy's generator.  These differences are listed in the driver's
fidelity ``gaps``.  Every number below is test data, not a fact about the device, and is marked ``# placeholder``.

Nothing here talks to a device.
"""

import random

#: The five part actions and their array lengths in the repository example (test_env.py:25-33).
#: placeholder: the live lengths come from the robosuite controller configuration, not from this clone.
PARTS = (
    ("left_hand", 7),    # placeholder
    ("right_hand", 7),   # placeholder
    ("left_arm", 7),     # placeholder
    ("right_arm", 7),    # placeholder
    ("waist", 3),        # placeholder
)

#: placeholder: the initial part positions are drawn uniformly from this interval.
INITIAL_LOW, INITIAL_HIGH = -0.05, 0.05
#: placeholder: a low-pass update keeps each part position inside the declared state Box(-1, 1).
DECAY, GAIN = 0.99, 0.01
#: placeholder: a 2x2x3 zero frame; the observation space declares 256x256x3 (gymnasium_groot.py:29-30).
FRAME = [[[0, 0, 0], [0, 0, 0]], [[0, 0, 0], [0, 0, 0]]]
#: placeholder: the task language the fake reports.
LANGUAGE = "open the cabinet door"

_VIDEO_KEYS = (
    "video.ego_view_pad_res256_freq20",
    "video.ego_view_bg_crop_pad_res256_freq20",
    "video.rs_view_pad_res256_freq20",
    "video.world_view",
)


def _frame():
    """A fresh 2x2x3 placeholder frame (the real frames are 256x256x3, gymnasium_groot.py:20,29-30)."""
    return [[list(pixel) for pixel in row] for row in FRAME]


class FakeGrootRoboCasaEnv:
    """``GrootRoboCasaEnv`` without robosuite: ``reset``, ``step`` and ``close`` only (gate G7)."""

    def __init__(self, **_options):
        self._closed = False
        self._started = False
        self._seed = 0
        self._rng = random.Random(self._seed)
        self._positions = {part: [0.0] * length for part, length in PARTS}   # placeholder
        self._tick = 0
        self._language = LANGUAGE                                             # placeholder

    def reset(self, seed=None, options=None):
        """``GrootRoboCasaEnv.reset(seed, options)`` -> ``(observation, info)``; options is ignored upstream too."""
        self._closed = False
        if seed is not None:
            self._seed = int(seed)
            self._rng = random.Random(self._seed)
        self._positions = {
            part: [self._rng.uniform(INITIAL_LOW, INITIAL_HIGH) for _ in range(length)]   # placeholder
            for part, length in PARTS
        }
        self._tick = 0
        self._started = True
        return self._observation(), {"success": False, "grasp_distractor_obj": False}

    def step(self, action):
        """``GrootRoboCasaEnv.step(action)`` -> ``(observation, reward, terminated, truncated, info)``."""
        if self._closed:
            raise RuntimeError("the environment is closed")
        if not self._started:
            raise RuntimeError("call reset before step")
        for part, length in PARTS:
            values = action["action." + part]
            if len(values) != length:
                raise ValueError(f"action.{part} must have {length} elements, got {len(values)}")
            target = self._positions[part]
            for index, value in enumerate(values):
                target[index] = DECAY * target[index] + GAIN * float(value)   # placeholder
        # gymnasium_basic.py:69 and :256: the wrapper passes ignore_done=True and always sets truncated False.
        self._tick += 1
        return self._observation(), 0.0, False, False, {"success": False, "grasp_distractor_obj": False}

    def close(self):
        """``GrootRoboCasaEnv.close`` delegates to the inner environment (gymnasium_basic.py:270-271)."""
        self._closed = True

    def _observation(self):
        """The Groot keys of ``get_groot_observation`` (gymnasium_groot.py:106-153)."""
        observation = {f"state.{part}": list(values) for part, values in self._positions.items()}
        for key in _VIDEO_KEYS:
            observation[key] = _frame()
        # gymnasium_groot.py:147-150: G1ArmsAndWaist uses "unlocked_waist: <language>".
        observation["annotation.human.coarse_action"] = "unlocked_waist: " + self._language
        return observation

"""Fake backend of the manipulator-mujoco driver: a pure Python stand-in for ``AuboI5Env``.

Why a fake: the upstream environment imports ``mujoco``, ``dm_control``, ``numpy`` and ``gymnasium``
(``requirements.txt:1-4``); ``mujoco``, ``dm_control`` and ``gymnasium`` are not installed where the acceptance gate
runs, the gate never installs the upstream package, and package code never imports the clone.  This module mirrors
the public surface of
``manipulator_mujoco.envs.aubo_i5_env:AuboI5Env`` (the class the driver names as ``native``): ``reset``, ``step``,
``render`` and ``close`` (gate G7), plus the two spaces, duck-typed by the ``Box`` class below (the bridge reads
``low``, ``high`` and ``shape``).

What this is not: the upstream environment.  The upstream ``step`` runs the operational-space controller and
MuJoCo on a model with meshes, contacts and tendons; this fake keeps only a tick counter and returns the constant
all-zero observation that the upstream ``_get_obs`` returns.  It does not integrate dynamics, does not render and
was never compared with the upstream environment (the fidelity ``gaps`` of the driver say so).  The numbers here
are test data for the bridge, not facts: they are marked ``# placeholder`` and every Fact cites the upstream line
that defines the interface, not this file.

Nothing here talks to a device.
"""

import math

# The upstream spaces (manipulator_mujoco/envs/aubo_i5_env.py:22-29) mirrored for the bridge; test data here.
OBSERVATION_SIZE = 6                             # placeholder
ACTION_LOW = -0.1                                # placeholder
ACTION_HIGH = 0.1                                # placeholder
# The upstream metadata (manipulator_mujoco/envs/aubo_i5_env.py:15-18); strings only, no numeric claim.
RENDER_MODES = ["human", "rgb_array"]


class Box:
    """Duck-typed one-dimensional ``gymnasium.spaces.Box``: a lower and an upper bound per element."""

    def __init__(self, low, high):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float64"


class FakeAuboI5Env:
    """The public API of ``AuboI5Env`` without MuJoCo: a tick counter and the upstream all-zero observation."""

    def __init__(self, render_mode=None):
        if render_mode is not None and render_mode not in RENDER_MODES:
            raise ValueError(f"render_mode {render_mode!r} is not one of {RENDER_MODES}")
        self.metadata = {"render_modes": list(RENDER_MODES), "render_fps": None}
        self.observation_space = Box([-math.inf] * OBSERVATION_SIZE, [math.inf] * OBSERVATION_SIZE)
        self.action_space = Box([ACTION_LOW] * OBSERVATION_SIZE, [ACTION_HIGH] * OBSERVATION_SIZE)
        self._render_mode = render_mode
        self._tick = 0                                       # placeholder
        self._seed = None
        self._closed = False

    def _get_obs(self):
        # aubo_i5_env.py:88-90: the upstream observation is the constant zeros(6)
        return [0.0] * OBSERVATION_SIZE                     # placeholder

    def _get_info(self):
        # aubo_i5_env.py:92-94
        return {}

    def reset(self, seed=None, options=None):
        # aubo_i5_env.py:96-109: the upstream reset accepts seed and options and returns the observation and info.
        self._seed = seed
        self._tick = 0                                       # placeholder
        return self._get_obs(), self._get_info()

    def step(self, action):
        # aubo_i5_env.py:111-133: the upstream step ignores the action, advances the physics once and returns
        # reward 0 with terminated and truncated False.  The fake advances only its tick counter.
        self._tick += 1                                      # placeholder
        return self._get_obs(), 0.0, False, False, self._get_info()   # placeholder reward

    def render(self):
        # aubo_i5_env.py:135-143: only rgb_array is rendered upstream; the fake has no frame to return.
        if self._render_mode == "rgb_array":
            return self._render_frame()
        return None

    def _render_frame(self):
        return None

    def close(self):
        # aubo_i5_env.py:173-178: close the viewer if one was launched; the fake has none.
        self._closed = True

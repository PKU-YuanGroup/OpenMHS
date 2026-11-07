"""Fake backend of the BiGym 2.0 driver: a pure Python kinematic stand-in for ``bigym.loco.gym_adapter:GymnasiumEnv``.

Why a fake: the acceptance gate runs without the upstream package (pyproject.toml requires mujoco, dm-env, gymnasium
and more, and package code never imports or runs the clone), so the ``fake`` backend is this package's own
environment object.  It implements only the public members of the upstream class that the gymnasium bridge uses:
``reset``, ``step`` and ``close`` (gate G7 checks this against the class in the clone).  The two helper space classes
duck-type ``gymnasium.spaces.Box`` and ``Dict``: the bridge reads ``low``, ``high``, ``shape``, ``dtype`` and
``spaces``.

Every numeric constant below is test data, not a fact: the markers ``# placeholder`` name the upstream quantity it
stands in for.  What this is not, all listed in the driver's fidelity ``gaps``:

* the real environment is a MuJoCo rigid-body simulation with a G1 humanoid; this fake advances a small state vector
  directly, with no dynamics, contacts, actuators, sensors or noise;
* the real observation is a Dict with an rgb array of ``(3, 3, 84, 84)`` uint8 by default and a state whose length is
  summed over the configured state keys; this fake returns a one-camera 4x4 image and a 12-value state;
* the real action vector length is computed from the selected G1 actuators and the controller; this fake uses 24
  placeholder slots;
* the fake draws its reset state with Python's ``random.Random`` while upstream draws the episode seed from numpy's
  generator, so one seed does not give the same trajectory on the two;
* there is no rendering and no snapshot/restore.

Nothing here talks to a device.
"""

import math
import random

ACTION_DIM = 24                              # placeholder: bigym/loco/env.py:921-923 computes the real action length
STATE_DIM = 12                               # placeholder: bigym/loco/env.py:1011-1039 sums the configured state keys
CAMERA_COUNT = 1                             # placeholder: the default is len(("head", "right_wrist", "left_wrist"))
FRAME_CHANNELS = 3                           # placeholder: the upstream frame is 3 * frame_stack channels
FRAME_SIZE = 4                               # placeholder: the default camera_shape is (84, 84)
EPISODE_TICKS = 10000                        # placeholder: bigym/loco/tasks.py:158 registers a 13500 inner-step budget
STEP_GAIN = 0.01                             # placeholder: arbitrary kinematic response of the stand-in state


class Box:
    """Duck-typed ``gymnasium.spaces.Box``: a flattened lower and upper bound, a shape and a dtype."""

    def __init__(self, low, high, shape, dtype):
        self.low = list(low)
        self.high = list(high)
        self.shape = tuple(shape)
        self.dtype = dtype


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``: the named subspaces of the observation."""

    def __init__(self, spaces):
        self.spaces = dict(spaces)


class FakeGymnasiumEnv:
    """``GymnasiumEnv`` without MuJoCo: ``reset(seed, options)`` and ``step(action)`` return its 5-tuple shape."""

    def __init__(self, task_name="drawer_top_open"):
        # placeholder: the upstream class derives both spaces from the wrapped bigym.loco environment
        self.action_space = Box([-1.0] * ACTION_DIM, [1.0] * ACTION_DIM, (ACTION_DIM,), "float32")
        rgb_count = CAMERA_COUNT * FRAME_CHANNELS * FRAME_SIZE * FRAME_SIZE
        self.observation_space = Dict(
            {
                "rgb": Box([0] * rgb_count, [255] * rgb_count,
                           (CAMERA_COUNT, FRAME_CHANNELS, FRAME_SIZE, FRAME_SIZE), "uint8"),
                "state": Box([-math.inf] * STATE_DIM, [math.inf] * STATE_DIM, (STATE_DIM,), "float32"),
            }
        )
        self._task_name = task_name
        self._rng = random.Random()
        self._state = None
        self._tick = 0

    def reset(self, *, seed=None, options=None):
        """Start an episode; ``options`` is accepted for the gymnasium signature and not read by the fake."""
        if seed is not None:
            self._rng = random.Random(seed)
        # placeholder: the upstream state is the wrapped environment's low_dim_obs and rgb_obs
        self._state = [self._rng.uniform(-1.0, 1.0) for _ in range(STATE_DIM)]
        self._tick = 0
        return self._observation(), {
            "success": False,
            "fell": False,
            "event_progress": None,
            "discount": 1.0,
        }

    def step(self, action):
        """Advance one outer control step with the normalized action and return the gymnasium 5-tuple."""
        if self._state is None:
            raise RuntimeError("reset() must be called before step()")
        values = list(action)
        if len(values) != ACTION_DIM:
            raise ValueError(f"expected {ACTION_DIM} action values, got {len(values)}")
        if any(value < -1.0 or value > 1.0 for value in values):
            raise ValueError("the action is outside the action space")
        self._tick += 1
        # placeholder: no physics; the stand-in state moves by STEP_GAIN per unit of the first STATE_DIM actions
        self._state = [
            max(-1.0, min(1.0, self._state[index] + STEP_GAIN * float(values[index])))
            for index in range(STATE_DIM)
        ]
        truncated = self._tick >= EPISODE_TICKS
        return self._observation(), 0.0, False, truncated, {
            "success": False,
            "fell": False,
            "event_progress": None,
            "discount": 0.0 if truncated else 1.0,
        }

    def close(self):
        """Release the stand-in state, as the upstream close() releases the wrapped environment."""
        self._state = None

    def _observation(self):
        rgb = [0] * (CAMERA_COUNT * FRAME_CHANNELS * FRAME_SIZE * FRAME_SIZE)  # placeholder: black stand-in frame
        rgb[0] = self._tick % 256                                             # placeholder: a visible tick pixel
        return {"rgb": rgb, "state": list(self._state)}
